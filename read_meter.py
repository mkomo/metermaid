#!/usr/bin/env python3

import sys
import os
import cv2
import numpy as np
from math import atan2, pi, floor, ceil
from matplotlib import pyplot as plt
from matplotlib import colors as mcolors
from collections import OrderedDict
import json
from datetime import datetime

PROJECTED_WIDTH = 400
PROJECTED_HEIGHT = 225
MAX_DIAL_DISTANCE = 45

DIALS = [
  # coord, clockwise, factor
  { "center": [93, 83], "clockwise": False, "factor": 1000000 },
  { "center": [172,83], "clockwise":  True, "factor": 100000 },
  { "center": [242,83], "clockwise": False, "factor": 10000 },
  { "center": [317,83], "clockwise":  True, "factor": 1000, "precise": True},

  # 1,037 BTU/cubic foot of natural gas, so ~500 BTU per revolution of 0.5 cu ft dial,
  # and ~2000 BTU to get both the 0.5 and 2cf to the same test dial state.

  # our furnace and HWT are both rated at 200kBTU/hr. Both running at their theoretical
  # maximum would take 18 seconds to return to the same test dial state.
  { "center": [68, 174], "clockwise":  False, "test": True, "factor": 0.5 / 10 },
  { "center": [153,174], "clockwise":  False, "test": True, "factor": 2 / 10 }
]

def get_dial_spec(c, cntr):
  area = cv2.contourArea(c)
  if not 400 < area < 700:
    return False
  dial_list = [dial for dial in DIALS if (cv2.norm(np.array(cntr) - np.array(dial["center"]), cv2.NORM_L2) < MAX_DIAL_DISTANCE)]
  if len(dial_list) == 0:
    return False
  elif len(dial_list) > 1:
    raise "too many dials found close to center of contour"

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

def analyze_contour(pts, img):
  #PCA
  sz = len(pts)
  data_pts = np.empty((sz, 2), dtype=np.float64)
  for i in range(data_pts.shape[0]):
    data_pts[i,0] = pts[i,0,0]
    data_pts[i,1] = pts[i,0,1]
  mean, eigenvectors, eigenvalues = cv2.PCACompute2(data_pts, np.empty((0)))
  M = cv2.moments(pts)
  if not M["m00"]:
    return {}
  center_of_mass = [M["m10"] / M["m00"], M["m01"] / M["m00"]]

  dial = get_dial_spec(pts, center_of_mass)
  if not dial:
    return {}

  bbrect = cv2.minAreaRect(pts)
  bb = cv2.boxPoints(bbrect)

  # make sure the ray is pointing from the center_of_mass toward the bb center along the principal component.
  factor = sign(center_of_mass, eigenvectors[0], bbrect[0])
  p1 = (center_of_mass[0] + eigenvectors[0,0] * 100 * factor, center_of_mass[1] + eigenvectors[0,1] * 100 * factor)
  # printerr(dial["factor"], mean[0], center_of_mass, bbrect[0])
  angle = atan2(eigenvectors[0,1] * factor, eigenvectors[0,0] * factor) # orientation in radians

  # Annotate the image by drawing the contours that were used
  cv2.drawContours(img, [pts], 0, (0,0,255), 2)
  cv2.drawContours(img, [np.int0(bb)], 0, (0,0,255), 2)
  cv2.line(img, np.int0(center_of_mass), np.int0(p1), (0, 220, 55), 3, cv2.LINE_AA)
  cv2.circle(img, np.int0(mean[0]), 3, (255, 0, 255), 2)
  cv2.circle(img, np.int0(bbrect[0]), 3, (255, 126, 0), 2)
  cv2.circle(img, np.int0(center_of_mass), 3, (0, 226, 0), 2)

  return {dial["factor"]: (dial, angle)}

def sign(origin, vector, point):
  perpendicular_slope = -1 * vector[0] / vector[1]
  vals = [(point[1] - perpendicular_slope * (point[0] - origin[0]) - origin[1]) for point in [np.add(origin, vector), point]]
  return 1 if vals[0] * vals[1] > 0 else -1

def get_dial_value(dial_spec, angle):
  angle_deg = (angle * 180 / pi + 90) % 360
  value = angle_deg / 36
  value = value if dial_spec['clockwise'] else (10 - value)
  printerr([
    dial_spec,
    value
  ])

  return value


def unskew_dials(original):
    ### find the meter dial case
    # skew from perspective to rectangle
    pts1 = np.float32([[99, 145], [216, 127],
                       [109, 228], [220,203]])
    pts2 = np.float32([[0, 0], [PROJECTED_WIDTH, 0],
                       [0, PROJECTED_HEIGHT], [PROJECTED_WIDTH, PROJECTED_HEIGHT]])

    # Apply Perspective Transform Algorithm
    matrix = cv2.getPerspectiveTransform(pts1, pts2)
    return cv2.warpPerspective(original, matrix, (PROJECTED_WIDTH, PROJECTED_HEIGHT))


def validate_value(value, previous_value):
  # handle case where value is very close to an integer (ie 7.999999 vs 8.00001)
  if previous_value is not None:
    tenth = (value - floor(value)) * 10
    if tenth < 1 and previous_value > 9:
      return np.nextafter(floor(value), floor(value) - 1)
    elif previous_value < 1 and tenth > 9:
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

def analyze_raw(filename, action='show'):
    original = cv2.imread(filename)
    result = unskew_dials(original)

    # find the dials and measure the angles
    imgray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(imgray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,11,2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    dials = {}
    if contours:
        for c in contours:
            # Find the orientation of each shape
            dials.update(analyze_contour(c, result))

    add_caption(result, filename, dials)

    if action == 'noop':
      pass
    elif action == 'show':
      # cv2.imshow('original', original)
      cv2.imshow('skewed', result)
      cv2.waitKey(0)
    elif action == 'save':
      new_filename = filename + '.annotated.jpg'
      cv2.imwrite(new_filename, result)
      printerr('saved to', new_filename)

def printerr(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def main(argv):
  action = argv[0] if len(sys.argv) > 0 else ""

  '''
  TODO
  get deltas between readings
  find background usage
  find contiguous usages, total them, draw characteristic
  function to prune images (in some rrd/logrotate type fashion)
  '''

  for filename in argv[1:]:
    if len(filename) > 0 and not os.path.exists(filename):
      printerr("Usage: python3 read_meter.py <show|save> <image>(...)")
      printerr(argv)
      sys.exit(1)
    analyze_raw(filename, action)


if __name__ == '__main__':
    main(sys.argv[1:])