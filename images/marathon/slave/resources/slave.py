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
import shutil
import sys
import time
import yaml

from ochopod.core.utils import shell
from ochopod.core.fsm import diagnostic
from os import path
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
        while 1:
            _, payload = client.blpop('queue-%d' % int(env['index']))
            try:
                started = time.time()
                js = json.loads(payload)

                #
                # -
                #
                branch = js['ref'].split('/')[-1]
                if branch != 'master':
                    continue

                ok = 1
                cfg = js['repository']
                tag = cfg['full_name']
                sha = js['after']
                last = js['commits'][0]
                safe = tag.replace('/', '-')
                log = ['- commit %s (%s)' % (sha[0:10], last['message'])]

                tmp = path.join('/tmp', safe)
                try:

                    try:

                        repo = path.join(tmp, cfg['name'])
                        if not path.exists(repo):

                            #
                            # - the repo is not in our cache
                            # - git clone it using the specified credentials
                            #
                            os.makedirs(tmp)
                            logger.info('cloning %s' % tag)
                            url = 'https://%s:%s@%s' % (git['username'], git['password'], cfg['git_url'][6:])
                            shell('git clone -b master --single-branch %s' % url, cwd=tmp)

                        else:

                            #
                            # - the repo is already in there
                            # - git pull
                            #
                            shell('git pull', cwd=repo)


                        #
                        # - checkout the specified commit hash
                        #
                        logger.info('checkout @ %s' % sha[0:10])
                        code, _ = shell('git checkout %s' % sha, cwd=repo)
                        assert code == 0, 'unable to checkout %s (wrong credentials and/or git issue ?)' % sha[0:10]

                        #
                        # - prep a little list of env. variable to pass down to the shell
                        #   snippets we'll run
                        #
                        var = \
                            {
                                'QUERY_URL': 'http://10.50.85.97:5000/status/%s' % tag,
                                'PRESETS': json.dumps(settings['presets']),
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
                        #
                        with open(path.join(repo, 'integration.yml'), 'r') as f:
                            yml = yaml.load(f)

                            #
                            # - the yaml can either be an array or a dict
                            # - force it to an array for convenience
                            # - otherwise loop and execute each shell snippet in order
                            #
                            js = yml if isinstance(yml, list) else [yml]
                            for blk in js:
                                log += ['- %s' % blk['step']]
                                debug = blk['debug'] if 'debug' in blk else 0
                                cwd = path.join(repo, blk['cwd']) if 'cwd' in blk else repo
                                for snippet in blk['shell']:

                                    tick = time.time()
                                    tokens = snippet.split(' ')
                                    always = tokens[0] == 'no-skip'
                                    if always or ok:

                                        #
                                        # -
                                        #
                                        if always:
                                            snippet = ' '.join(tokens[1:])

                                        #
                                        # -
                                        #
                                        local = {'LOG': '\n'.join(log)}
                                        if ok:
                                            local['OK'] = 'true'

                                        local.update(var)
                                        logger.debug('running %s' % snippet)
                                        code, lines = shell(snippet, cwd=cwd, env=local)
                                        lapse = int(time.time() - tick)
                                        status = 'passed' if not code else 'failed'
                                        log += ['[%s] %s (%d seconds)' % (status, snippet, lapse)]
                                        if debug:
                                            log += ['[%s]   . %s' % (status, line) for line in lines]

                                        #
                                        # - switch the ok trigger off if the shell invocation failed
                                        #
                                        if code != 0:
                                            ok = 0

                                    else:
                                        log += ['[skipped] %s' % snippet]

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
                    seconds = int(time.time() - started)
                    summary = \
                        {
                            'ok': ok,
                            'sha': sha,
                            'log': log,
                            'seconds': seconds
                        }
                    client.set(tag, json.dumps(summary))
                    logger.info('%s @ %s -> %s %d seconds' % (tag, sha[0:10], 'ok' if ok else 'ko', seconds))

            except Exception as failure:

                logger.error('unexpected condition -> %s' % diagnostic(failure))

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)