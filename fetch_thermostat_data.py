#!/usr/bin/env python3

import sys
import os
import json
import argparse
import datetime
import requests

def fetch_thermostat_data(project_id, token):
  api_url = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/%s/devices' % project_id

  response = requests.get(api_url, headers={'Authorization': 'Bearer %s' % token})
  return json.loads(response.text)

def update_bearer_token(state, statefile):
  api_url = ('https://www.googleapis.com/oauth2/v4/token?' +
    'client_id=%s&' +
    'client_secret=%s&' +
    'grant_type=refresh_token&' +
    'refresh_token=%s&' +
    'redirect_uri=%s') % (
      state.get('client_id'),
      state.get('client_secret'),
      state.get('refresh_token'),
      state.get('redirect_uri')
    )

  printerr(api_url)

  response = requests.post(api_url)
  body = json.loads(response.text)

  printerr('received response from api: {}'.format(response.text))
  state['bearer_token'] = body['access_token']
  state['bearer_token_expire_timestamp'] = body['expires_in'] + datetime.datetime.now().timestamp()

  with open(statefile, "w") as outfile:
      outfile.write(json.dumps(state, indent=2))

def get_bearer_token(state, options):
  if state['bearer_token'] is not None and \
      state['bearer_token_expire_timestamp'] is not None and \
      state['bearer_token_expire_timestamp'] > datetime.datetime.now().timestamp():
    printerr('token is great')
  else:
    printerr('token is expired or missing. getting a new one.')
    update_bearer_token(state, options.get('statefile'))
  return state['bearer_token']

def process_file(file, options={}):
  state = json.load(open(options['statefile']))
  token = get_bearer_token(state, options)

  response = fetch_thermostat_data(state['project_id'], token)
  output = {'timestamp': datetime.datetime.now().timestamp(), 'response_body': response}
  print(json.dumps(output))

DEBUG = False

def debug(*args, **kwargs):
  if DEBUG:
    printerr(*args, **kwargs)

def printerr(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def main(argv):

  parser = argparse.ArgumentParser(
    prog = __file__,
    description = 'Fetch thermostat data from google api'
  )
  parser.add_argument('statefile')
  parser.add_argument('-d', '--debug', action='store_true')   # on/off flag

  args = parser.parse_args()

  global DEBUG
  if args.debug:
    DEBUG = True
    # pass

  if not os.path.exists(args.statefile):
    printerr('could not find file: {}'.format(args.statefile))
    printerr()
    printerr(parser.format_help())
    sys.exit(1)

  process_file(open(args.statefile), vars(args))

if __name__ == '__main__':
  main(sys.argv[1:])
