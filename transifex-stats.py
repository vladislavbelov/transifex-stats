#!/usr/bin/python
#
# The MIT License (MIT)
#
# Copyright (c) 2016-2021 Vladislav Belov
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

__author__ = 'vladislavbelov'
__license__ = 'MIT'
__version__ = '0.1.2'


import argparse
import base64
import getpass
import json
import os
import sys
import time
if sys.version_info[0] == 2:
    from urllib2 import HTTPError
    from urllib2 import Request
    from urllib2 import urlopen
elif sys.version_info[0] == 3:
    from urllib.error import HTTPError
    from urllib.request import Request
    from urllib.request import urlopen
else:
    raise ImportError('Unsupported python version')


# cache expired in seconds
UPDATE_TIME = 60 * 15


class Translation(object):
    sort_by = None
    def __init__(self, source_string, last_update, user, resource, translated_string):
        self.source_string = source_string
        self.last_update = last_update
        self.user = user
        self.resource = resource
        self.translated_string = translated_string

    def __lt__(self, other):
        return self.less(other)

    def __cmp__(self, other):
        return self.less(other)

    def less(self, other):
        if Translation.sort_by is None:
            return self.last_update > other.last_update
        if Translation.sort_by == 'resource':
            return self.resource < other.resource
        elif Translation.sort_by == 'user':
            return self.user < other.user
        elif Translation.sort_by == 'source':
            return self.source < other.source
        else:
            return self.last_update > other.last_update

    @staticmethod
    def sort_by(group):
        Translation.sort_by = group


class User(object):
    def __init__(self, name):
        self.name = name
        self.count = 0
        self.last_update = '1970-01-01T00:00:00.000'

    def add_translation(self, translation):
        self.count += 1
        if translation['last_update'] > self.last_update:
            self.last_update = translation['last_update']

    def __lt__(self, other):
        return self.count > other.count

    def __cmp__(self, other):
        return self.count > other.count


class TransifexStats(object):

    def __init__(self, project, username, language='en', password=None, quiet=False, logoutput=sys.stdout):
        # project authorization data
        self.project = project
        self.username = username
        self.password = password
        self.language = language
        self.quiet = quiet
        self.logoutput = logoutput

        # project translation data
        self.resources = None

    def log(self, text):
        if not self.quiet:
            self.logoutput.write(text + '\n')

    def request(self, method):
        url = 'https://www.transifex.com/api/2' + method
        auth = ('%s:%s' % (self.username, self.password)).encode('utf-8')
        base64string = base64.b64encode(auth).decode('ascii')
        headers = {
            'Authorization': 'Basic %s' % base64string,
            'Content-Type': 'application/json',
            'User-Agent': 'Statsbot/%s' % (__version__)
        }

        try:
            request = Request(url, None, headers)
            handle = urlopen(request)
            data = json.loads(handle.read().decode('utf-8'))
            handle.close()
        except HTTPError as error:
            if error.code == 401:
                print('Authorization failed.')
                exit()
            else:
                raise

        return data

    def need_password(self, cache=True):
        path = '%s_resources_%s.json' % (self.project, self.language)
        if cache and os.path.isfile(path) and time.time() - os.path.getmtime(path) <= UPDATE_TIME:
            return False
        return True

    def download(self, cache=True):
        path = '%s_resources_%s.json' % (self.project, self.language)
        if cache and os.path.isfile(path) and time.time() - os.path.getmtime(path) <= UPDATE_TIME:
            self.log('Cache used.')
            handle = open(path, 'r')
            self.resources = json.load(handle)
            handle.close()
            return

        self.log('Downloading resource list:')
        self.resources = self.request('/project/%s/resources/' % self.project)
        self.log(' Completed.')

        self.log('Downloading resources strings for language "%s":' % (self.language))
        for resource in self.resources:
            self.log(' Resource: %s' % (resource['name']))
            method = '/project/%s/resource/%s/translation/%s/strings/?details' % (self.project, resource['slug'], self.language)
            resource['strings'] = self.request(method)
            self.log('  Completed.')

        if cache:
            handle = open(path, 'w')
            json.dump(self.resources, handle)
            handle.close()

    def analyze(self, limits, group):
        users = {}
        translations = []
        for resource in self.resources:
            for str in resource['strings']:
                user = str['user']
                if not user:
                    continue
                if user not in users:
                    users[user] = User(user)
                translation = Translation(str['source_string'], str['last_update'], str['user'], resource['name'], str['translation'])
                users[user].add_translation({'last_update': str['last_update']})
                translations.append(translation)

        if group:
            Translation.sort_by(group)
        users = sorted(users.values())
        translations = sorted(translations)

        # top users
        top_limit = 50
        if 'top_limit' in limits:
            top_limit = int(limits['top_limit'])

        path = '%s_%s_users_top_%d.txt' % (self.project, self.language, top_limit)
        handle = open(path, 'w')
        line = '%21s %18s %21s\n' % ('user name', 'translations', 'last update')
        handle.write(line)
        for user in users[:top_limit]:
            line = '%25s: %9d %32s\n' % (user.name, user.count, user.last_update)
            try:
                handle.write(line)
            except:
                handle.write(line.encode('utf-8'))
        handle.close()

        print('Top %d user list saved to "%s"' % (top_limit, path))

        # last changes
        changes_limit = 100
        if 'changes_limit' in limits:
            changes_limit = int(limits['changes_limit'])

        path = '%s_%s_last_changes.txt' % (self.project, self.language)
        handle = open(path, 'w')
        handle.write('Last changes\n\n')

        for translation in translations[:changes_limit]:
            line = '%s: "%s", %s by %s\n' % (translation.resource, translation.source_string, translation.last_update, translation.user)
            try:
                handle.write(line)
            except:
                handle.write(line.encode('utf-8'))
        handle.close()

        print('Last %d changes list saved to "%s"' % (changes_limit, path))


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('projectcode', help='project code')
    parser.add_argument('username', help='username of an account on the transifex')
    parser.add_argument('-p', '--password', help='password of the account on the transifex', default=None)
    parser.add_argument('-l', '--language', help='language code of the project on the transifex', default=None)
    parser.add_argument('-g', '--groupby', choices=['resource', 'user', 'source', 'date'],
        help='group changes by param (resource, user, source, date - default)', default=None)
    parser.add_argument('-s', '--limits', help='set limits (top_limit, changes_limit', default=None)
    args = parser.parse_args()

    password = args.password
    language = args.language

    limits = {}
    if args.limits:
        pair = args.limits.split('=')
        limits[pair[0]] = pair[1]

    stats = TransifexStats(args.projectcode, args.username)

    if not language:
        language = raw_input('Language code: ')
    stats.language = language

    if not password and stats.need_password():
        password = getpass.getpass('Password: ')
    stats.password = password

    stats.download()
    stats.analyze(limits, args.groupby)


if __name__ == '__main__':
    run()

