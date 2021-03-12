import os
import requests
from datetime import datetime as dt
from datetime import timedelta, timezone

from market_dicts import market_ids, price_types

class DataHandler():
    def __init__(self, tables, db):
        pword = os.getenv('cg_pword')
        self.base = 'https://ciapi.cityindex.com/TradingAPI'
        self.appkey = os.getenv('cg_api')
        self.user = os.getenv('cg_uname')
        self.session = self.get_session_id(pword)
        self.tables = tables
        self.db = db

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
        return ticks['PriceTicks']

    def load_ticks(self):
        cutoff = dt.now() - timedelta(minutes=15)
        for table in self.tables:
            tname = table.__tablename__
            market_id = market_ids[tname]
            price_type = price_types[tname]
            while True:
                latest_ts = table.query\
                .order_by(table.timestamp.desc()).first().timestamp
                if latest_ts < cutoff:
                    l_ts = int(cutoff.timestamp())
                    ticks = self.get_ticks_after(
                        market_id,
                        l_ts,
                        price_type
                    )
                else:
                    l_ts = int(latest_ts.timestamp())
                    ticks = self.get_ticks_after(
                        market_id,
                        l_ts,
                        price_type
                    )
                rows = [
                    table(
                        timestamp=self.convert_wcf(
                            int(tick['TickDate'][6:-2])
                        ),
                        rate=tick['Price']
                    ) for tick in ticks
                ]
                self.db.session.add_all(rows)
                self.db.session.commit()
                if len(rows) < 4000 and len(rows) > 0:
                    break
                elif len(rows) == 0:
                    # this will break app, do some error handling
                    break
        return

    def convert_wcf(self, wcf):
    	epoch = dt(1970, 1, 1, tzinfo=timezone.utc)
    	utc_dt = epoch + timedelta(milliseconds=wcf)
    	return utc_dt
