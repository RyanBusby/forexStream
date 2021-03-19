import json
import datetime as dt
from datetime import timedelta, timezone
from dateutil.relativedelta import relativedelta, FR

import numpy as np
import pandas as pd
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import AjaxDataSource, ColumnDataSource, HoverTool, CrosshairTool, formatters, CustomJS, DateRangeSlider, Plot,  Grid, LinearAxis, MultiLine
from bokeh.layouts import column

from market_dicts import title_dict, price_types

class BPBuilder():
	def __init__(self, tables, ohlc_tables, db, minutes=30):
		self.tables = tables
		self.minutes = minutes
		self.ohlc_tables = ohlc_tables
		self.db = db

		self.TOOLS = "pan,box_zoom,reset"

	def build_returns_components(self):
		# xs, ys, color, label = [], [], [], []
		colors = [
			'#2f7ed8', '#0d233a', '#8bbc21', '#910000', '#1aadce',\
			'#492970', '#f28f43', '#77a1e5', '#c42525', '#a6c96a'
		]

		plot = figure(
			plot_height=500,
			plot_width=1250,
			x_axis_type='datetime',
			toolbar_location="above",
			tools=self.TOOLS,
			title='Daily Returns Going Back 3 Years'
		)
		for i, table in enumerate(self.ohlc_tables):
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
			cols = ['timestamp', 'close']
			df = pd.read_sql_table(cp, self.db.engine, columns=cols)\
				.set_index('timestamp', drop=True)
			three_years_ago = dt.datetime.now() - timedelta(days=365*3)
			df = df[df.index >= three_years_ago] # include range selector
			df.drop_duplicates(inplace=True)
			df = df.pct_change(period)
			df['close'] = df['close']*100
			df.dropna(inplace=True)
			x = (
				np.array(
					df.index.values.tolist()
				) / 1000000
			).astype(int).tolist()
			y = df.close.values.tolist()
			plot.line(
				x,
				y,
				line_color=colors[i],
				legend_label=cp[:6].upper()
			)
		plot.legend.location = "top_left"
		plot.legend.click_policy="hide"
		plot.title.text_color = "#f8f9fa"
		plot.background_fill_color = '#f8f9fa'
		plot.border_fill_color = "#343a40"
		plot.xaxis.axis_label_text_color = "#868e96"
		plot.yaxis.axis_label_text_color = "#868e96"
		plot.xaxis.major_label_text_color = "#868e96"
		plot.yaxis.major_label_text_color = "#868e96"
		plot.xgrid.visible=False
		return components(plot)


	def build_ohlc_components(self):
		plot_dict = {}
		for table in self.ohlc_tables:
			tname = table.__tablename__
			cp = tname[:6]

			df = pd.read_sql_table(
				tname,
				self.db.engine,
				columns=['timestamp','open', 'high','low','close']
			)
			df.drop_duplicates(inplace=True)
			r = pd.date_range(
				start=df.timestamp.min(), end=df.timestamp.max()
			)
			df = df.set_index('timestamp').reindex(r).fillna(np.NaN)
			df.index = df.index.rename('timestamp')

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
				plot_height=250,
				plot_width=1400,
				toolbar_location="above",
				tools=self.TOOLS,
				# these didn't do much
				# sizing_mode='stretch_width',
				# sizing_mode='stretch_height',
				# sizing_mode='stretch_both',
				# sizing_mode='scale_width',
				# sizing_mode='scale_height',
				# sizing_mode='scale_both',
				# sizing_mode='fixed',
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
				# width=400,
				align='center',
				margin=(25,50,5,50),
				# format="%x",
				format="%B %e, %Y",
				value=(
					df.index.min(),
					df.index.max()
				),
				start=df.index.min(),
				end=df.index.max(),
				background='#343a40',
				bar_color='#f8f9fa',
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

			# NaN's sometimes show up in hover tool
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
				renderers=[inc_bar,dec_bar]
			)
			plot.add_tools(hover_tool)
			plot.background_fill_color = '#f8f9fa'
			plot.border_fill_color = "#343a40"
			plot.title.text_color = "#f8f9fa"
			plot.xaxis.axis_label_text_color = "#f8f9fa"
			plot.yaxis.axis_label_text_color = "#f8f9fa"
			plot.xaxis.major_label_text_color = "#f8f9fa"
			plot.yaxis.major_label_text_color = "#f8f9fa"
			plot.xgrid.visible = False
			plot.xaxis.formatter = formatters.DatetimeTickFormatter(
				days="%m/%d/%Y",
				months = "%m/%d/%Y"
			)
			# plot.background_fill_color = '#868e96'
			plot_dict[cp] = column(plot, date_range_slider)


		return components(plot_dict)


	def build_components(self):
		plot_dict = {}
		for table in self.tables:
			cp = table.__tablename__
			url =f"http://localhost:5000/data/{cp}/{self.minutes}"
			source = AjaxDataSource(
				data_url=url,
				polling_interval=1000,
				mode='replace'
			)

			plot = figure(
				plot_height=150,
				plot_width=1200,
				x_axis_type='datetime',
				toolbar_location="above",
				tools=self.TOOLS,
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
			# plot.xaxis.axis_label = "UTC"

			line = plot.line(
				'timestamp',
				'rate',
				source=source
			)
			plot.background_fill_color = '#f8f9fa'
			plot.border_fill_color = "#343a40"
			plot.xaxis.axis_label_text_color = "#868e96"
			plot.yaxis.axis_label_text_color = "#868e96"
			plot.xaxis.major_label_text_color = "#868e96"
			plot.yaxis.major_label_text_color = "#868e96"
			plot.xgrid.visible=False

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
			plot.add_tools(hover_tool)
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
