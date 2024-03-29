#!/usr/bin/env python3

import sys
import os
import cv2
import argparse
import shutil
import numpy as np
from math import atan2, pi, floor, ceil
from matplotlib import pyplot as plt
from matplotlib import colors as mcolors
from collections import OrderedDict
import json
import functools
from datetime import datetime

PROJECTED_WIDTH = 400
PROJECTED_HEIGHT = 225
MAX_DIAL_DISTANCE = 45

DEBUG = False

DIALS = [
  # coord, clockwise, factor
  { "center": [93, 83], "clockwise": False, "factor": 100000 },
  { "center": [172,83], "clockwise":  True, "factor": 10000 },
  { "center": [242,83], "clockwise": False, "factor": 1000 },
  { "center": [317,83], "clockwise":  True, "factor": 100, "precise": True},

  # 1,037 BTU/cubic foot of natural gas, so ~500 BTU per revolution of 0.5 cu ft dial,
  # and ~2000 BTU to get both the 0.5 and 2cf to the same test dial state.

  # our furnace and HWT are both rated at 200kBTU/hr. Both running at their theoretical
  # maximum would take 18 seconds to return to the same test dial state.
  { "center": [68, 174], "clockwise":  False, "test": True, "factor": 0.5 / 10 },
  { "center": [153,174], "clockwise":  False, "test": True, "factor": 2 / 10 }
]

def get_dial_spec(c, cntr):
  area = cv2.contourArea(c)
  if not 300 < area < 700:
    return False
  dial_list = [dial for dial in DIALS if (cv2.norm(np.array(cntr) - np.array(dial["center"]), cv2.NORM_L2) < MAX_DIAL_DISTANCE)]
  if len(dial_list) == 0:
    return False
  elif len(dial_list) > 1:
    printerr("too many dials found close to center of contour", dial_list)
    # raise(Exception("too many dials found close to center of contour"))

  debug('get_dial_spec', cntr, dial_list)
  return dial_list[0]

def compare_thresholds(result):
  # https://opencv24-python-tutorials.readthedocs.io/en/latest/py_tutorials/py_imgproc/py_thresholding/py_thresholding.html
  imgray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
  _, th1 = cv2.threshold(imgray, 188, 255, 0)
  th2 = cv2.adaptiveThreshold(imgray,255,cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,11,2)
  th3 = cv2.adaptiveThreshold(imgray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,11,2)
  titles = ['Original Image', 'Global Thresholding (v = 127)',
              'Adaptive Mean Thresholding', 'Adaptive Gaussian Thresholding']
  images = [imgray, th1, th2, th3]
  for i in range(4):
      plt.subplot(2,2,i+1),plt.imshow(images[i],'gray')
      plt.title(titles[i])
      plt.xticks([]),plt.yticks([])
  plt.show()

def analyze_contour(pts, img, dials, filename):
  #PCA
  sz = len(pts)
  data_pts = np.empty((sz, 2), dtype=np.float64)
  for i in range(data_pts.shape[0]):
    data_pts[i,0] = pts[i,0,0]
    data_pts[i,1] = pts[i,0,1]
  mean, eigenvectors, eigenvalues = cv2.PCACompute2(data_pts, np.empty((0)))
  M = cv2.moments(pts)
  if not M["m00"]:
    return
  center_of_mass = [M["m10"] / M["m00"], M["m01"] / M["m00"]]

  dial = get_dial_spec(pts, center_of_mass)
  if not dial:
    cv2.drawContours(img, [pts], 0, (0,199,255), 1)
    return

  if dial["factor"] in dials:
    printerr('analyze_contour', 'found duplicate dial', filename, dial["factor"])
    cv2.drawContours(img, [pts], 0, (255,199,0), 1)
    return

  bbrect = cv2.minAreaRect(pts)
  bb = cv2.boxPoints(bbrect)

  # make sure the ray is pointing from the center_of_mass toward the bb center along the principal component.
  factor = sign(center_of_mass, eigenvectors[0], bbrect[0])
  p1 = (center_of_mass[0] + eigenvectors[0,0] * 100 * factor, center_of_mass[1] + eigenvectors[0,1] * 100 * factor)
  # debug(dial["factor"], mean[0], center_of_mass, bbrect[0])
  angle = atan2(eigenvectors[0,1] * factor, eigenvectors[0,0] * factor) # orientation in radians

  # Annotate the image by drawing the contours that were used
  cv2.drawContours(img, [pts], 0, (0,0,255), 2)
  cv2.drawContours(img, [np.intp(bb)], 0, (0,0,255), 2)
  cv2.line(img, np.intp(center_of_mass), np.intp(p1), (0, 220, 55), 3, cv2.LINE_AA)
  cv2.circle(img, np.intp(mean[0]), 3, (255, 0, 255), 2)
  cv2.circle(img, np.intp(bbrect[0]), 3, (255, 126, 0), 2)
  cv2.circle(img, np.intp(center_of_mass), 3, (0, 226, 0), 2)

  dials.update({dial["factor"]: (dial, angle)})

def sign(origin, vector, point):
  perpendicular_slope = -1 * vector[0] / vector[1]
  vals = [(point[1] - perpendicular_slope * (point[0] - origin[0]) - origin[1]) for point in [np.add(origin, vector), point]]
  return 1 if vals[0] * vals[1] > 0 else -1

def get_dial_value(dial_spec, angle):
  angle_deg = (angle * 180 / pi + 90) % 360
  value = angle_deg / 36
  value = value if dial_spec['clockwise'] else (10 - value)
  debug('get_dial_value', {
    'spec': dial_spec,
    'value': value
  })

  return value


def unskew_dials(original):
  return unskew_dials_complex(original)

def unskew_dials_complex(original):
  '''
    get histogram
    set threshold based on 2x size of dial panel
    find largest contour over threshold
    simplify contour to quadrilateral
  '''

  ### figure out threshold
  # histo = list(cv2.calcHist([out], [0], None, [256], [0,256]))
  # print([i[0] for i in histo])
  # print(sum([i[0] for i in histo]))
  # print(out.shape, out.shape[0] * out.shape[1])
  # tested this value on one image; seemed to work well
  # TODO make this dynamic
  thold = 248

  out = original.copy()
  imgray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)

  _, thresh = cv2.threshold(imgray,thold,255, cv2.THRESH_BINARY)
  cnts, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
  cnt = functools.reduce(lambda x, y: x if cv2.contourArea(x) > cv2.contourArea(y) else y, cnts)

  # loop over our contours
  debug('found contours', len(cnts))
  rgb = [255,100,0]

  cv2.drawContours(out, [cnt], 0, rgb, 1)

  ch = cv2.convexHull(cnt)
  debug('working on contour len={}, approxlen={}, area={}, bb={}, color={}'.format(
    len(cnt), len(ch), cv2.contourArea(cnt), cv2.boundingRect(ch), rgb)
  )
  rect = cv2.minAreaRect(cnt)
  box = np.intp(cv2.boxPoints(rect))
  debug(box)
  cv2.drawContours(out, [box], 0, rgb, 3)
  cv2.drawContours(out, [ch], 0, rgb, 2)

  cv2.putText(out, str(thold), (0, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1, cv2.LINE_AA)

  ### show image
  # cv2.imshow('result', np.concatenate((original, cv2.cvtColor(out, cv2.COLOR_BGR2RGB)), axis=1))
  # input = cv2.waitKey(0)
  # debug('received key', input)
  # if input in [3, 27, 99]:
  #   sys.exit(130)

  pts1 = np.float32(cv2.boxPoints(rect))
  pts2 = np.float32([
    [0, 0],
    [PROJECTED_WIDTH, 0],
    [PROJECTED_WIDTH, PROJECTED_HEIGHT],
    [0, PROJECTED_HEIGHT]])

  # Apply Perspective Transform Algorithm
  matrix = cv2.getPerspectiveTransform(pts1, pts2)
  return cv2.warpPerspective(original, matrix, (PROJECTED_WIDTH, PROJECTED_HEIGHT))


def validate_value(value, previous_value):
  # handle case where value is very close to an integer (ie 7.999999 vs 8.00001)
  if previous_value is not None:
    tenth = (value - floor(value)) * 10
    debug('validate_value', value, previous_value)
    if tenth < 3 and previous_value > 7:
      return np.nextafter(floor(value), floor(value) - 1)
    elif previous_value < 3 and tenth > 7:
      return np.nextafter(ceil(value), ceil(value) + 1)
  return value

def calculate_total(dials):
  approx = 0
  reading = 0
  previous_value = None
  test = {}
  for factor in sorted(dials):
    spec, angle = dials[factor]
    value = get_dial_value(spec, angle)
    if spec.get("test", False):
      test.update({spec['factor']: value * spec['factor']})
    else:
      value = validate_value(value, previous_value)
      approx += floor(value) * spec['factor']
      reading += (value if spec.get('precise') else floor(value)) * spec['factor']
      previous_value = value
  return OrderedDict({
    'approx': approx,
    'reading': reading,
    'test': dict([(key,test[key]) for key in sorted(test.keys())])
  })


def add_caption(result, filename, dials):
  timestamp = filename[-23:-4]
  outcome = calculate_total(dials)
  date = str(datetime.strptime(timestamp, '%Y-%m-%d_%H-%M-%S'))
  label = "{} - {}".format(
    date, #2022-08-09_17-00-08
    list(outcome.values())
  )
  outcome['date'] = date
  outcome['imagesrc'] = filename
  print(json.dumps(outcome))
  cv2.putText(result, label, (0, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1, cv2.LINE_AA)

def analyze_raw(f, action='show', options={}):
    original = cv2.imread(f.name)
    result = unskew_dials(original)

    # find the dials and measure the angles
    imgray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(imgray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,11,2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    dials = {}
    if contours:
        for c in contours:
            # Find the orientation of each shape
            analyze_contour(c, result, dials, f.name)

    add_caption(result, f.name, dials)

    if action == 'noop':
      pass
    elif action == 'archive':
      if 'archive_dir' not in options:
        raise(Exception('archive target not specified: ' + str(options)))
      shutil.move(f.name, options['archive_dir'])
    elif action == 'show':
      cv2.imshow('skewed', result)
      cv2.waitKey(0)
    elif action == 'save':
      new_filename = filename + '.ANNOTATED.JPG'
      cv2.imwrite(new_filename, result)
      debug('saved to', new_filename)

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
  parser.add_argument('action', choices=['noop', 'archive', 'show', 'save'])
  parser.add_argument('filename', nargs='+') # positional argument
  parser.add_argument('--archive_dir')
  parser.add_argument('-d', '--debug', action='store_true')   # on/off flag

  args = parser.parse_args()

  '''
  TODO
  find background usage
  find contiguous usages, total them, draw characteristic
  function to prune images (in some rrd/logrotate type fashion)
  '''
  global DEBUG
  if args.debug:
    DEBUG = True

  for filename in args.filename:
    if not os.path.exists(filename):
      printerr('could not find file: {}'.format(filename))
      printerr()
      printerr(parser.format_help())
      sys.exit(1)
    analyze_raw(open(filename), args.action, vars(args))


if __name__ == '__main__':
    main(sys.argv[1:])