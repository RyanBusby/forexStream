from datetime import datetime as dt
from datetime import timedelta
from dateutil.relativedelta import relativedelta, FR

from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import ColumnDataSource, Label, Panel, Tabs, HoverTool, Span, CrosshairTool, formatters

class BokehPlots():
    # load ticks from this view as well
    def __init__(self, tables, minutes=30):
        self.tables=tables
        self.minutes = minutes

    def closed(self, now):
        # this is specific to mst.. fix to work anywhere dateutil prolly
        # make this shared by DataHandler
    	return (
        	(now.weekday() == 4 and now.time() >= dt.time(21,1))\
        	| (now.weekday() == 5) \
        	| (now.weekday() == 6 and now.time() < dt.time(21))
        )

    def get_plots(self):
        now = dt.now().replace(microsecond=0)
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
                ('timestamp', '@{timestamp}{%d %b %Y %l:%M %p}'),
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
                times.append(row.timestamp)
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
                hours="%H",
                minutes="%l:%M %P"
            )
            plot.add_tools(hover_tool)
            plots[tname] = plot
            deltas[tname] = delta
            current_rates[tname] = plot_data['rate'][-1]

        script, divs = components(plots)
        return script, divs, deltas, current_rates
