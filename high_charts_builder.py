import os
import requests
import datetime as dt
from datetime import timedelta, timezone
from dateutil.relativedelta import relativedelta, FR
from time import mktime

from market_dicts import market_ids, price_types

class HCBuilder():
    '''
    DataHandler queries the the db and builds response objects for high charts.
    '''
    def __init__(self, tables, minutes=30):
        self.tables = tables
        # self.tick_tables = tick_tables
        # self.ohlc_tables = ohlc_tables
        self.minutes = minutes

    def build_response(self, is_closed):
        # get the latest entries
        response = {}
        cutoff = dt.datetime.now() - timedelta(minutes=self.minutes)
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
            if is_closed:
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
        response['closed'] = is_closed
        response['choice'] = 'highcharts'
        return response
