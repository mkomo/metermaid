#!/usr/bin/env python3

import sys
import os
import json
import math
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import argparse

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

def update_annot(annot, ind, sc):

    pos = sc.get_offsets()[ind["ind"][0]]
    print(str(sc))
    annot.xy = pos
    print(" ".join(list(map(str,ind["ind"]))))
    text = "{}".format(" ".join(list(map(str,ind["ind"]))))
    annot.set_text(text)
    # annot.get_bbox_patch().set_facecolor(cmap(norm(c[ind["ind"][0]])))
    annot.get_bbox_patch().set_alpha(0.4)


def hover(annot, fig, ax, plots):
  def h(event):
    vis = annot.get_visible()
    if event.inaxes == ax:
      for sc in plots:
        cont, ind = sc.contains(event)
        if cont:
          update_annot(annot, ind, sc)
          annot.set_visible(True)
          fig.canvas.draw_idle()
          return
      if vis:
        annot.set_visible(False)
        fig.canvas.draw_idle()
  return h

def process_file(file, options={}):
  temps = []
  cfs = []
  hours = []
  timestamps = []
  hourcats = []
  for line in file:
    entry = json.loads(line)
    cfs.append(entry['cf'])
    temps.append(entry['temp'])
    hours.append(entry['hour'])
    timestamps.append(datetime.fromisoformat(entry['utcdatetime']))
    hour = int(entry['hour'][11:13])
    if hour in range(7,21,1):
      hourcat = 'daytime'
    elif hour in [5,6]:
      hourcat = 'AM'
    elif hour in [21,22]:
      hourcat = 'PM'
    else:
      hourcat = 'overnight'

    hourcat = 'AM' if hour in [5,6] else ('PM' if hour in [21, 22] else 'normal')
    print(hour, hourcat)
    hourcats.append(hourcat)

  if options.get('action') == 'scatter':
    scatter(hours, temps, cfs, hourcats)
  elif options.get('action') == 'ts':
    ts(timestamps, temps, cfs)

def ts(timestamps, temps, cfs):

  # plt.plot(timestamps, cfs, ds="steps-pre")
  # ax = plt.gca()

  # scale = 1.5
  # f = zoom_factory(ax,base_scale = scale)

  # plt.show()

  hdds = [max(0,65 - t) for t in temps]
  cfphdd = [(0 if hdd < 1 else 24*cf/hdd) for cf,hdd in zip(cfs,hdds)]

  fig, ax1 = plt.subplots()

  ax1.set_xlabel('date')

  color = 'red'
  ax1.set_ylabel('HDD', color=color)
  ax1.plot(timestamps, hdds, color=color)
  ax1.tick_params(axis='y', labelcolor=color)

  # ax2 = ax1.twinx()
  # color = 'blue'
  # ax2.set_ylabel('cf/h', color=color)
  # ax2.plot(timestamps, cfs, color=color)
  # ax2.tick_params(axis='y', labelcolor=color)

  ax3 = ax1.twinx()
  color = 'green'
  ax3.set_ylabel('cf/hdd', color=color)
  ax3.plot(timestamps, cfphdd, color=color)
  ax3.tick_params(axis='y', labelcolor=color)

  scale = 1.5
  f = zoom_factory(plt.gca(),base_scale = scale)

  plt.show()

def scatter(hours, temps, cfs, hourcats):
  df = pd.DataFrame({'x': temps,
                   'y': cfs,
                   'z': hourcats,
                   'h': hours})
  groups = df.groupby('z')

  fig, ax = plt.subplots()
  plots = []

  ax.set_ylabel('cf of ng')
  ax.set_xlabel('outside temp')

  for name, group in groups:
    plots.append(ax.scatter(group.x, group.y, marker='o', s=10, label=name))

    # annotate
    # print(list(key for key in group.h))
    # print(group.h)
    # print(group.h.index)
    for i, txt in zip(group.h.index, group.h):
      # print(i, txt, group.x[i], group.y[i])
      # plt.annotate(txt, (group.x[i], group.y[i]))
      pass


  # annot = ax.annotate("", xy=(0,0), xytext=(20,20),textcoords="offset points",
  #                     bbox=dict(boxstyle="round", fc="w"),
  #                     arrowprops=dict(arrowstyle="->"))
  # annot.set_visible(False)
  # fig.canvas.mpl_connect("motion_notify_event", hover(annot, fig, ax, plots))

  ax.legend()
  ax.set_ylim([0, None])


  scale = 1.5
  f = zoom_factory(ax,base_scale = scale)


  plt.show()


def main(argv):

  parser = argparse.ArgumentParser(
    prog = __file__,
    description = 'graph aggregated hourly gas meter data'
  )
  parser.add_argument('action', choices=['scatter', 'ts'])
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
