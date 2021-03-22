import os
import requests
import datetime as dt
from datetime import timedelta, timezone
from dateutil.relativedelta import relativedelta, FR

import pandas as pd

from market_dicts import market_ids, price_types

class HCBuilder():
    '''
    DataHandler queries the the db and builds response objects for high charts.
    '''
    def __init__(self, tables, ohlc_tables, db, minutes=30):
        self.tables = tables
        # self.tick_tables = tick_tables
        self.ohlc_tables = ohlc_tables
        self.minutes = minutes
        self.db = db

    def build_returns_response(self):
        response = {}
        cols = ['timestamp','close']
        for table in self.ohlc_tables:
            cp = table.__tablename__
            price_type = price_types[cp[:6]]
            '''
            direct markets:
                return = t1 quote / t0 quote

            indirect markets:
                return  = t0 quote / t1 quote

            to make this more accurate (account for spread)

            direct markets:
                return = t1 ask / t0 buy

            indirect markets:
                return = t0 buy / t1 ask
            '''
            if price_type == 'BID':
                period = -1
            elif price_type == 'ASK':
                period = 1
            df = pd.read_sql_table(cp, self.db.engine, columns=cols)\
                .set_index('timestamp', drop=True)
            three_years_ago = dt.datetime.now() - timedelta(days=365*3)
            df = df[df.index >= three_years_ago] # include range selector
            df = df.pct_change(period)
            df['close'] = df['close']*100
            df.dropna(inplace=True)
            df['t'] = df.index
            df['t'] = df['t'].apply(
                lambda x: int(x.timestamp()*1000)
            )
            df = df[['t','close']].values.tolist()
            response[cp[:6]] = {'data': df}
        return response

    def build_ohlc_response(self, is_closed):
        response = {}
        for table in self.ohlc_tables:
            rows = table.query.order_by(table.timestamp).all()
            table_data = []
            for row in rows:
                table_data.append(
                    [
                        row.timestamp.timestamp()*1000,
                        row.open,
                        row.high,
                        row.low,
                        row.close
                    ]
                )
            # change the cp in view to match this ohlc table name
            response[table.__tablename__[:6]] = {'data': table_data}
        response['closed'] = is_closed
        return response

    def build_response(self, is_closed):
        # get the latest entries
        response = {}
        cutoff = dt.datetime.now() - timedelta(minutes=self.minutes)
        if is_closed:
             cutoff = dt.datetime.now() + relativedelta(weekday=FR(-1))
             cutoff =\
             cutoff.replace(hour=14,minute=30,second=0,microsecond=0)
        for table in self.tables:
            rows = table.query\
                .filter(table.timestamp > cutoff)\
                .order_by(table.timestamp)\
                .all()
            table_data = []
            for x, row in enumerate(rows):
                if x == len(rows)-1:
                    last_ts = row.timestamp
                table_data.append(
                    [row.timestamp.timestamp()*1000, row.rate]
                )
            first_val = table_data[0][1]
            last_val = table_data[-1][1]
            delta = abs(round(last_val - first_val, 5))
            increasing = last_val > first_val
            if is_closed:
                five_after = last_ts+timedelta(minutes=5)
                table_data.append(
                    [int(five_after.timestamp()*1000), last_val]
                )
            response[table.__tablename__] = {
                'data': table_data,
                'last_val': last_val,
                'delta': delta,
                'increasing': increasing,
            }
        response['closed'] = is_closed
        response['choice'] = 'highcharts'
        return response
