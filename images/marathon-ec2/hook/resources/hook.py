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
import sys

from datetime import datetime
from flask import Flask, request, render_template
from ochopod.core.fsm import diagnostic

logger = logging.getLogger('ochopod')

web = Flask(__name__)


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
        # - grab our redis IP
        # - connect to it
        #
        tokens = os.environ['redis'].split(':')
        client = redis.StrictRedis(host=tokens[0], port=int(tokens[1]), db=0)

        @web.route('/ping', methods=['GET'])
        def _ping():

            return '', 200

        @web.route('/status/<path:path>', methods=['GET'])
        def _status(path):

            payload = client.get(path)
            if payload is None:
                return '', 404

            return payload, 200, \
                {
                    'Content-Type': 'application/json; charset=utf-8'
                }

        @web.route('/svg/<path:path>', methods=['GET'])
        def _svg(path):

            log = []
            payload = client.get(path)
            if payload is None:
                tagline = 'repo not indexed (check your git hook)'

            else:

                #
                # -
                #
                js = json.loads(payload)
                tagline = 'integration %s (ran in %d seconds, commit %s)' % ('passed' if js['ok'] else 'failed', js['seconds'], js['sha'][0:10])

                def _clip(line):
                    chars = len(line)
                    return line if chars <= 80 else line[0:77] + '...'

                log = [_clip(line) for line in js['log']]

            svg = render_template('status_80chars.svg', lines=1+len(log), tagline=tagline, log=enumerate(log))

            return svg, 200, \
                {
                    'Content-Type': 'image/svg+xml',
                    'Last-Modified': datetime.now(),
                    'Cache-Control': 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0',
                    'Expires': '-1',
                    'Pragma': 'no-cache'
                }

        @web.route('/', methods=['POST'])
        def _post():

            client.rpush('queue', request.data)
            return '', 200

        #
        # - run our flask endpoint on TCP 10000
        #
        web.run(host='0.0.0.0', port=10000)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)