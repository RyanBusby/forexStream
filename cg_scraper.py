import os
import datetime as dt
from datetime import timezone, timedelta
from dateutil.relativedelta import relativedelta, FR
import requests

from ratelimit import limits

from market_dicts import market_ids, price_types

class CGScraper():
    def __init__(self, tables, db, minutes=30):
        self.pword = os.getenv('upass')
        self.base = 'https://ciapi.cityindex.com/TradingAPI'
        self.appkey = os.getenv('cg_api')
        self.user = os.getenv('cg_uname')
        self.session = self.get_session_id(self.pword)

        self.tables = tables
        self.db = db

        self.minutes=minutes


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
                latest_ts = dt.datetime.fromtimestamp(
                    latest_ts.timestamp(), tz=timezone.utc
                )
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

    def get_session_id(self, pword):
        '''
        call this only when necessary
        might be cool to persist this and only get it when it errors
        '''
        target = 'session'
        payload = {
            "Password":pword,
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
        latest_ts = table.query\
            .order_by(table.timestamp.desc())\
            .first().timestamp.replace(microsecond=0)
        latest_ts = dt.datetime.fromtimestamp(
            latest_ts.timestamp(), tz=timezone.utc
        )
        if latest_ts >= self.last_ts:
            return True, latest_ts
        else:
            return False, latest_ts

    def check_error(self, response, status_code):
        # make this better
        if status_code != 200 and 'ErrorCode' in ticks:
            if ticks['ErrorCode'] == 4011:
                self.session = get_session_id(self.pword)
                # print('new session id requested')
                return
            else:
                raise Exception(ticks)
        elif status_code == 200:
            return
        else:
            raise Exception(ticks)

    def convert_wcf(self, wcf):
    	epoch = dt.datetime(1970, 1, 1, tzinfo=timezone.utc)
    	utc_dt = epoch + timedelta(milliseconds=wcf)
    	return utc_dt
