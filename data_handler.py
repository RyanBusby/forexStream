import os
import requests
from datetime import datetime as dt
from datetime import timedelta, timezone
from dateutil.relativedelta import relativedelta, FR
from time import mktime

from market_dicts import market_ids, price_types

class DataHandler():
    '''
    DataHandler queries the cgapi then inserts results into db.
    It also queries the db and builds response objects.
    '''
    def __init__(self, tables, db, minutes=30):
        self.pword = os.getenv('upass')
        self.base = 'https://ciapi.cityindex.com/TradingAPI'
        self.appkey = os.getenv('cg_api')
        self.user = os.getenv('cg_uname')
        self.session = self.get_session_id(self.pword)
        self.tables = tables
        # self.tick_tables = tick_tables
        # self.ohlc_tables = ohlc_tables
        self.db = db
        self.minutes = minutes

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

    def db_is_current(self, table, cutoff):
        self.last_ts = cutoff+timedelta(minutes=self.minutes)
        latest_ts = table.query\
            .order_by(table.timestamp.desc())\
            .first().timestamp.replace(microsecond=0)
        if latest_ts >= self.last_ts:
            return True, latest_ts
        else:
            return False, latest_ts

    def load_ticks(self):
        # check if market is open
        # if its closed - make sure db is loaded up until close
        # if lastest_ts from db is 15 min after cutoff - don't scrape
        now = dt.now().replace(microsecond=0)
        is_closed = self.closed(now)
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
        return cutoff

    def convert_wcf(self, wcf):
    	epoch = dt(1970, 1, 1, tzinfo=timezone.utc)
    	utc_dt = epoch + timedelta(milliseconds=wcf)
    	return utc_dt

    def build_response(self, cutoff):
        response = {}
        _closed = False
        if self.closed(dt.now()):
            _closed = True
        for table in self.tables:
            rows = table.query\
                .filter(table.timestamp > cutoff)\
                .order_by(table.timestamp)\
                .all()
            table_data = []
            for row in rows:
                table_data.append(
                    [mktime(row.timestamp.timetuple())*1000, row.rate]
                )
            first_val = table_data[0][1]
            last_val = table_data[-1][1]
            delta = abs(round(last_val - first_val, 5))
            increasing = last_val > first_val
            if _closed:
                five_after = self.last_ts+timedelta(minutes=5)
                table_data.append(
                    [mktime(five_after.timetuple())*1000, last_val]
                )
            response[table.__tablename__] = {
                'data': table_data,
                'last_val': last_val,
                'delta': delta,
                'increasing': increasing,
            }
        response['closed'] = _closed
        return response


    def closed(self, now):
        # this is specific to mst.. fix to work anywhere
    	return (
        	(now.weekday() == 4 and now.time() >= dt.time(21,1))\
        	| (now.weekday() == 5) \
        	| (now.weekday() == 6 and now.time() < dt.time(21))
        )
