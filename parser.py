import json
import re
import requests

from html.parser import HTMLParser


def clean_entry(s):
    return s.replace('\r', '').replace('<br>', '').replace('<br />', '').strip()


class LogParser(HTMLParser):

    regex1 = re.compile(
        r'header=\[(.+?)\] body=\[(\d+|\d+\.\d+) miles\s+\(\d+:\d+/pace\s{0,1}\)\s+\((\d+) min\)\s+(.+?)\]',
        re.DOTALL
    )
    regex2 = re.compile(
        r'header=\[(.+?)\] body=\[(\d+|\d+\.\d+) miles (.*?)\]',
        re.DOTALL
    )

    def __init__(self, date):
        super().__init__()
        self.date = date
        self.out = []
        self.errors = []
        self.idx = 0

    def to_json(self):
        return json.dumps(self.out, indent=4)

    def handle_starttag(self, tag, attrs):
        if tag != 'span':
            return

        for name, value in attrs:
            if name != 'title':
                continue

            self.idx += 1
            value = value.strip()
            m = self.regex1.match(value)
            if m is not None:
                self.out.append({
                    'index': self.idx,
                    'title': m.group(1),
                    'miles': float(m.group(2)),
                    'minutes': int(m.group(3)),
                    'entry': clean_entry(m.group(4))
                })
                continue

            m = self.regex2.match(value.strip())
            if m is not None:
                self.out.append({
                    'index': self.idx,
                    'title': m.group(1),
                    'miles': float(m.group(2)),
                    'minutes': 0,
                    'entry': clean_entry(m.group(3))
                })
                continue

            print('COULD NOT MATCH: ', value)
            self.errors.append(value)


if __name__ == '__main__':
    resp = requests.get('http://www.runnerunner.com/log.php?username=The%20Burmeister&dates=2015-10-01')
    parser = LogParser('2015-10-01')
    parser.feed(resp.content.decode())
    parser.close()
    print(parser.to_json())
