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
import base64
import json
import logging
import tempfile
import time
import shutil

from os.path import join
from tools.tool import shell, Template
from urlparse import urlparse

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def go():

    class _Tool(Template):

        help = \
            '''
                Leverages the underlying docker daemon to build & push an image. You must run this script
                in a directory that contains a valid Dockerfile. The optional -t switch can be used to specify
                a tag.

                The underlying node's docker configuration (.dockercfg) is used when performing the push and must
                be mounted in /host.
            '''

        tag = 'push'

        def customize(self, parser):

            parser.add_argument('repository', type=str, nargs=1, help='docker repository to build')
            parser.add_argument('-t', dest='tag', type=str, default='latest', help='optional image tag')

        def body(self, args, remote):

            #
            # - setup a temp directory
            # - use it to store a tar of the current folder
            #
            now = time.time()
            tmp = tempfile.mkdtemp()
            tar = join(tmp, 'bundle.tgz')
            try:

                #
                # - tar the whole thing
                #
                code, _ = shell('tar zcf %s *' % tar)
                assert code is 0, 'failed to tar'

                #
                # - send the archive over to the underlying docker daemon
                # - by design our container runs a socat on TCP 9001
                #
                logger.info('building %s...' % args.repository[0])
                code, lines = shell('curl -H "Content-Type:application/octet-stream" --data-binary @%s "http://localhost:9001/build?forcerm=1\&t=%s:%s"' % (tar, args.repository[0], args.tag))
                assert code is 0, 'non zero (%d) docker exit code ?' % code
                assert len(lines) > 1, 'empty docker output (failed to build or docker error ?)'

                #
                # - cat our .dockercfg (which is mounted)
                # - craft the authentication header required for the push
                # - push the image using the specified tag
                #
                _, lines = shell('sudo cat /host/.dockercfg')
                js = json.loads(' '.join(lines))
                for url, payload in js.items():
                    tokens = base64.b64decode(payload['auth']).split(':')
                    host = urlparse(url).hostname
                    credentials = \
                        {
                            'serveraddress': host,
                            'username': tokens[0],
                            'password': tokens[1],
                            'email': payload['email'],
                            'auth': ''
                        }
                    auth = base64.b64encode(json.dumps(credentials))
                    logger.info('pushing %s as %s...' % (args.repository[0], args.tag))
                    code, lines = shell('curl -X POST -H "X-Registry-Auth:%s" "http://localhost:9001/images/%s/push?tag=%s"' % (auth, args.repository[0], args.tag))
                    assert code is 0, 'non zero (%d) docker exit code ?' % code
                    logger.info(lines)

                #
                # - clean things up and run a docker rmi
                #
                lapse = int(time.time() - now)
                logger.info('building/pushing %s took %d seconds, cleaning up...' % (args.repository[0], lapse))
                code, _ = shell('curl -X DELETE "http://localhost:9001/images/%s:%s"' % (args.repository[0], args.tag))
                assert code is 0, 'non zero (%d) docker exit code ?' % code

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                shutil.rmtree(tmp)

            return 0

    return _Tool()