import os
import json
from datetime import datetime as dt

from flask import Flask, render_template, session, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from data_handler import DataHandler
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
    timestamp = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    rate = db.Column(db.Float, nullable=False)

class EURUSD(db.Model):
    __tablename__ = 'eurusd'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    rate = db.Column(db.Float, nullable=False)

class GBPUSD(db.Model):
    __tablename__ = 'gbpusd'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    rate = db.Column(db.Float, nullable=False)

class NZDUSD(db.Model):
    __tablename__ = 'nzdusd'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    rate = db.Column(db.Float, nullable=False)

class USDCAD(db.Model):
    __tablename__ = 'usdcad'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    rate = db.Column(db.Float, nullable=False)

class USDCHF(db.Model):
    __tablename__ = 'usdchf'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    rate = db.Column(db.Float, nullable=False)

class USDJPY(db.Model):
    __tablename__ = 'usdjpy'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    rate = db.Column(db.Float, nullable=False)

tables = [AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY]
data_handler = DataHandler(tables, db)

# @app.before_first_request
# def load_ticks():
#     data_handler.load_ticks()

@app.route('/', methods=["GET","POST"])
def index():
    cps = {
        table.__tablename__: title_dict[table.__tablename__]
        for table in tables
    }
    return render_template('stream.html', currency_pairs=cps)

@app.route('/data', methods=['GET','POST'])
def data():
    # load_ticks will check db for latest date
    # then ask cgapi for ticks after that time stamp
    # irl database could be getting loaded all the time, but for this purpose only get data when someone is looking at it
    # how about if two people are using the app , you now have two scrapers running.. it only makes sense as a demo
    data_handler.load_ticks()
    response = data_handler.build_response()
    return jsonify(response)
'''
@app.route('/risk')
def risk():
    return render_template('risk.html', risk=True)

@app.route('/returns')
def returns():
    return render_template('returns.html', returns=True)
'''
