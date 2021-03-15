import os
import json
import datetime as dt
from datetime import timezone
import threading

from flask import Flask, render_template, session, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from bokeh.embed import components

from cg_scraper import CGScraper
from high_charts_builder import HCBuilder
from bokeh_plots_builder import BPBuilder
from ajax import AjaxBokeh
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
tnames = [table.__tablename__ for table in tables]

cg_scraper = CGScraper(tables, db)
hc_builder = HCBuilder(tables)
bp_builder = BPBuilder(tables)
ajax_bokeh = AjaxBokeh()

cps = {
    table.__tablename__: title_dict[table.__tablename__]
    for table in tables
}

@app.route('/')
def index():
    return render_template('index.html')
#
# @app.route('/stream')
# def stream():
#     return render_template('highcharts.html', currency_pairs=cps)

@app.route('/stream_highcharts', methods=["GET","POST"])
def stream_highcharts():
    return render_template('highcharts.html', currency_pairs=cps)

@app.route('/stream_bokeh', methods=["GET","POST"])
def stream_bokeh():
    return render_template('bokeh.html', currency_pairs=cps)

@app.route('/data/<choice>')
def data(choice):
    now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
    is_closed = closed(now)
    if choice == 'bokeh':
        response = bp_builder.build_response(is_closed)
    elif choice == 'highcharts':
        response = hc_builder.build_response(is_closed)
    return jsonify(response)

# @app.route('/chart')
# def chart():
#     now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
#     is_closed = closed(now)
#     response = hc_builder.build_response(is_closed)
#     return jsonify(response)

@app.route('/new_tab')
def new_tab():
    return render_template('new_tab.html')

@app.route('/bokeh')
def bokeh():
    p = ajax_bokeh.p
    script, div = components(p)
    return render_template('bokeh2.html', script=script, div=div)

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

def run_bokeh():
    ajax_bokeh.run()

if __name__ == "__main__":
    threading.Thread(target=scrape).start()
    threading.Thread(target=run).start()
    threading.Thread(target=run_bokeh).start()
