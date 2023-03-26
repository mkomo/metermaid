#!/usr/bin/env python3

import sys
import os
import json
import math
from datetime import datetime
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


def process_file(file):
  rate_times = []
  rate_vals = []
  for line in file:
    diff = json.loads(line)
    rate_vals.append(diff['rate'])
    rate_times.append(datetime.fromtimestamp(diff['timestamp']))

  plt.plot(rate_times, rate_vals, ds="steps-pre")
  # plt.scatter(rate_times, rate_vals, c ="blue", s=1)
  ax = plt.gca()
  ax.set_ylim([0, None])

  # ax.plot(range(10))
  scale = 1.5
  f = zoom_factory(ax,base_scale = scale)

  plt.show()


def main(argv):

  filename = argv[0] if len(argv) > 0 else ""

  if not os.path.exists(filename):
    print("Usage: python3 graph_rates.py <rates.ndjson>")
    sys.exit(1)

  file = open(filename, 'r')

  process_file(file)

if __name__ == '__main__':
  main(sys.argv[1:])
