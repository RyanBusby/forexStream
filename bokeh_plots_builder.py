import json
import datetime as dt
from datetime import timedelta, timezone
from dateutil.relativedelta import relativedelta, FR

import numpy as np
import pandas as pd
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import AjaxDataSource, ColumnDataSource, HoverTool, CrosshairTool, formatters, CustomJS, DateRangeSlider
from bokeh.layouts import column

from market_dicts import title_dict

class BPBuilder():
	def __init__(self, tables, ohlc_tables, db, minutes=30):
		self.tables = tables
		self.minutes = minutes
		self.ohlc_tables = ohlc_tables
		self.db = db

	def build_ohlc_components(self):
		'''

		'''
		plot_dict = {}
		for table in self.ohlc_tables:
			tname = table.__tablename__
			cp = tname[:6]

			# the date slider is a little glitchy.
			# better with less data

			# df = pd.read_sql_table(
			# 	tname,
			# 	self.db.engine,
			# 	columns=['timestamp','open', 'high','low','close']
			# )

			sql =\
			f"""select * from {tname} where timestamp > '1/1/2019'"""
			df = pd.read_sql(
				sql,
				self.db.engine,
				columns=['timestamp','open', 'high','low','close']
			)

			df.set_index('timestamp', drop=True, inplace=True)
			df['open_inc'],df['high_inc'],df['low_inc'],df['close_inc']=\
			df['open'],    df['high'],    df['low'],    df['close']
			df['open_dec'],df['high_dec'],df['low_dec'],df['close_dec']=\
			df['open'],    df['high'],    df['low'],    df['close']

			inc = df.close > df.open
			dec = df.open > df.close

			df['open_dec'][inc]=None
			df['high_dec'][inc]=None
			df['low_dec'][inc]=None
			df['close_dec'][inc]=None

			df['open_inc'][dec]=None
			df['high_inc'][dec]=None
			df['low_inc'][dec]=None
			df['close_inc'][dec]=None

			source = ColumnDataSource(data=df)
			reference = ColumnDataSource(data=df)

			plot = figure(
				x_axis_type="datetime",
				plot_height=300,
				plot_width=1300,
				title=title_dict[cp]
			)
			seg = plot.segment(
				x0='timestamp',
				y0='high',
				x1='timestamp',
				y1='low',
				color='black',
				source=source
			)
			inc_bar = plot.vbar(
				x='timestamp',
				width=20*60*60*1000,
				top='close_inc',
				bottom='open_inc',
				fill_color="#D5E1DD",
				line_color="black",
				source=source
			)
			dec_bar = plot.vbar(
				x='timestamp',
				width=20*60*60*1000,
				top='open_dec',
				bottom='close_dec',
				fill_color="#F2583E",
				line_color="black",
				source=source
			)

			date_range_slider = DateRangeSlider(
				value=(
					df.index.min().date(),
					df.index.max().date()
				),
				start=df.index.min().date(),
				end=df.index.max().date(),
				# background='#f8f9fa',
				# bar_color='#f8f9fa',
				css_classes=['font-weight-lighter','bg-light'],
				step=86400000
			)

			args = dict(
				source=source,
				reference=reference
			)
			code =\
			"""
			const data = source.data;
			const data_ref = reference.data;

			const from_date = this.value[0];
			const to_date = this.value[1];

			var from_pos = data_ref['timestamp'].indexOf(to_date);
			var to_pos = data_ref['timestamp'].indexOf(from_date);

			if (from_pos == -1) {
			// ADD TWO DAYS TO 'FROM' IF SLIDER LANDS ON SAT OR SUN
			var from_pos = data_ref['timestamp'].indexOf(to_date+48*60*60*1000);
			} else if (to_pos == -1) {
			// SUBTRACT TWO DAYS FROM 'TO' IF SLIDER LANDS ON SAT OR SUN
			var to_pos = data_ref['timestamp'].indexOf(to_date-48*60*60*1000);
			}

			data['timestamp'] = data_ref['timestamp'].slice(to_pos,from_pos);

			data['high'] = data_ref['high'].slice(to_pos,from_pos);
			data['low'] = data_ref['low'].slice(to_pos,from_pos);

			data['open_inc'] = data_ref['open_inc'].slice(to_pos,from_pos);
			data['high_inc'] = data_ref['high_inc'].slice(to_pos,from_pos);
			data['low_inc'] = data_ref['low_inc'].slice(to_pos,from_pos);
			data['close_inc'] = data_ref['close_inc'].slice(to_pos,from_pos);

			data['open_dec'] = data_ref['open_dec'].slice(to_pos,from_pos);
			data['high_dec'] = data_ref['high_dec'].slice(to_pos,from_pos);
			data['low_dec'] = data_ref['low_dec'].slice(to_pos,from_pos);
			data['close_dec'] = data_ref['close_dec'].slice(to_pos,from_pos);

			source.change.emit();
			"""
			callback = CustomJS(args=args, code=code)

			date_range_slider.js_on_change("value", callback)

			hover_tool = HoverTool(
				tooltips=[
				# https://docs.bokeh.org/en/latest/docs/reference/models/formatters.html#bokeh.models.formatters.DatetimeTickFormatter
					('timestamp', '@{timestamp}{%x}'),
					('open', '@{open}{%0.4f}'),
					('high', '@{high}{%0.4f}'),
					('low', '@{low}{%0.4f}'),
					('close', '@{close}{%0.4f}')
				],
				formatters={
					'@{timestamp}': 'datetime',
					'@{open}': 'printf',
					'@{high}': 'printf',
					'@{low}': 'printf',
					'@{close}': 'printf'

				},
				renderers=[seg]
			)
			crosshair_tool = CrosshairTool(
				dimensions='width',
				line_color='blue'
			)
			plot.add_tools(crosshair_tool)
			plot.add_tools(hover_tool)
			plot.background_fill_color = '#f8f9fa'
			# plot.background_fill_color = '#868e96'
			plot_dict[cp] = column(date_range_slider, plot)


		return components(plot_dict)


	def build_components(self):
		plot_dict = {}
		for table in self.tables:
			cp = table.__tablename__
			url =f"http://localhost:5000/ajax_data/{cp}/{self.minutes}"
			source = AjaxDataSource(
				data_url=url,
				polling_interval=1000,
				mode='replace'
			)

			plot = figure(
				plot_height=250,
				plot_width=1000,
				x_axis_type='datetime'
			)

			plot.xaxis.formatter = formatters.DatetimeTickFormatter(
				days="%m/%d",
				hours = "%l:%M %P",
				hourmin = "%l:%M %P",
				minutes="%l:%M %P",
				minsec="%l:%M:%S %P",
				seconds="%l:%M:%S %P",
				microseconds="%l:%M:%S:%f %P",
				milliseconds="%l:%M:%S:%f %P"

			)
			plot.xaxis.axis_label = "UTC"

			line = plot.line(
				'timestamp',
				'rate',
				source=source
			)
			plot.background_fill_color = '#f8f9fa'

			hover_tool = HoverTool(
				tooltips=[
				# https://docs.bokeh.org/en/latest/docs/reference/models/formatters.html#bokeh.models.formatters.DatetimeTickFormatter
					('timestamp', '@{timestamp}{%d %b %Y %l:%M:%S:%N %P}'),
					('rate', '@{rate}{%0.4f}'),
				],
				formatters={
					'@{timestamp}': 'datetime',
					'@{rate}': 'printf'
				}
			)


			callback = CustomJS(
				args={'line':line, 'source':source, 'cp':cp}, code="""
				var rates = source.data.rate;
				var first_val = rates[0];
				var last_val = rates[rates.length-1];
				var delta = Number.parseFloat(Math.abs(last_val-first_val)).toFixed(5);
				var increasing = first_val < last_val;
				if (increasing) {
					line.glyph.line_color = 'green';
				} else {
					line.glyph.line_color = 'red';
				}
						var card_class_dict = {
						true: {
						  "card_class":"card-text text-center font-weight-lighter text-success",
						  "new_color": "green",
						  "arrow": "▲"
						},
						false: {
						  "card_class":"card-text text-center font-weight-lighter text-danger",
						  "new_color": "red",
						  "arrow": "▼"
						  }
						}
						var formats = card_class_dict[increasing];

						$('#delta_'+cp)
						.removeClass()
						.addClass(
							  formats['card_class']
						)
						.html(
							formats["arrow"].concat(delta)
						);
						$('#current_'+cp).html(last_val);

				"""
			)
			source.js_on_change('change:data', callback)
			plot_dict[cp] = plot
		return components(plot_dict)
