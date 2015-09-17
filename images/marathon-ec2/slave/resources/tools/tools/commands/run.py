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
import logging

from tools.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():

    class _Tool(Template):

        help = \
            '''
                Runs an arbitrary shell snippet through the portal and print out the outcome on stdout. This is
                a convenient way to remote-control your cluster straight from your integration.yml.
            '''

        tag = 'run'

        def customize(self, parser):

            parser.add_argument('snippet', type=str, nargs=1, help='verbatim shell snippet')

        def body(self, args, remote):

            js = remote(' '.join(args.snippet))
            logger.info(js['out'])
            return 0 if js['ok'] else 1

    return _Tool()