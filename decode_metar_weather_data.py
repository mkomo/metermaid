#!/usr/bin/env python3

import sys
import os
import json
import math
from datetime import datetime
import pytz
from metar import Metar
import argparse


import matplotlib.pyplot as plt

def zoom_factory(ax,base_scale = 2.):
  def zoom_fun(event):
    cur_xlim = ax.get_xlim()
    xdata = event.xdata
    if event.button == 'down':
      scale_factor = 1/base_scale
    elif event.button == 'up':
      scale_factor = base_scale
    ax.set_xlim([xdata - (xdata - cur_xlim[0])*scale_factor,
                 xdata - (xdata - cur_xlim[1])*scale_factor])
    plt.draw()

  fig = ax.get_figure()
  fig.canvas.mpl_connect('scroll_event',zoom_fun)

  return zoom_fun


def process_file(file, options={}):
  rate_times = []
  rate_vals = []
  previous_time = None
  previous_hour_temp = None

  for line in file:
    weather_entry = json.loads(line)
    if weather_entry['REPORT_TYPE'] == 'FM-15' and 'REM' in weather_entry:
      rem = weather_entry['REM']
      debug()
      debug('The DATE is:       {}'.format(weather_entry['DATE']))
      date = datetime.strptime(weather_entry['DATE'], "%Y-%m-%dT%H:%M:%S")

      if previous_time == None or (date - previous_time).total_seconds() > 3600:
        printerr('prev and current', previous_time, date)
        previous_hour_temp = None
      previous_time=date

      # date = date.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(date))
      debug('The timezone is:   {}'.format(date.astimezone()))
      date = pytz.utc.localize(date).astimezone(pytz.timezone('America/New_York'))
      # date = pytz.timezone('America/New_York').localize(date)
      debug('The local date is: {}'.format(date))
      debug('The rem is: {}'.format(rem))
      metar_data = ' '.join(rem.split(' ')[2:])
      debug('The metar_data is: {}'.format(metar_data))
      metar_object = Metar.Metar(metar_data, date.month, date.year, strict=False)
      debug('%s' % metar_object.string())
      if metar_object.temp is not None:
        debug('temperature:    %s' % metar_object.temp)

        if options.get('action') == 'ndjson':
          try:
            print(json.dumps({
              'utcdatetime': weather_entry['DATE'],
              'hour': datetime.strftime(date, '%Y-%m-%dT%H%Z'),
              'temp': None if metar_object.temp is None else metar_object.temp.value("F"),
              'temp_previous_hour': None if previous_hour_temp is None else previous_hour_temp.value("F"),
              'dewpt': metar_object.dewpt.value("F"),
              # 'weather': metar_object.weather,
              'wind_speed': None if metar_object.wind_speed is None else metar_object.wind_speed.value("MPH"),
              'wind_gust': None if metar_object.wind_gust is None else metar_object.wind_speed.value("MPH")
            }))
          except Exception as e:
            printerr(e)
        else:
          rate_vals.append(metar_object.temp.value("F"))
          rate_times.append(date)

      previous_hour_temp = metar_object.temp
  if options.get('action') == 'graph':
    plt.plot(rate_times, rate_vals, ds="steps-pre")
    ax = plt.gca()

    scale = 1.5
    f = zoom_factory(ax,base_scale = scale)

    plt.show()

DEBUG = False

def debug(*args, **kwargs):
  if DEBUG:
    printerr(*args, **kwargs)

def printerr(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def main(argv):
  parser = argparse.ArgumentParser(
    prog = __file__,
    description = 'Read an image of a gas meter'
  )
  parser.add_argument('action', choices=['ndjson', 'graph', 'debug'])
  parser.add_argument('filename', nargs='+') # positional argument
  parser.add_argument('-d', '--debug', action='store_true')   # on/off flag

  args = parser.parse_args()

  global DEBUG
  if args.debug:
    DEBUG = True
    # pass

  for filename in args.filename:
    if not os.path.exists(filename):
      printerr('could not find file: {}'.format(filename))
      printerr()
      printerr(parser.format_help())
      sys.exit(1)
    process_file(open(filename), vars(args))


if __name__ == '__main__':
    main(sys.argv[1:])