import atexit
import json
import os
import requests

from concurrent.futures import ThreadPoolExecutor
from flask import Flask, redirect, request, session, url_for
from download import parse_month

app = Flask(__name__)
global config
global executor


@app.route('/')
def index():
    if session.get('token') is None:
        return redirect('https://www.strava.com/oauth/authorize?client_id={}'
                        '&redirect_uri=http://{}/auth&response_type=code'
                        '&scope=activity:write'.format(config['client_id'], config['server_url']))

    return session['token']


@app.route('/auth')
def auth():
    if session.get('token') is None:
        code = request.args.get('code')
        resp = requests.post('https://www.strava.com/oauth/token?client_id={}'
                             '&client_secret={}&code={}&grant_type=authorization_code'
                             ''.format(config['client_id'], config['client_secret'], code))
        session['token'] = resp.json()['access_token']

    return redirect(url_for('index'))


@app.route('/clear')
def clear():
    session.clear()
    return redirect(url_for('index'))


@app.route('/test')
def test():
    data = {
        'name': 'test',
        'type': 'run',
        'start_date_local': '2018-11-18T12:00:00Z',
        'elapsed_time': 60,
        'description': 'this is a test',
        'distance': 100
    }
    headers = {'Authorization': 'Bearer {}'.format(session['token'])}
    resp = requests.post('https://www.strava.com/api/v3/activities', data=data, headers=headers)
    return resp.content.decode()


@app.route('/convert/<username>/<month>')
def convert(username, month):
    uploaded = load_user_month(username, month)
    entries, errors = parse_month(username, month)
    successful = 0
    skip_zero = 0
    skipped = []
    futures = []

    for entry in entries:
        if entry['miles'] <= 0:
            skip_zero += 1
            continue

        if str(entry['index']) in uploaded:
            skipped.append(entry['title'])
            continue

        data = entry_to_strava(entry, month)
        print(json.dumps(data, indent=4))
        futures.append(executor.submit(do_post, entry, data, session['token']))

    for future in futures:
        try:
            entry, resp = future.result()
        except Exception as e:
            errors.append(str(e))
            continue
        
        if resp.ok:
            uploaded[str(entry['index'])] = True
            successful += 1
        else:
            errors.append(resp.content.decode())

    out = '{} out of {} successful <br>'.format(successful, len(entries) - skip_zero)
    out += 'skipped: <br>'
    for title in skipped:
        out += title + '<br>'
    out += 'errors: <br>'
    for error in errors:
        out += error + '<br>'

    store_user_month(username, month, uploaded)
    return out


def do_post(entry, data, token):
    headers = {'Authorization': 'Bearer {}'.format(token)}
    return entry, requests.post('https://www.strava.com/api/v3/activities', data=data, headers=headers)


def entry_to_strava(entry, month):
    if session.get('token') is None:
        redirect(url_for('index'))

    data = {
        'name': entry['title'],
        'type': 'run',
        'elapsed_time': 60 * entry['minutes'],
        'description': entry['entry'],
        'distance': 1609.344 * entry['miles']
    }

    if entry['tod'] == 'AM':
        data['start_date_local'] = '{}-{}T08:00:00Z'.format(month, entry['day'])
    else:
        data['start_date_local'] = '{}-{}T017:00:00Z'.format(month, entry['day'])

    if entry['minutes'] == 0:
        # Default to 7:30 pace
        data['elapsed_time'] = int(450 * entry['miles'])

    return data


def load_user_month(username, month):
    filename = os.path.join('data', '{}-{}.json'.format(username, month))
    if not os.path.exists(filename):
        return {}

    with open(filename, 'r') as fp:
        return json.load(fp)


def store_user_month(username, month, uploaded):
    filename = os.path.join('data', '{}-{}.json'.format(username, month))
    with open(filename, 'w') as fp:
        json.dump(uploaded, fp)


def shutdown():
    executor.shutdown()


if __name__ == '__main__':
    with open('config.json') as fp:
        config = json.load(fp)

    Flask.secret_key = config['secret_key']
    executor = ThreadPoolExecutor()
    atexit.register(shutdown)
    app.run(threaded=True)
