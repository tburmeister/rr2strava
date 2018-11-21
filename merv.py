import csv
import io
import json
import re
import requests

from datetime import datetime


def get_user_report(name):
    data = {
        'name': name,
        'reportType': 'csv',
        'allDates': '1',
        'startDate': '',
        'endDate': '',
        'type': 'Run',
        'allSubtypes': '1',
        'whatToPlot': 'pace',
        'paceUnit': '/mi',
        'distanceUnit': 'mi',
        'dataStyle': 'linespoints',
        'mergeSubtypes': '0',
        'Request': 'Do it',
        'Action': 'plot'
    }
    return requests.post('http://mervsrunning.com/Workouts', data=data)


def parse_data(raw):
    cleaned = re.sub(r'NOW SAVE AS A FILE WITH THE EXTENSION .*', '', raw.decode()).lstrip()
    fp = io.StringIO(cleaned)
    reader = csv.reader(fp, delimiter=',')
    out = []

    for idx, row in enumerate(reader):
        if idx == 0:
            continue

        if len(row) == 0:
            continue

        out.append(parse_row(row))

    return out


def parse_row(row):
    """
    ['Date',
     'type',
     'subtype',
     'distance',
     'distanceUnit',
     'pace',
     'paceUnit',
     'duration',
     'shoepair',
     'rhr',
     'brief',
     'addendum',
     'note']
    """
    print(len(row))
    (date,
     event_type,
     workout_type,
     distance, _,
     pace, _,
     duration, _, _,
     title,
     addendum,
     desc, _) = row

    time_conversion = 60 if pace and float(pace) > 1 else 3600
    desc = addendum + '\n' + desc if addendum else desc
    desc = desc.replace('    ', '\n\n')
    date = datetime.strptime('%Y-%m-%d', date).strftime('%Y-%m-%dT12:00:00Z')

    return {
        'start_date_local': date,
        'type': convert_event_type(event_type),
        'workout_type': convert_workout_type(workout_type),
        'distance': 1609.344 * float(distance) if distance else 0,
        'elapsed_time': time_conversion * float(duration) if duration else 0,
        'name': title,
        'description': desc
    }


def convert_event_type(event_type):
    return 'run'


def convert_workout_type(workout_type):
    return None


if __name__ == '__main__':
    resp = get_user_report('The Burmeister')
    out = parse_data(resp.content)
    print(json.dumps(out, indent=4))
