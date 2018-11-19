import json

from flask import Flask, redirect, request, session, url_for

app = Flask(__name__)
global config


@app.route('/')
def index():
    if session.get('token') is None:
        return redirect('https://www.strava.com/oauth/authorize?client_id=30264'
                        '&redirect_uri=http://{}/auth&response_type=code'
                        '&scope=activity:write'.format(config['server_url']))

    return session['token']


@app.route('/auth')
def auth():
    if session.get('token') is None:
        session['token'] = request.args.get('code')

    return redirect(url_for('index'))


if __name__ == '__main__':
    with open('config.json') as fp:
        config = json.load(fp)

    Flask.secret_key = config['secret_key']
    app.run(threaded=True)
