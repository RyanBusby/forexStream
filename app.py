import threading
import datetime as dt
from datetime import timezone, timedelta

from flask import render_template, jsonify

from models import app, db, tables, ohlc_tables, tnames, cps
from cg_scraper import CGScraper
from high_charts_builder import HCBuilder
from bokeh_plots_builder import BPBuilder

cg_scraper = CGScraper(tables, ohlc_tables, db)
hc_builder = HCBuilder(tables, ohlc_tables, db)
bp_builder = BPBuilder(tables, ohlc_tables, db)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream-highcharts', methods=["GET","POST"])
def stream_highcharts():
    return render_template('highcharts.html', currency_pairs=cps)

@app.route('/stream-bokeh')
def stream_bokeh():
    script, divs = bp_builder.build_components()
    return render_template('bokeh.html', divs=divs, script=script, currency_pairs=cps)

@app.route('/ohlc-highcharts')
def ohlc_highcharts():
    return render_template('ohlc_highcharts.html', currency_pairs=cps)

@app.route('/ohlc-bokeh')
def ohlc_bokeh():
    script, divs = bp_builder.build_ohlc_components()
    return render_template('ohlc_bokeh.html', divs=divs, script=script, currency_pairs=cps)

@app.route('/returns-highcharts')
def returns_highcharts():
    return render_template('returns_highcharts.html', currency_pairs=cps)

@app.route('/returns-bokeh')
def returns_bokeh():
    script, div = bp_builder.build_returns_components()
    return render_template('returns_bokeh.html', div=div, script=script, currency_pairs=cps)

@app.route('/data/<type>', methods=['GET'])
def data(type):
    if type=='returns':
        response = hc_builder.build_returns_response()
        return jsonify(response)
    elif type=='stream-highcharts':
        now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
        is_closed = closed(now)
        response = hc_builder.build_response(is_closed)
        return jsonify(response)
    elif type=='ohlc-highcharts':
        now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
        is_closed = closed(now)
        response = hc_builder.build_ohlc_response(is_closed)
        return jsonify(response)

@app.route("/data/<tname>/<int:cutoff>", methods=['POST'])
def get_data(tname, cutoff):
    table = tnames[tname]
    n_minutes_ago = dt.datetime.now() - timedelta(minutes=cutoff)
    rows = table.query\
        .filter(table.timestamp > n_minutes_ago)\
        .order_by(table.timestamp)\
        .all()
    timestamps = []
    rates = []
    for row in rows:
        x = row.timestamp.timestamp()*1000
        y = row.rate
        timestamps.append(x)
        rates.append(y)
    return jsonify(timestamp=timestamps, rate=rates)

def closed(now):
	return (
    	(now.weekday() == 4 and now.time() >= dt.time(21,1))\
    	| (now.weekday() == 5) \
    	| (now.weekday() == 6 and now.time() < dt.time(21))
    )

'''
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500
'''

# @app.route('/returns_data')
# def returns_data():
#     response = hc_builder.build_returns_response()
#     return jsonify(response)

# @app.route('/ohlc_data')
# def ohlc_data():
#     now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
#     is_closed = closed(now)
#     response = hc_builder.build_ohlc_response(is_closed)
#     return jsonify(response)

# @app.route('/hcdata')
# def data():
#     now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
#     is_closed = closed(now)
#     response = hc_builder.build_response(is_closed)
#     hcdata = jsonify(response)
#     return hcdata

def scrape():
    while True:
        now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
        is_closed = closed(now)
        day_now = now.replace(hour=0,minute=0,second=0)
        cg_scraper.loadticks(now, is_closed)
        cg_scraper.loadbars(day_now, is_closed)

def run():
    app.run()

if __name__ == "__main__":
    threading.Thread(target=scrape).start()
    threading.Thread(target=run).start()
