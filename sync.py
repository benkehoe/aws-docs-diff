#!/bin/env/python3

import os
from pathlib import Path
import re
import subprocess
import datetime
import time

import requests

class DocsDiff(object):
    GITHUB_USER_ENV_KEY = 'AWSDOCSDIFF_GITHUB_USER'
    GITHUB_PASSWORD_ENV_KEY = 'AWSDOCSDIFF_GITHUB_PASSWORD'
    
    def __init__(self):
        self.content_root = Path('content')
        
        self.docs_root = self.content_root/'docs'
        self.diffs_root = self.content_root/'diffs'
        
        self._timestamp = None
        
        self.github_url = 'https://api.github.com/orgs/awsdocs/repos'
        
        self.excludes = [
            r'-samples$'
        ]
    
    @property
    def timestamp(self):
        if not self._timestamp:
            self._timestamp = datetime.datetime.now()
        return self._timestamp
    
    @timestamp.setter
    def timestamp(self, value):
        self._timestamp = value
    
    def _run(self, *args, **kwargs):
#         print('running', args, kwargs)
        output = subprocess.check_output(*args, **kwargs)
#         print('output:', output)
        return output
    
    def _get_github_auth(self):
        if self.GITHUB_USER_ENV_KEY in os.environ:
            user = os.environ[self.GITHUB_USER_ENV_KEY]
            password = os.environ[self.GITHUB_PASSWORD_ENV_KEY]
            return requests.auth.HTTPBasicAuth(user, password)
        return None
    
    def get_repos(self):
        #print('>>>get_repos')
        repos = {}
        
        url = self.github_url
        
        while True:
            response = requests.get(url,
                                    auth=self._get_github_auth())
            
            response.raise_for_status()
            
            body = response.json()
            
            for repo in body:
                name = repo['name']
                
                include = True
                for exclude in self.excludes:
                    if (re.search(exclude, name) or
                        re.search(exclude, repo['full_name'])):
                        include = False
                        break
                
                if include:
                    repos[name] = repo['clone_url']
            
            link = response.headers.get('Link', '')
            match = re.search(r'<([^>]+)>; rel="next"', link)
            if match:
                url = match.group(1)
                time.sleep(0.5)
            else:
                break
        return repos

    def sync_repo(self, repo_name, repo_url):
        if not self._doc_repo_path(repo_name).is_dir():
            self._clone_repo(repo_name, repo_url)
            self._write_diff(repo_name, '')
        else:
            self._fetch_repo(repo_name, repo_url)
            diff = self._get_diff(repo_name)
            self._write_diff(repo_name, diff)

    def sync(self):
        _ = self.timestamp # make sure we have a timestamp before doing anything
        
        repos = self.get_repos()
        
        for repo_name, repo_url in repos.items():
            self.sync_repo(repo_name, repo_url)
        
        self._commit()
        
        for repo_name in repos.keys():
            self._move_head(repo_name)

    def _doc_repo_path(self, repo_name):
        return self.docs_root/repo_name

    def _clone_repo(self, repo_name, repo_url):
        #print('>>>clone', repo_name)
        doc_repo_path = self._doc_repo_path(repo_name)
        doc_repo_path.parent.mkdir(parents=True, exist_ok=True)
        self._run([
                'git',
                'clone',
                repo_url,
                doc_repo_path,
            ],
        )
        update_commit = self._get_branch_commit(repo_name, 'HEAD')
        self._run([
                'git',
                '-C', self._doc_repo_path(repo_name),
                '-c', 'advice.detachedHead=false',
                'checkout',
                update_commit,
            ],
        )
        self._fetch_repo(repo_name, repo_url)

    def _fetch_repo(self, repo_name, repo_url):
        #print('>>>fetch', repo_name)
        self._run([
                'git',
                '-C', self._doc_repo_path(repo_name),
                'fetch',
                repo_url,
            ],
        )

    def _get_branch_commit(self, repo_name, branch):
        #print('>>>get commit', repo_name, branch)
        return self._run([
                'git',
                '-C', self._doc_repo_path(repo_name),
                'rev-list',
                '-1',
                '--before', self.timestamp.isoformat(),
                branch,
            ],
        ).strip()

    def _move_head(self, repo_name):
        #print('>>>move_head', repo_name)
        fetch_head = self._get_branch_commit(repo_name, 'FETCH_HEAD')
        self._run([
                'git',
                '-C', self._doc_repo_path(repo_name),
                '-c', 'advice.detachedHead=false',
                'checkout',
                fetch_head,
            ],
        )

    def _get_diff(self, repo_name):
        #print('>>>get_diff', repo_name)
        head = self._get_branch_commit(repo_name, 'HEAD')
        fetch_head = self._get_branch_commit(repo_name, 'FETCH_HEAD')
        
        updated = fetch_head != head
        
        if not updated:
            return ''
        
        diff = self._run([
                'git',
                '-C', self._doc_repo_path(repo_name),
                'diff',
                '--unified={}'.format(10),
                head,
                fetch_head,
            ],
        ).decode("utf-8")
        
        return diff

    def _init_diff_repo(self):
        #print('>>>create_diff_repo')
        self.diffs_root.mkdir(parents=True)
        self._run([
                'git',
                'init',
                self.diffs_root,
            ],
        )
    
    def _write_diff(self, repo_name, diff):
        #print('>>>write_diff', repo_name)
        if not self.diffs_root.is_dir():
            self._init_diff_repo()
        path = self.diffs_root/(repo_name+'.diff')
        with path.open('w') as fp:
            fp.write(diff)
        t = self.timestamp.timestamp()
        os.utime(path, (t,t))
    
    def _commit(self):
        #print('>>>commit')
        self._run([
                'git',
                '-C', self.diffs_root,
                'add',
                '.',
            ],
        )
        changed = 0 != subprocess.call([
                'git',
                '-C', self.diffs_root,
                'diff',
                '--cached',
                '--exit-code',
            ],
            )
        if changed:
            self._run([
                    'git',
                    '-C', self.diffs_root,
                    'commit',
                    '-a',
                    '-m', self.timestamp.isoformat(),
                    '--date="{}"'.format(self.timestamp.isoformat())
                ]
            )
        else:
            print('nothing to commit')

timestamp1 = datetime.datetime(2018, 3, 14)
timestamp2 = datetime.datetime(2018, 3, 21)
timestamp3 = datetime.datetime(2018, 3, 28)


diff = DocsDiff()

# diff.timestamp = timestamp1
# diff.timestamp = timestamp2
# diff.timestamp = timestamp3

diff.sync()

# diff._commit()