#!/usr/bin/python
# 
# The MIT License (MIT)
# 
# Copyright (c) 2016 Vladislav Belov
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
__version__ = '0.1.0'


import base64
import getpass
import json
import os
import sys
import time
if sys.version_info[0] == 2:
    import urllib2
elif sys.version_info[0] == 3:
    # TODO: implement Python3 support
    raise ImportError('Unsupported python version')
else:
    raise ImportError('Unsupported python version')

UPDATE_TIME = 60 * 15


class TransifexStats(object):
    
    def __init__(self, project, username, password, language='en', quiet=False, logoutput=sys.stdout):
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
        base64string = base64.encodestring('%s:%s' % (self.username, self.password)).replace('\n', '')
        headers = {
            'Authorization': 'Basic %s' % base64string,
            'Content-Type': 'application/json',
            'User-Agent': 'Statsbot/%s' % (__version__)
        }
        
        try:
            request = urllib2.Request(url, None, headers)
            handle = urllib2.urlopen(request)
            data = json.loads(handle.read().decode('utf-8'))
            handle.close()
        except urllib2.HTTPError, error:
            if error.code == 401:
                print('Authorization failed.')
                exit()
            else:
                raise
        
        return data

    def download(self, cache=True):
        path = '%s_resources_%s.json' % (self.project, self.language)
        if cache and os.path.isfile(path):
            if time.time() - os.path.getmtime(path) <= UPDATE_TIME:
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

    def analyze(self):
        # TODO: implement analyzing
        pass


if __name__ == '__main__':
    def help():
        print('usage: transifex-stats -p project -u username [-p password -l language -q]')
        print(' -i\tproject code')
        print(' -u\tusername of the account on the transifex')
        print(' -p\tpassword of the account on the transifex')
        print(' -l\tlanguage code of the project on the transifex')
    
    def parse():
        if len(sys.argv) == 1:
            help()
            return
        
        project = None
        username = None
        password = None
        language = None
        
        for i in range(len(sys.argv)):
            key = sys.argv[i]
            value = None
            if i + 1 < len(sys.argv):
                value = sys.argv[i + 1]
            if key == '-i':
                project = value
            elif key == '-u':
                username = value
            elif key == '-p':
                username = value
            elif key == '-l':
                language = value
        
        if not project or not username:
            help()
            return
        
        if not password:
            password = getpass.getpass('Password: ')
        
        if not language:
            language = raw_input('Language code: ')
        
        stats = TransifexStats(project, username, password, language)
        stats.download()
        stats.analyze()
    
    parse()
    