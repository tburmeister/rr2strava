import json
import os


def entry_to_strava(entry, month):
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
