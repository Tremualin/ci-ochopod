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

from ochopod.bindings.ec2.marathon import Pod
from ochopod.models.piped import Actor as Piped
from ochopod.models.reactive import Actor as Reactive


logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    class Model(Reactive):

        depends_on = ['portal', 'redis']

    class Strategy(Piped):

        cwd = '/opt/slave'

        def can_configure(self, cluster):

            assert len(cluster.dependencies['portal']) == 1,    'need 1 portal'
            assert len(cluster.dependencies['redis']) == 1,     'need 1 redis'

        def configure(self, cluster):

            #
            # - look the ochothon portal up @ TCP 9000
            # - update the resulting connection string into /opt/slave/.portal
            # - this will be used by the CI/CD scripts to issue commands
            #
            with open('/opt/slave/.portal', 'w') as f:
                f.write(cluster.grep('portal', 9000))

            #
            # - note we use supervisor to socat the unix socket used by the underlying docker daemon
            # - it is bound to TCP 9001 (e.g any curl to localhost:9001 will talk to the docker API)
            # - run the slave
            #
            return 'python slave.py', {'redis': cluster.grep('redis', 6379)}

    Pod().boot(Strategy, model=Model)