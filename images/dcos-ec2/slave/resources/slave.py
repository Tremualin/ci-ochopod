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
import tempfile
import shutil
import sys
import yaml

from ochopod.core.fsm import diagnostic
from os import path
from subprocess import Popen, PIPE
from time import time
from yaml import YAMLError


logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        # - parse our $pod settings (defined in marathon.yml)
        #
        env = os.environ
        hints = json.loads(env['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')
        settings = json.loads(env['pod'])

        #
        # -
        #
        tokens = os.environ['redis'].split(':')
        client = redis.StrictRedis(host=tokens[0], port=int(tokens[1]), db=0)

        while 1:
            _, payload = client.blpop('queue')
            try:
                log = []
                now = time()
                js = json.loads(payload)
                cfg = js['repository']
                tag = cfg['full_name']
                sha = js['after']
                last = js['commits'][0]
                summary = {'ok': 0}

                logger.info('building %s @ %s' % (tag, sha))
                tmp = tempfile.mkdtemp()
                try:

                    try:
                        def _shell(snippet, cwd=tmp, env={}):
                            out = []
                            pid = Popen(snippet, shell=True, stdout=PIPE, stderr=PIPE, cwd=cwd, env=env)
                            while 1:
                                line = pid.stdout.readline().rstrip('\n')
                                code = pid.poll()
                                if line == '' and code is not None:
                                    return code, out
                                out += [line]

                        repo = path.join(tmp, cfg['name'])
                        branch = js['ref'].split('/')[-1]
                        code, _ = _shell('git clone -b %s --single-branch %s' % (branch, cfg['git_url']))
                        assert code == 0, 'unable to git clone %s (firewall issue ?)' % cfg['git_url']

                        #
                        #
                        #
                        local = \
                            {
                                'COMMIT': sha,
                                'COMMIT_SHORT': sha[0:10],
                                'MESSAGE': last['message'],
                                'TAG': tag,
                                'TIMESTAMP': last['timestamp']
                            }

                        env.update(local)

                        #
                        # - go look for integration.yml
                        # - if not found abort
                        # - otherwise loop and execute each shell snippet in order
                        #
                        with open(path.join(repo, 'integration.yml'), 'r') as f:
                            yml = yaml.load(f)
                            debug = yml['debug'] if 'debug' in yml else 0
                            for snippet in yml['steps']:
                                code, lines = _shell(snippet, cwd=repo, env=env)
                                log += ['> "%s" (exit %d)' % (snippet, code)]
                                if debug:
                                    log += ['  - %s' % line for line in lines]
                                assert code == 0, 'failed to run "%s"' % snippet

                        summary['ok'] = 1

                    except AssertionError as failure:

                        log += [str(failure)]

                    except IOError:

                        log += ['unable to load integration.yml (missing from the repo ?)']

                    except YAMLError as failure:

                        log += ['invalid YAML syntax']

                    except Exception as failure:

                        log += ['unexpected condition -> %s' % diagnostic(failure)]

                finally:

                    #
                    # - make sure to cleanup our temporary directory
                    # - update redis with
                    #
                    shutil.rmtree(tmp)
                    summary['log'] = log
                    summary['seconds'] = int(time() - now)
                    client.set(tag, json.dumps(summary))

            except Exception as failure:

                logger.error('unexpected condition -> %s' % diagnostic(failure))

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)