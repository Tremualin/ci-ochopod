Operations
==========

CI Backend Deployment
_____________________

You first need a Mesos_ cluster equipped with Ochothon_ (please refer to their respective documentations).

The *YAML definition* to use for each component can be found in the repository (grep for *marathon.yml*). Please note
some of them specify settings that are not defaulted (especially for the slave image). You can copy them all in one
place and edit them according to your needs.

Go ahead and add all those pods in an arbitrary "ci" namespace. We need at least one *hook* (to receive HTTP POST
requests from Git), one *redis* and a set of *slaves*. Let's pick 3 slaves for the sake of illustration. For instance:

.. code:: bash

    $ cli.py
    54.164.112.137 > deploy -n ci images/marathon/hook/marathon.yml -t 120
    54.164.112.137 > deploy -n ci images/marathon/redis/marathon.yml -t 120
    54.164.112.137 > deploy -n ci images/marathon/slave/marathon.yml -p 3 -t 120

Once this is done you should have 5 pods running on your cluster:

.. code:: bash

    $ cli.py
    54.164.112.137 > ls
    5 pods, 100% replies ->

    cluster                     |  ok   |  status
                                |       |
    ci.hook                     |  1/1  |
    ci.redis                    |  1/1  |
    ci.slave                    |  3/3  |

Note the *hook* URL (and make sure it is reachable from your Git deployment). The container will bind to its host's
TCP 5000. For instance:

.. code:: bash

    $ cli.py
    54.164.112.137 > grep *hook
    1 pods, 100% replies ->

Pay also attention to the *hook* auto-generated secret token. This random identifier must be used when setting up your
Git web-hook. For instance:

.. code:: bash

    $ cli.py
    54.164.112.137 > poll *hook
    1 pods, 100% replies ->


.. _Mesos: http://mesos.apache.org/
.. _Ochopod: https://github.com/autodesk-cloud/ochopod
.. _Ochothon: https://github.com/autodesk-cloud/ochothon
.. _Redis: http://redis.io/


