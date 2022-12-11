#!/usr/bin/env python3

import sys
import os
import json
import math
from datetime import datetime

# there might be noise in readings. If a dial jumps back more than this fraction, assume it has completed a full revolution
MAX_JITTER = 0.5

def read_test_delta(last, entry, dial):
  if dial not in entry['test'] or dial not in last['test']:
    return 0
  return entry['test'][dial] - last['test'][dial]

def get_delta(val, last, dial_unit_string):
  dial_unit = 10 * float(dial_unit_string)
  delta = val - last

  # correct for turnover from max to 0
  if delta < -1 * MAX_JITTER * dial_unit:
    # correct for turnover from max to 0
    delta = delta + dial_unit
  elif delta > MAX_JITTER * dial_unit:
    # jitter'd back to below zero from above zero
    delta = delta - dial_unit

  return delta

def get_diff(entry, last_diff, dial_to_check):
  if dial_to_check in entry['test']:
      val = entry['test'][dial_to_check]
      timestamp = datetime.strptime(entry['date'], "%Y-%m-%d %H:%M:%S").timestamp()
      if last_diff is not None:
        delta = get_delta(val, last_diff['val'], dial_to_check)
        if delta > 0:
          delta_time = timestamp - last_diff['timestamp']
          diff = {
            'reading': entry['reading'],
            'val': val,
            'delta': delta,
            'delta_time': delta_time,
            'delta_reading': entry['reading'] - last_diff['reading'],
            'rate': delta/delta_time,
            'date': entry['date'],
            'timestamp': timestamp
          }
          print(json.dumps(diff))
          return diff
      else:
        # this line is the first entry in the input
        return {
          'val': val,
          'reading': entry['reading'],
          'timestamp': timestamp
        }

def process_file(file):
  last_diff = None
  for line in file:
    entry = json.loads(line)
    dial_to_check = '0.2'
    diff = get_diff(entry, last_diff, dial_to_check)
    if diff is not None:
      last_diff = diff



def main(argv):

  filename = argv[0] if len(argv) > 0 else ""

  if not os.path.exists(filename):
    print("Usage: python3 process_series.py <series.ndjson>")
    sys.exit(1)

  file = open(filename, 'r')

  try:
    process_file(file)
  except BrokenPipeError as e:
    pass

if __name__ == '__main__':
  main(sys.argv[1:])
