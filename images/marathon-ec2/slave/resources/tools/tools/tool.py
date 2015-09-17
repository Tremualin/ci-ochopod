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
import time

from argparse import ArgumentParser
from logging import DEBUG
from os.path import basename, expanduser, isfile
from subprocess import Popen, PIPE

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def shell(snippet):
    """
    Helper invoking a shell command and returning its stdout broken down by lines as a list. The sub-process
    exit code is also returned. Since it's crucial to see what's going on when troubleshooting Jenkins the
    shell command output is logged line by line.

    :type snippet: str
    :param snippet: shell snippet, e.g "echo foo > /bar"
    :rtype: (int, list) 2-uple
    """

    out = []
    logger.debug('shell> %s' % snippet)
    pid = Popen(snippet, shell=True, stdout=PIPE, stderr=PIPE)
    while pid.poll() is None:
        stdout = pid.stdout.readline()
        out += [stdout]
        line = stdout[:-1]
        if line:
            logger.debug('shell> %s' % (line if len(line) < 80 else '%s...' % line[:77]))

    code = pid.returncode
    return code, out

class Template():
    """
    High-level template defining a CI/CD script. The scripts all talk to the portal and rely on its toolset to
    perform operations such as deploying or killing containers. The portal coordinates are located in
    /opt/slave/.portal and set by the slave's pod script.
    """

    #: Optional short tool description. This is what's displayed when using --help.
    help = ""

    #: Mandatory identifier. The tool will be invoked using "tools <tag>".
    tag = ""

    def run(self, cmdline):

        class _Parser(ArgumentParser):
            def error(self, message):
                logger.error('error: %s\n' % message)
                self.print_help()
                exit(1)

        parser = _Parser(prog=self.tag, description=self.help)
        self.customize(parser)
        parser.add_argument('-d', '--debug', action='store_true', help='debug mode')
        args = parser.parse_args(cmdline)
        if args.debug:
            for handler in logger.handlers:
                handler.setLevel(DEBUG)

        #
        # - retrieve the portal coordinates from ~/.portal
        #
        _, lines = shell('cat /opt/slave/.portal')
        portal = lines[0]
        assert portal, '/opt/slave/.portal not found (pod not yet configured ?)'
        logger.debug('using proxy @ %s' % portal)
        def _remote(cmdline):

            #
            # - this block is taken from cli.py in ochothon
            # - in debug mode the verbatim response from the portal is dumped on stdout
            #
            now = time.time()
            tokens = cmdline.split(' ')
            files = ['-F %s=@%s' % (basename(token), expanduser(token)) for token in tokens if isfile(expanduser(token))]
            line = ' '.join([basename(token) if isfile(expanduser(token)) else token for token in tokens])
            logger.debug('"%s" -> %s' % (line, portal))
            snippet = 'curl -X POST -H "X-Shell:%s" %s %s/shell' % (line, ' '.join(files), portal)
            code, lines = shell(snippet)
            assert code is 0, 'i/o failure (is the proxy portal down ?)'
            js = json.loads(lines[0])
            elapsed = time.time() - now
            logger.debug('<- %s (took %.2f seconds) ->\n\t%s' % (portal, elapsed, '\n\t'.join(js['out'].split('\n'))))
            return js

        return self.body(args, _remote)

    def customize(self, parser):
        pass

    def body(self, args, remote):
        """
        CI/CD script body. The 2nd parameter is a callable which takes a string as input and forwards it to the portal
        as a shell request. The corresponding json response is returned as a dict.

        :type args: class:`argparse.Namespace`
        :type remote: callable
        :param args: parsed command-line arguments
        :param remote: prepackaged method which will forward a shell request to the portal
        :rtype int
        """

        raise NotImplementedError