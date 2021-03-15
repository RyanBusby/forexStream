import json
import datetime as dt
from datetime import timedelta, timezone
from dateutil.relativedelta import relativedelta, FR

from bokeh.plotting import figure
from bokeh.embed import components, json_item
from bokeh.models import ColumnDataSource, Label, Panel, Tabs, HoverTool, Span, CrosshairTool, formatters

class BPBuilder():
    def __init__(self, tables, minutes=30):
        self.tables = tables
        self.minutes = minutes

    def closed(self, now):
        # this is specific to mst.. fix to work anywhere dateutil prolly
        # make this shared by DataHandler
    	return (
        	(now.weekday() == 4 and now.time() >= dt.time(21,1))\
        	| (now.weekday() == 5) \
        	| (now.weekday() == 6 and now.time() < dt.time(21))
        )

    def build_response(self, is_closed):
        response = {}
        cutoff = dt.datetime.now() - timedelta(minutes=self.minutes)
        for table in self.tables:
            tname = table.__tablename__
            rows = table.query\
                .filter(table.timestamp > cutoff)\
                .order_by(table.timestamp)\
                .all()
            plot, delta, last_val, increasing = self.get_plot(rows)
            response[tname] = {
                'data': json.dumps(json_item(plot, tname)),
                'last_val': last_val,
                'delta': delta,
                'increasing': increasing
            }
        response['closed'] = is_closed
        response['choice'] = 'bokeh'
        return response


    def get_plot(self, rows):
        hover_tool = HoverTool(
            tooltips=[
            # https://docs.bokeh.org/en/latest/docs/reference/models/formatters.html#bokeh.models.formatters.DatetimeTickFormatter
                ('timestamp', '@{timestamp}{%d %b %Y %l:%M:%S:%N %P}'),
                ('rate', '@{rate}{%0.4f}'),
                # ('timestamp', '@{bardate}{%c}'), #preferred datetime
            ],
            formatters={
                '@{timestamp}': 'datetime',
                '@{rate}': 'printf'
            }
        )
        times = []
        rates = []
        for row in rows:
            # convert to utc here. bokeh is iffy with time zones
            utc_ts =\
            dt.datetime.utcfromtimestamp(row.timestamp.timestamp())
            times.append(utc_ts)
            rates.append(row.rate)

        plot_data = {'timestamp': times, 'rate': rates}
        first_val = plot_data['rate'][0]
        last_val = plot_data['rate'][-1]
        delta = abs(round(last_val - first_val, 5))
        increasing = last_val > first_val
        if delta >= 0:
            color = 'green'
        else:
            color = 'red'
        source = ColumnDataSource(data=plot_data)
        plot = figure(
            plot_width=1150,
            plot_height=250,
            x_axis_type='datetime'
        )
        plot.line(
            x='timestamp',
            y='rate',
            source=source,
            color=color
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
        plot.add_tools(hover_tool)
        return plot, delta, last_val, increasing

    def get_plots(self):
        now = dt.datetime.now(tz=timezone.utc).replace(microsecond=0)
        is_closed = self.closed(now)
        if is_closed:
            m = int(59 - self.minutes)
            cutoff = (now + relativedelta(weekday=FR(-1)))\
                .replace(hour=14, minute=m, second=55)
        else:
            cutoff = now - timedelta(minutes=self.minutes)
        plots = {}
        hover_tool = HoverTool(
            tooltips=[
            # https://docs.bokeh.org/en/latest/docs/reference/models/formatters.html#bokeh.models.formatters.DatetimeTickFormatter
                ('timestamp', '@{timestamp}{%d %b %Y %l:%M:%S:%N %P}'),
                ('rate', '@{rate}{%0.4f}'),
                # ('timestamp', '@{bardate}{%c}'), #preferred datetime
            ],
            formatters={
                '@{timestamp}': 'datetime',
                '@{rate}': 'printf'
            }
        )
        crosshair_tool = CrosshairTool(
            dimensions='width',
            line_color='blue'
        )
        deltas = {}
        current_rates = {}
        for table in self.tables:
            tname = table.__tablename__
            rows = table.query\
                .filter(table.timestamp > cutoff)\
                .order_by(table.timestamp)\
                .all()
            times = []
            rates = []
            for row in rows:
                # convert to utc here. bokeh is iffy with time zones
                utc_ts =\
                dt.datetime.utcfromtimestamp(row.timestamp.timestamp())
                times.append(utc_ts)
                rates.append(row.rate)

            plot_data = {'timestamp': times, 'rate': rates}
            delta = plot_data['rate'][-1]-plot_data['rate'][0]
            if delta >= 0:
                color = 'green'
            else:
                color = 'red'
            source = ColumnDataSource(data=plot_data)
            plot = figure(
                plot_width=1150,
                plot_height=250,
                x_axis_type='datetime'
            )
            plot.line(
                x='timestamp',
                y='rate',
                source=source,
                color=color
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
            plot.add_tools(hover_tool)
            plots[tname] = plot
            deltas[tname] = delta
            current_rates[tname] = plot_data['rate'][-1]

        script, divs = components(plots)
        return script, divs, deltas, current_rates
