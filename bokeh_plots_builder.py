import json
import datetime as dt
from datetime import timedelta, timezone
from dateutil.relativedelta import relativedelta, FR
from bokeh.palettes import Purples
from bokeh.plotting import figure
from bokeh.themes import built_in_themes
from bokeh.embed import components, json_item
from bokeh.models import AjaxDataSource, Label, Panel, Tabs, HoverTool, Span, CrosshairTool, formatters, CustomJS

class BPBuilder():
    def __init__(self, tables, minutes=30):
        self.tables = tables
        self.minutes = minutes

    def build_components(self):
        plot_dict = {}
        for table in self.tables:
            name = table.__tablename__
            url =f"http://localhost:5000/ajax_data/{name}/{self.minutes}"
            source = AjaxDataSource(
                data_url=url,
                polling_interval=1000,
                mode='replace'
            )

            plot = figure(
                title=name.upper(),
                plot_height=250,
                plot_width=1150,
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
            # use multi_line to set color
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
            plot.add_tools(hover_tool)

            callback = CustomJS(
                args={'line':line, 'source':source, 'cp':name}, code="""
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
            plot_dict[name] = plot
        return components(plot_dict)
