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
import hashlib
import hmac
import json
import logging
import ochopod
import os
import redis
import sys

from flask import Flask, request
from ochopod.core.fsm import diagnostic

logger = logging.getLogger('ochopod')

web = Flask(__name__)


if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        # - grab redis
        # - connect to it
        #
        env = os.environ
        hints = json.loads(env['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')
        tokens = os.environ['redis'].split(':')
        client = redis.StrictRedis(host=tokens[0], port=int(tokens[1]), db=0)
        slaves = int(os.environ['slaves'])

        @web.route('/ping', methods=['GET'])
        def _ping():

            return '', 200

        @web.route('/status/<path:path>', methods=['GET'])
        def _status(path):

            branch = 'master'
            key = '%s:%s' % (branch, path)

            #
            # - force a json output if the Accept header matches 'application/json'
            # - otherwise default to a text/plain response
            #
            raw = request.accept_mimetypes.best_match(['application/json']) is None
            payload = client.get('status:%s' % key)
            if payload is None:
                return '', 404

            if raw:

                #
                # - if 'application/json' was not requested simply dump the log as is
                # - force the response code to be HTTP 412 upon failure and HTTP 200 otherwise
                #
                js = json.loads(payload)
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
                return payload, 200, \
                    {
                        'Content-Type': 'application/json; charset=utf-8'
                    }

        @web.route('/', methods=['POST'])
        def _git_hook():

            #
            # - if we have no build slaves, fast-fail on a 304
            #
            if not slaves:
                return '', 304

            #
            # - we want the hook to be signed
            # - fail on a HTTP 403 if not
            #
            if not 'X-Hub-Signature' in request.headers:
                return '', 403

            #
            # - compute the HMAC and compare (use our pod token as the key)
            # - fail on a 403 if mismatch
            #
            digest = 'sha1=' + hmac.new(env['token'], request.data, hashlib.sha1).hexdigest()
            if digest != request.headers['X-Hub-Signature']:
                return '', 403

            #
            # - ignore any push that is not done on master
            # - fail in that case on a 304
            #
            js = json.loads(request.data)
            branch = js['ref'].split('/')[-1]
            if branch != 'master':
                return '', 304

            #
            # - hash the data from git to send it to a specific queue
            # - we do this to splay out the traffic amongst our slaves while retaining stickiness
            #
            cfg = js['repository']
            path = cfg['full_name']
            qid = hash(path) % slaves
            key = '%s:%s' % (branch, path)
            client.set('git:%s' % key, request.data)
            logger.debug('updated git push data @ %s' % key)

            build = \
                {
                    'key': key
                }
            client.rpush('queue-%d' % qid, build)
            logger.debug('requested build @ %s' % key)
            return '', 200

        @web.route('/build/<path:path>', methods=['POST'])
        def _build(path):

            #
            # - if we have no build slaves, fast-fail on a 304
            #
            if not slaves:
                return '', 304

            branch = 'master'
            qid = hash(path) % slaves
            key = '%s:%s' % (branch, path)

            #
            # - look the specified repository up
            # - fail on a 404 if not found
            #
            payload = client.get('git:%s' % key)
            if payload is None:
                return '', 404

            #
            # - simply push they key to the appropriate queue
            #
            reset = 'X-Reset' in request.headers and request.headers['X-Reset'] == 'true'
            build = \
                {
                    'key': key,
                    'reset': reset
                }
            client.rpush('queue-%d' % qid, json.dumps(build))
            logger.debug('requested build @ %s' % key)
            return '', 200

        #
        # - run our flask endpoint on TCP 5000
        #
        web.run(host='0.0.0.0', port=5000)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)