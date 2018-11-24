import atexit
import json
import re
import requests

from concurrent.futures import ThreadPoolExecutor
from flask import Flask, make_response, redirect, render_template, request, session, url_for
from download import parse_month
from merv import get_user_cache
from strava import entry_to_strava, load_user, store_user

app = Flask(__name__)
global config
global executor


merv_cache = {}


@app.route('/')
def index():
    if session.get('token') is None:
        return redirect('https://www.strava.com/oauth/authorize?client_id={}'
                        '&redirect_uri=http://{}/auth&response_type=code'
                        '&scope=activity:write'.format(config['client_id'], config['server_url']))

    if session.get('redirect') is not None:
        goto = session['redirect']
        del session['redirect']
        return redirect(goto)

    return render_template('index.html')


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


@app.route('/refresh')
def refresh():
    if 'token' in session:
        del session['token']

    return redirect(url_for('index'))


# @app.route('/test')
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
    resp = requests.post('https://www.strava.com/api/v3/activities',
                         data=data, headers=headers)
    return resp.content.decode()


@app.route('/rr', methods=['GET', 'POST'])
def rr():
    if request.method == 'GET' or request.form.get('new', '') != '':
        if session.get('token') is None:
            session['redirect'] = 'rr'
            return refresh()

        return render_template('rr_get.html')

    if request.form.get('refresh', '') != '':
        session['redirect'] = 'rr'
        return refresh()

    return rr_post()


def rr_post():
    username = request.form['username']
    req_type = request.form['type']
    month = request.form['month']
    uploaded = load_user(username, month)
    entries, errors = parse_month(username, month)
    successful = 0
    skip_zero = 0
    skipped = []
    futures = []

    if session.get('token') is None:
        session['redirect'] = 'rr'
        return refresh()

    if re.match(r'\d\d\d\d-\d\d', month) is None:
        errors.append('month not formatted correctly: must be yyyy-mm')
        return render_template('rr_post.html',
                               username=username,
                               req_type=req_type,
                               month=month,
                               successful=successful,
                               skipped=skipped,
                               errors=errors)

    if req_type == 'test':
        strava = []
        for entry in entries:
            if entry['miles'] <= 0:
                skip_zero += 1
                continue

            new = entry_to_strava(entry, month)
            new['miles'] = '{} mi'.format(entry['miles'])
            new['minutes'] = '{} min'.format(entry['minutes'])
            strava.append(new)

        response = make_response(json.dumps(strava, indent=4))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['mimetype'] = 'application/json'
        response.status_code = 200
        return response

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

    store_user(username, month, uploaded)
    return render_template('rr_post.html',
                           username=username,
                           req_type=req_type,
                           month=month,
                           successful=successful,
                           skipped=skipped,
                           errors=errors)


@app.route('/merv', methods=['GET', 'POST'])
def merv():
    if request.method == 'GET' or request.form.get('new', '') != '':
        if session.get('token') is None:
            session['redirect'] = 'merv'
            return refresh()

        return render_template('merv_get.html')

    if request.form.get('refresh', '') != '':
        session['redirect'] = 'merv'
        return refresh()

    return merv_post()


def merv_post():
    username = request.form['username']
    req_type = request.form['type']
    month = request.form['month']
    entries = get_user_cache(username)
    uploaded = load_user(username, 'merv')
    attempted = 0
    successful = 0
    skipped = []
    futures = []
    errors = []

    if session.get('token') is None:
        session['redirect'] = 'merv'
        return refresh()

    if entries is None:
        errors.append('unable to retrieve report for user {}'.format(username))
        return render_template('merv_post.html',
                               username=username,
                               req_type=req_type,
                               month=month,
                               successful=successful,
                               attempted=attempted,
                               skipped=skipped,
                               errors=errors)

    if req_type == 'test':
        entries = entries.copy()
        for entry in entries:
            entry['miles'] = '{} mi'.format(entry['distance'] / 1609.344)
            entry['minutes'] = '{} min'.format(int(entry['elapsed_time'] / 60))

        response = make_response(json.dumps(entries, indent=4))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['mimetype'] = 'application/json'
        response.status_code = 200
        return response

    if req_type == 'month' and re.match(r'\d\d\d\d-\d\d', month) is None:
        errors.append('month not formatted correctly: must be yyyy-mm')
        return render_template('merv_post.html',
                               username=username,
                               req_type=req_type,
                               month=month,
                               successful=successful,
                               attempted=attempted,
                               skipped=skipped,
                               errors=errors)

    for idx, entry in enumerate(entries):
        if req_type == 'month' and entry['start_date_local'][:7] != month:
            continue

        if str(idx) in uploaded:
            skipped.append(entry['name'])
            continue

        print(json.dumps(entry, indent=4))
        futures.append(executor.submit(do_post, idx, entry, session['token']))
        attempted += 1

    for future in futures:
        try:
            idx, resp = future.result()
        except Exception as e:
            errors.append(str(e))
            continue

        if resp.ok:
            uploaded[str(idx)] = True
            successful += 1
        else:
            errors.append(resp.content.decode())

    store_user(username, 'merv', uploaded)
    return render_template('merv_post.html',
                           username=username,
                           req_type=req_type,
                           month=month,
                           successful=successful,
                           attempted=attempted,
                           skipped=skipped,
                           errors=errors)


def do_post(entry, data, token):
    headers = {'Authorization': 'Bearer {}'.format(token)}
    resp = requests.post('https://www.strava.com/api/v3/activities',
                         data=data, headers=headers)
    return entry, resp


def shutdown():
    executor.shutdown()


if __name__ == '__main__':
    with open('config.json') as fp:
        config = json.load(fp)

    Flask.secret_key = config['secret_key']
    executor = ThreadPoolExecutor()
    atexit.register(shutdown)
    app.run(host='0.0.0.0', threaded=True)
