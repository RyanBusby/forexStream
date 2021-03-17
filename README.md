# Streaming Forex Data

### Flask, Bootstrap, HighCharts, & Bokeh to display live forex data

![](md_files/screenshot.png)


create a db called forexticks and enter database uri in config.py. then run the following command

```$ flask db migrate```

app.py creates threads - one for the scraper and another to run the application, in order for that to work FLASK_DEBUG must be false.

```$ export FLASK_DEBUG=0```

Acquire an API key thru forex.com and put the credentials in the \_\_init__ of CGScraper
