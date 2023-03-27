#!/usr/bin/env python3

import sys
import os
import json
import math
from datetime import datetime
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

def get_thermostat_temps(thermostat_file):
  temps = dict()
  for line in thermostat_file:
    d = json.loads(line)
    if 'devices' in d['response_body']:
      for i,dev in enumerate(d['response_body']['devices']):
        if i not in temps:
          temps[i] = {'temp':[], 'time':[], 'is_heating': []}
        temps[i].get('time').append(datetime.fromtimestamp(d['timestamp']))
        temps[i].get('temp').append(dev['traits']["sdm.devices.traits.Temperature"]['ambientTemperatureCelsius'] * 9/5 + 32)
        # temps[i].get('is_heating').append()

  return temps

def process_file(file, options={}):
  rate_times = []
  rate_vals = []
  thermostat_temps = None if not options.get('thermostat') else get_thermostat_temps(open(options.get('thermostat')))

  for line in file:
    diff = json.loads(line)
    rate_vals.append(diff['rate'])
    rate_times.append(datetime.fromtimestamp(diff['timestamp']))

  fig, ax1 = plt.subplots()

  ax1.set_xlabel('date')

  color = 'blue'
  ax1.set_ylabel('CF', color=color)
  ax1.plot(rate_times, rate_vals, color=color, ds="steps-pre")
  ax1.tick_params(axis='y', labelcolor=color)

  if thermostat_temps is not None:
    ax2 = ax1.twinx()
    color = 'green'
    ax2.set_ylabel('thermostat temp', color=color)
    ax2.plot(thermostat_temps[1]['time'], thermostat_temps[1]['temp'], color=color)
    ax2.plot(thermostat_temps[0]['time'], thermostat_temps[0]['temp'], color='red')
    ax2.tick_params(axis='y', labelcolor=color)

  scale = 1.5
  f = zoom_factory(plt.gca(),base_scale = scale)

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
  parser.add_argument('filename', nargs='+') # positional argument
  parser.add_argument('--thermostat')
  parser.add_argument('-d', '--debug', action='store_true')   # on/off flag

  args = parser.parse_args()

  global DEBUG
  if args.debug:
    DEBUG = True




  for filename in args.filename:
    if not os.path.exists(filename):
      printerr('could not find file: {}'.format(filename))
      printerr()
      printerr(parser.format_help())
      sys.exit(1)
    #TODO handle multiple files
    process_file(open(filename), vars(args))

if __name__ == '__main__':
  main(sys.argv[1:])
