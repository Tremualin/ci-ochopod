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
import string
import tempfile
import time
import shutil
import sys

from flask import Flask, request
from ochopod.core.fsm import diagnostic
from ochopod.core.utils import shell
from os import path
from pykka import ThreadingFuture, Timeout

logger = logging.getLogger('ochopod')

web = Flask(__name__)


if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        #
        blocked = {}
        env = os.environ
        hints = json.loads(env['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')

        @web.route('/callback/<id>', methods=['POST'])
        def _set_callback(id):

            if id not in blocked:
                return '', 404

            blocked[id].set(request.data)
            return '', 200

        @web.route('/callback/<id>', methods=['GET'])
        def _wait_for_callback(id):

            assert not id in blocked
            latch = ThreadingFuture()
            blocked[id] = latch
            try:

                logger.info('blocking on %s' % id)
                return latch.get(60.0), 200

            except Timeout:

                return '', 404

            finally:

                del blocked[id]

        @web.route('/run/<script>', methods=['POST'])
        def _from_curl(script):

            #
            # - retrieve the X-Token header
            # - check against our random token
            # - fast-fail on a HTTP 403 if not there or if there is a mismatch
            #
            if not 'X-Token' in request.headers or request.headers['X-Token'] != env['token']:
                return '', 403

            #
            # - force a json output if the Accept header matches 'application/json'
            # - otherwise default to a text/plain response
            #
            raw = request.accept_mimetypes.best_match(['application/json']) is None

            js = \
                {
                    'ok': 0,
                    'log': ['running %s...' % script]
                }

            tmp = tempfile.mkdtemp()
            try:

                #
                # - download the archive
                # - extract it into its own folder
                #
                upload = request.files['tgz']
                upload.save(path.join(tmp, 'upload.tgz'))
                code, _ = shell('mkdir uploaded && tar zxf upload.tgz -C uploaded', cwd=tmp)
                assert code == 0, 'unable to open the archive (bogus payload ?)'

                #
                # - any request header in the form X-Var-* will be kept around and passed as
                #   an environment variable when executing the script
                # - make sure the variable is spelled in uppercase
                #
                local = {key[6:].upper(): value for key, value in request.headers.items() if key.startswith('X-Var-')}
                for key, value in local:
                    js['log'] += '$%s = %s' % (key, value)

                #
                # - craft a unique callback URL that points to this pod
                # - this will be passed down to the script to enable transient testing jobs
                #
                alphabet = string.letters + string.digits
                token = ''.join(alphabet[ord(c) % len(alphabet)] for c in os.urandom(8))
                local['CALLBACK'] = 'http://%s/callback/%s' % (env['local'], token)

                #
                # - make sure the requested script is there
                #
                cwd = path.join(tmp, 'uploaded')
                code, _ = shell('ls %s' % script, cwd=cwd)
                assert code == 0, 'unable to find %s (check your scripts)' % script

                #
                # - run it
                # - keep the script output as a json array
                #
                now = time.time()
                code, lines = shell('python %s' % script, cwd=cwd, env=local)
                js['ok'] = code == 0
                js['log'] += lines + ['script run in %d seconds' % int(time.time() - now)]

            except AssertionError as failure:

                js['log'] += ['failure (%s)' % failure]

            except Exception as failure:

                js['log'] += ['unexpected failure (%s)' % diagnostic(failure)]

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                shutil.rmtree(tmp)

            if raw:

                #
                # - if 'application/json' was not requested simply dump the log as is
                # - force the response code to be HTTP 412 upon failure and HTTP 200 otherwise
                #
                code = 200 if js['ok'] else 412
                return '\n'.join(js['log']), code, \
                    {
                        'Content-Type': 'text/plain; charset=utf-8'
                    }

            else:

                #
                # - if 'application/json' was requested always respond with a HTTP 200
                # - the response body then contains our serialized JSON output
                #
                return json.dumps(js), 200, \
                    {
                        'Content-Type': 'application/json; charset=utf-8'
                    }

        #
        # - run our flask endpoint on TCP 10000
        #
        web.run(host='0.0.0.0', port=10000, threaded=True)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)