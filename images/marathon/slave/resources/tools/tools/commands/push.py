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

from ochopod.core.utils import shell
from tools.tool import Template
from docker import Client

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

#: Docker client
#  - by design our container runs a socat on TCP 9001
docker = Client(base_url='http://localhost:9001')

def go():

    class _Tool(Template):

        help = \
            '''
                Leverages the underlying docker daemon to build & push an image. You must run this script
                in a directory that contains a valid Dockerfile. The optional -t switch can be used to specify
                one or more image tags (defaults to latest if not specified).

                The underlying node's docker configuration (.dockercfg) is used when performing the push and must
                be mounted in /host.
            '''

        tag = 'push'

        def customize(self, parser):

            parser.add_argument('repo', type=str, nargs=1, help='docker repo to build, e.g paugamo/test')
            parser.add_argument('-t', dest='tags', type=str, default='latest', help='optional comma separated tags, e.g latest,foo,bar')

        def body(self, args):

            #
            # - setup a temp directory
            # - use it to store a tar of the current folder
            #
            stated = time.time()
            tmp = tempfile.mkdtemp()
            try:

                #
                # - tar the whole thing
                # - loop over the specified image tags
                #
                code, _ = shell('tar zcf %s/bundle.tgz *' % tmp)
                assert code == 0, 'failed to tar'
                for tag in args.tags.split(','):

                    image = '%s:%s' % (args.repo[0], tag)

                    #
                    # - send the archive over to the underlying docker daemon
                    # - make sure to remove the intermediate containers
                    #
                    tick = time.time()
                    built, output = docker.build(path='%s/bundle.tgz' % tmp, pull=True, forcerm=True, tag=image)
                    assert built, 'empty docker output (failed to build or docker error ?)'
                    logger.debug('built image %s in %d seconds' % (image, time.time() - tick))

                    #
                    # - cat our .dockercfg (which is mounted)
                    # - craft the authentication header required for the push
                    # - push the image using the specified tag
                    #
                    auth = docker.login('autodeskcloud','/host/.docker/config.json')

                    tick = time.time()
                    docker.push(image)
                    logger.debug('pushed image %s to %s in %d seconds' % (image, auth['serveraddress'], time.time() - tick))

                    #
                    # - remove the image we just built if not latest
                    # - this is done to avoid keeping around too many tagged images
                    #
                    if tag != 'latest':
                        docker.remove_image(image, force=True)

                #
                # - clean up and remove any untagged image
                # - this is important otherwise the number of images will slowly creep up
                #
                images = docker.images(quiet=True, all=True)
                victims = [item['Id'] for item in images if item['RepoTags'] == ['<none>:<none>']]
                for victim in victims:
                    logger.debug('removing untagged image %s' % victim)
                    docker.remove_image(victim, force=True)

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                shutil.rmtree(tmp)

            lapse = int(time.time() - stated)
            logger.info('%s built and pushed in %d seconds' % (args.repo[0], lapse))
            return 0

    return _Tool()