import os
import datetime as dt
from datetime import timezone, timedelta
from dateutil.relativedelta import relativedelta, FR
import requests

from ratelimit import limits

from market_dicts import market_ids, price_types

class CGScraper():
	def __init__(self, tables, ohlc_tables, db, minutes=30):

		self.base = os.getenv('cg_base')
		self.appkey = os.getenv('cg_api')
		self.user = os.getenv('cg_uname')
		self.pword = os.getenv('cg_pword')

		self.session = self.get_session_id()

		self.tables = tables
		self.ohlc_tables = ohlc_tables

		self.db = db

		self.minutes=minutes

	def loadbars(self, now, is_closed):
		# get latest date in db.
		# if not yesterday, get bars between the latest day and yesterday
		for table in self.ohlc_tables:
			# cp is currencypair
			cp = table.__tablename__[:6]
			yesterday = now - timedelta(hours=24)

			'''
			date.weekday()
			Return the day of the week as an integer, where Monday is 0 and Sunday is 6.
			'''

			if is_closed and now.weekday() == 4:
				# if the market is closed but its still friday, we want bars up to today; there won't be any partial bars
				yesterday = now

			elif is_closed and now.weekday() == 5:
				# if the market is closed and its saturday we want bars up to the previous friday. this block is here just for consistency
				yesterday = now + relativedelta(weekday=FR(-1))

			elif now.weekday() == 0:
				# anytime it's sunday even when the market is open, we want price bars from the previous friday. if not the loop will run continuously trying to get a price bar from saturday and that will never occur
				yesterday = now + relativedelta(weekday=FR(-1))

			# TODO!: forex market is also closed on christmas and new year's day, work in logic for that

			while True:
				latest_local_ts = table.query\
				.order_by(
					table.timestamp.desc()
				)\
				.first()

				if latest_local_ts is None:
					latest = dt.datetime(1970,1,1)

				# you can avoid all this converting back and forth if you just load the db with either tz unaware utc times or straight up timestamps

				else:
					latest = latest_local_ts.timestamp\
					.replace(hour=0,minute=0,second=0,microsecond=0)
				yesterday = yesterday.replace(tzinfo=None)

				if latest == yesterday:
					break
				# use yesterday to not get a partial bar
				latest_ts = int(latest.timestamp())
				yesterday_ts = int(yesterday.timestamp())
				market_id = market_ids[cp]
				price_type = price_types[cp]
				bars, status_code = self.get_bars_between(
					latest_ts,
					yesterday_ts,
					market_id,
					price_type
				)
				self.check_error(bars, status_code)
				rows = []
				for bar in bars['PriceBars']:
					date = self.convert_wcf_notz(
						int(bar['BarDate'][6:-2])
					)
					open_ = bar['Open']
					high = bar['High']
					low = bar['Low']
					close = bar['Close']
					row = table(
						timestamp=date,
						open=open_,
						high=high,
						low=low,
						close=close
					)
					rows.append(row)
				self.db.session.add_all(rows)
				self.db.session.commit()


	def get_bars_between(self,latest, yesterday, market_id, price_type):
		target = 'market'
		uri = f'{market_id}/barhistorybetween'
		payload = {
			'interval': 'DAY',
			'span': 1,
			'fromTimeStampUTC': latest,
			'toTimeStampUTC': yesterday,
			'maxResults': 4000,
			'priceType': price_type,
			'UserName': self.user,
			'Session': self.session
		}
		url = f'{self.base}/{target}/{uri}'
		r = requests.get(url, params=payload)
		response = r.json()
		return response, r.status_code

	def loadticks(self, now, is_closed):
		if is_closed:
			m = int(59 - self.minutes)
			cutoff = (now + relativedelta(weekday=FR(-1)))\
				.replace(hour=14, minute=m, second=55)
		else:
			cutoff = now - timedelta(minutes=self.minutes)
		for table in self.tables:
			tname = table.__tablename__
			market_id = market_ids[tname]
			price_type = price_types[tname]
			while True:
				# if latest_ts >= now: don't scrape
				# elif cutoff < latest_ts < now: scrape from latest_ts
				# elif latest_ts < cutoff : scrape from cutoff
				is_current, latest_ts = self.db_is_current(table, cutoff)
				if is_current:
					break
				# leave while loop, continue for loop
				if cutoff < latest_ts < now:
					l_ts = int(latest_ts.timestamp())
				elif latest_ts < cutoff:
					l_ts = int(cutoff.timestamp())
				ticks, status_code = self.get_ticks_after(
					market_id,
					l_ts,
					price_type
				)
				# if session_id is invalid, get new and try again
				self.check_error(ticks, status_code)
				rows = [
					table(
						timestamp=self.convert_wcf(
							int(tick['TickDate'][6:-2])
						),
						rate=tick['Price']
					) for tick in ticks['PriceTicks']
				]
				if len(rows) == 4000:
					self.db.session.add_all(rows)
					self.db.session.commit()
				elif len(rows) < 4000 and len(rows) > 0:
					self.db.session.add_all(rows)
					self.db.session.commit()
					break
				elif len(rows) == 0:
					break

	def get_session_id(self):
		'''
		call this only when necessary
		might be cool to persist this and only get it when it errors
		'''
		target = 'session'
		payload = {
			"Password":self.pword,
			"AppVersion":"1",
			"AppComments":"",
			"UserName":self.user,
			"AppKey":self.appkey
		}
		url = f'{self.base}/{target}'
		r = requests.post(url, json=payload)
		s = r.json()['Session']
		return s

	'''
	The GCAPI servers have been set to throttle requests from the client UI application, if more than 500 requests are sent over a 5 second window. When throttling is activated, a 503 HTTP status code is returned. In this case, the client UI application must wait 1 second before sending further API requests.
	'''

	@limits(calls=500, period=5)
	def get_ticks_after(self, market_id, latest_ts, price_type):
		# add log to verify not double scraping
		target = 'market'
		uri = f'{market_id}/tickhistoryafter'
		payload = {
			'maxResults': 4000,
			'fromTimeStampUTC': latest_ts,
			'priceType': price_type,
			'UserName': self.user,
			'Session': self.session
		}
		url = f'{self.base}/{target}/{uri}'
		r = requests.get(url, params=payload)
		ticks = r.json()
		return ticks, r.status_code

	def db_is_current(self, table, cutoff):
		self.last_ts = cutoff+timedelta(minutes=self.minutes)
		# timestamp will be an ineger
		latest_ts = table.query\
			.order_by(table.timestamp.desc())\
			.first()
		if latest_ts is None:
			return False, dt.datetime(1970,1,1,tzinfo=timezone.utc)
		latest_ts = dt.datetime.fromtimestamp(
			latest_ts.timestamp.timestamp(), tz=timezone.utc
		)
		if latest_ts >= self.last_ts:
			return True, latest_ts
		else:
			return False, latest_ts

	def check_error(self, response, status_code):
		# make this better
		if status_code != 200 and 'ErrorCode' in response:
			if response['ErrorCode'] == 4011:
				self.session = get_session_id(self.pword)
				print('new session id requested')
				return
			else:
				raise Exception(response)
		elif status_code == 200:
			return
		else:
			raise Exception(response)

	def convert_wcf(self, wcf):
		epoch = dt.datetime(1970, 1, 1, tzinfo=timezone.utc)
		utc_dt = epoch + timedelta(milliseconds=wcf)
		return utc_dt

	def convert_wcf_notz(self, wcf):
		epoch = dt.datetime(1970, 1, 1, tzinfo=timezone.utc)
		utc_dt = epoch + timedelta(milliseconds=wcf)
		utc_dt = utc_dt.replace(tzinfo=None)
		return utc_dt
