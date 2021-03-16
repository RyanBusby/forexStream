import os
import json
import datetime as dt
from datetime import timezone, timedelta
import threading
import math
from time import mktime

from flask import Flask, render_template, session, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.models import AjaxDataSource

from cg_scraper import CGScraper
from high_charts_builder import HCBuilder
from bokeh_plots_builder import BPBuilder

from market_dicts import title_dict

u, p = os.getenv('uname'), os.getenv('upass')
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] =\
f'postgresql://{u}:{p}@localhost:5432/forexticks'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.urandom(16).hex()


db = SQLAlchemy(app)
migrate = Migrate(app, db)

class AUDUSD(db.Model):
    __tablename__ = 'audusd'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class EURUSD(db.Model):
    __tablename__ = 'eurusd'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class GBPUSD(db.Model):
    __tablename__ = 'gbpusd'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class NZDUSD(db.Model):
    __tablename__ = 'nzdusd'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class USDCAD(db.Model):
    __tablename__ = 'usdcad'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class USDCHF(db.Model):
    __tablename__ = 'usdchf'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    rate = db.Column(db.Float, nullable=False)

class USDJPY(db.Model):
    __tablename__ = 'usdjpy'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    rate = db.Column(db.Float, nullable=False)

tables = [AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY]
tnames = {table.__tablename__: table for table in tables}

cg_scraper = CGScraper(tables, db)
hc_builder = HCBuilder(tables)
bp_builder = BPBuilder(tables)

cps = {
    table.__tablename__: title_dict[table.__tablename__]
    for table in tables
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream_highcharts', methods=["GET","POST"])
def stream_highcharts():
    return render_template('highcharts.html', currency_pairs=cps)

@app.route('/stream_bokeh')
def stream_bokeh():
    script, divs = bp_builder.build_components()
    return render_template('bokeh.html', divs=divs, script=script, currency_pairs=cps)

@app.route('/hcdata')
def data():
    now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
    is_closed = closed(now)
    response = hc_builder.build_response(is_closed)
    return jsonify(response)

@app.route("/ajax_data/<tname>/<int:cutoff>", methods=['POST', "GET"])
def get_data(tname, cutoff):
    table = tnames[tname]
    thirty_ago = dt.datetime.now() - timedelta(minutes=cutoff)
    rows = table.query\
        .filter(table.timestamp > thirty_ago)\
        .order_by(table.timestamp)\
        .all()
    timestamps = []
    rates = []
    for row in rows:
        x = row.timestamp.timestamp()*1000
        y = row.rate
        timestamps.append(x)
        rates.append(y)

    if rates[0] > rates[-1]:
        color = 'red'
    else:
        color = 'green'

    colors = [color for _ in range(len(rates))]

    return jsonify(timestamp=timestamps, rate=rates, color=colors)


@app.route('/new_tab')
def new_tab():
    return render_template('new_tab.html')

def closed(now):
	return (
    	(now.weekday() == 4 and now.time() >= dt.time(21,1))\
    	| (now.weekday() == 5) \
    	| (now.weekday() == 6 and now.time() < dt.time(21))
    )
def scrape():
    while True:
        now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
        is_closed = closed(now)
        cg_scraper.loadticks(now, is_closed)

def run():
    app.run()

if __name__ == "__main__":
    threading.Thread(target=scrape).start()
    threading.Thread(target=run).start()
