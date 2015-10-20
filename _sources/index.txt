
Overview
========

The CI backend
______________

This project is a simple CI/CD backend built on top of the Ochopod_ mini-PaaS. It allows you to build your images
straight from Git_ using a flow similar to Travis_.

The backend itself is made of multiple Docker_ container running Ochopod_ and living into a Mesos_ cluster. It is
articulated around a *hook* container that acts as a Git_ web-hook sink and forwards the corresponding payload to
a *redis* queue. A set of *slave* containers will pick those notifications, clone or update the code and execute a
bunch of shell commands defined in the repository itself.

Being built on top of Ochopod_ and Mesos_ the backend can easily scale up and support upgrades. The main motivation
behind this architecture is to simplify what our developers have to do to go from a Git_ repository to a
full-blown Docker_ image. Usual integration steps such as unit-testing, compilation, packaging, docker push and so
on can all be nicely folded into the repository itself.

.. warning::
    This project is *not* a replacement for CI tools such as Jenkins_ but rather a specialized companion service.

Contents
________

.. toctree::
   :maxdepth: 3

   ci
   cd
   operations

Indices and tables
__________________

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _Docker: https://www.docker.com/
.. _Git: https://github.com/
.. _Jenkins: https://jenkins-ci.org/
.. _Mesos: http://mesos.apache.org/
.. _Ochopod: https://github.com/autodesk-cloud/ochopod
.. _Travis: https://travis-ci.org
