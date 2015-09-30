#
# Copyright (c) 2015 Autodesk Inc.
# All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import json
import logging
import ochopod
import os
import redis
import requests
import tempfile
import shutil
import sys
import yaml

from fnmatch import fnmatch
from ochopod.core.utils import shell
from ochopod.core.fsm import diagnostic
from os import path
from requests.auth import HTTPBasicAuth
from time import time
from yaml import YAMLError


logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        # - parse our $pod settings (defined in the pod yml)
        # - grab redis
        # - connect to it
        #
        env = os.environ
        hints = json.loads(env['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')
        settings = json.loads(env['pod'])
        tokens = os.environ['redis'].split(':')
        client = redis.StrictRedis(host=tokens[0], port=int(tokens[1]), db=0)

        #
        # -
        #
        git = settings['git']
        jenkins = settings['jenkins']

        while 1:
            _, payload = client.blpop('queue')
            try:
                log = []
                now = time()
                js = json.loads(payload)
                branch = js['ref'].split('/')[-1]
                cfg = js['repository']
                tag = cfg['full_name']
                sha = js['after']
                last = js['commits'][0]
                summary = {'ok': 0, 'sha': sha, 'branch': branch}

                tmp = tempfile.mkdtemp()
                try:

                    try:

                        #
                        # -
                        #
                        repo = path.join(tmp, cfg['name'])
                        url = 'https://%s:%s@%s' % (git['username'], git['password'], cfg['git_url'][6:])
                        logger.info('building %s (%s) @ %s' % (tag, branch, sha[0:10]))
                        code, _ = shell('git clone -b %s --single-branch %s' % (branch, url), cwd=tmp)
                        assert code == 0, 'unable to git clone %s (credentials issue ?)' % cfg['git_url']

                        #
                        # -
                        #
                        local = \
                            {
                                'HOST': env['HOST'],
                                'COMMIT': sha,
                                'COMMIT_SHORT': sha[0:10],
                                'MESSAGE': last['message'],
                                'TAG': tag,
                                'TIMESTAMP': last['timestamp']
                            }

                        #
                        # - go look for integration.yml
                        # - if not found abort
                        # - otherwise loop and execute each shell snippet in order
                        #
                        with open(path.join(repo, 'integration.yml'), 'r') as f:
                            yml = yaml.load(f)
                                                            
                            for regex in yml:
                                if fnmatch(branch, regex):

                                    #
                                    # -
                                    #
                                    js = yml[regex] if isinstance(yml[regex], list) else [yml[regex]]
                                    for blk in js:
                                        log += ['- %s' % blk['step']]
                                        debug = blk['debug'] if 'debug' in blk else 0
                                        cwd = path.join(repo, blk['cwd']) if 'cwd' in blk else repo
                                        for snippet in blk['shell']:
                                            logger.debug('running %s' % snippet)
                                            code, lines = shell(snippet, cwd=cwd, env=local)
                                            status = 'passed' if not code else 'failed'
                                            log += ['[%s] %s' % (status, snippet)]
                                            if debug:
                                                log += ['[%s]   . %s' % (status, line) for line in lines]
                                            assert code == 0, 'failed to run "%s"' % snippet

                            summary['ok'] = 1
                                                                    

                    except AssertionError as failure:

                        log += ['* %s' % str(failure)]

                    except IOError:

                        log += ['* unable to load integration.yml (missing from the repo ?)']

                    except YAMLError as failure:

                        log += ['* invalid YAML syntax']

                    except Exception as failure:

                        log += ['* unexpected condition -> %s' % diagnostic(failure)]

                finally:

                    #
                    # - make sure to cleanup our temporary directory
                    # - update redis with
                    #
                    shutil.rmtree(tmp)
                    seconds = int(time() - now)
                    summary['log'] = log
                    summary['seconds'] = seconds
                    client.set(tag, json.dumps(summary))
                    logger.info('%s @ %s -> %d seconds' % (tag, sha[0:10], seconds))

                    #
                    # -
                    #
                    safe = tag.replace('/', '-')
                    auth = HTTPBasicAuth(jenkins['username'], jenkins['token'])
                    cb = '%s/status/%s' % (settings['front-url'], tag)
                    script = \
                        [
                            '#!/bin/bash',
                            'CODE=$(curl -H "Accept: text/plain" %s)' % cb,
                            'if [[ $CODE -ne 200 ]] ; then',
                            'exit 1',
                            'fi'
                        ]

                    xml = \
                        """
                            <project>
                                <actions/>
                                <description>auto-generated CI project for repo %s</description>
                                <builders>
                                    <hudson.tasks.Shell>
                                        <command>%s</command>
                                    </hudson.tasks.Shell>
                                </builders>
                            </project>
                        """

                    requests.post(
                        '%s/createItem?name=%s' % (jenkins['url'], safe),
                        data=xml % (tag, '\n'.join(script)),
                        headers={'Content-Type': 'application/xml'},
                        auth=auth)

                    requests.post('%s/job/%s/build' % (jenkins['url'], safe), auth=auth)

            except Exception as failure:

                logger.error('unexpected condition -> %s' % diagnostic(failure))

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)