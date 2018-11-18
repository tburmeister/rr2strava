import json
import os
import requests

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from parser import LogParser

USERNAME = 'The%20Burmeister'
START = '2008-04-01'
END = '2016-07-01'
OUTDIR = 'out'
URL = 'http://www.runnerunner.com/log.php?username={}&dates={}'


def get_month(date):
    resp = requests.get(URL.format(USERNAME, date))
    print('Retrieved log for {}'.format(date))
    parser = LogParser(date)
    parser.feed(resp.content.decode())
    parser.close()

    with open(os.path.join(OUTDIR, '{}.json'.format(date)), 'w') as fp:
        json.dump(parser.out, fp)

    if len(parser.errors) > 0:
        with open(os.path.join(OUTDIR, 'errors-{}.txt'.format(date)), 'w') as fp:
            fp.writelines(parser.errors)

    print('Wrote data for {}'.format(date))


def get_all():
    executor = ThreadPoolExecutor()
    curr = datetime.strptime(START, '%Y-%m-%d')
    end = datetime.strptime(END, '%Y-%m-%d')

    while curr < end:
        executor.submit(get_month, curr.strftime('%Y-%m-%d'))
        if curr.month == 12:
            curr = datetime(year=curr.year + 1, month=1, day=1)
        else:
            curr = datetime(year=curr.year, month=curr.month + 1, day=1)

    executor.shutdown(wait=True)


if __name__ == '__main__':
    get_all()
