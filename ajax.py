import os
import datetime as dt

from flask import Flask, jsonify, make_response, request
from flask_sqlalchemy import SQLAlchemy
import numpy as np

from bokeh.models import AjaxDataSource, CustomJS
from bokeh.plotting import figure, show

class AjaxBokeh():
    def __init__(self):
        u, p = os.getenv('uname'), os.getenv('upass')
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] =\
        f'postgresql://{u}:{p}@localhost:5432/forexticks'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.secret_key = os.urandom(16).hex()

        db = SQLAlchemy(self.app)

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


        adapter = CustomJS(
            code=\
            """
                const result = {x: [], y: []}
                const {points} = cb_data.response
                for (const [x, y] of points) {
                    result.x.push(x)
                    result.y.push(y)
                    }
                return result
            """
        )

        source = AjaxDataSource(
            data_url='http://localhost:5050/data',
            polling_interval=1000,
            adapter=adapter
        )

        self.p = figure(
            plot_height=250,
            plot_width=1150,
            title="AUDUSD",
            x_axis_type='datetime'
        )

        table = tables[0]
        row = table.query.order_by(table.timestamp.desc()).first()

        self.x = [0]
        self.y = [row.rate]

        self.p.circle('x', 'y', source=source)

        self.p.x_range.follow = "end"
        self.p.x_range.follow_interval = 1000

        # Flask related code

        def crossdomain(f):
            def wrapped_function(*args, **kwargs):
                resp = make_response(f(*args, **kwargs))
                h = resp.headers
                h['Access-Control-Allow-Origin'] = '*'
                h['Access-Control-Allow-Methods'] = "GET, OPTIONS, POST"
                h['Access-Control-Max-Age'] = str(21600)
                requested_headers = request.headers.get(
                    'Access-Control-Request-Headers'
                )
                if requested_headers:
                    h['Access-Control-Allow-Headers'] = requested_headers
                return resp
            return wrapped_function

        @self.app.route('/data', methods=['GET', 'OPTIONS', 'POST'])
        @crossdomain
        def data():
            table = tables[0]
            row = table.query.order_by(table.timestamp.desc()).first()
            # self.x.append(row.timestamp.timestamp())
            self.y.append(row.rate)
            self.x.append(self.x[-1]+0.1)
            # self.y.append(np.sin(self.x[-1])+np.random.random())
            return jsonify(points=list(zip(self.x,self.y)))

    def run(self):
        self.app.run(port=5050)
