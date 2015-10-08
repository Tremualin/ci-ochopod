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
import os
import requests
import sys
import yaml

from contextlib import contextmanager
from ochopod.core.fsm import diagnostic
from ochopod.core.utils import shell
from os.path import basename, expanduser, isfile


@contextmanager
def servo(strict=True, verbose=False):
    try:

        #
        # - retrieve the portal coordinates from /opt/servo/.portal
        # - this file is rendered by the pod script upon boot
        #
        _, lines = shell('cat .portal', cwd='/opt/servo')
        portal = lines[0]
        assert portal, '/opt/servo/.portal not found (pod not yet configured ?)'

        def _proxy(cmdline):

            #
            # - this block is taken from cli.py in ochothon
            # - in debug mode the verbatim response from the portal is dumped on stdout
            # - slight modification : we force the json output (-j)
            #
            tokens = cmdline.split(' ') + ['-j']
            files = ['-F %s=@%s' % (basename(token), expanduser(token)) for token in tokens if isfile(expanduser(token))]
            line = ' '.join([basename(token) if isfile(expanduser(token)) else token for token in tokens])
            snippet = 'curl -X POST -H "X-Shell:%s" %s %s/shell' % (line, ' '.join(files), portal)
            code, lines = shell(snippet)
            assert code is 0, 'is the portal @ %s down ?' % portal
            js = json.loads(lines[0])
            ok = js['ok']
            if verbose:
                print '[%s] "%s"' % ('passed' if ok else 'failed', cmdline)
            assert not strict or ok, '"%s" failed' % cmdline
            return json.loads(js['out']) if ok else None

        yield _proxy

        #
        # - all clear, return 0 to signal a success
        #
        sys.exit(0)

    except AssertionError as failure:

        print 'failure -> %s' % failure

    except Exception as failure:

        print 'unexpected failure -> %s' % diagnostic(failure)

    sys.exit(1)

