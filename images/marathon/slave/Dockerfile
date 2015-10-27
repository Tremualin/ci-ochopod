FROM autodeskcloud/pod:1.0.7

#
# - install jdk8 from oracle
#
RUN apt-get install -y python-software-properties software-properties-common
RUN add-apt-repository ppa:webupd8team/java
RUN echo oracle-java8-installer shared/accepted-oracle-license-v1-1 select true | /usr/bin/debconf-set-selections
RUN apt-get update && apt-get install -y oracle-java8-installer

#
# - add socat, pyyaml & redis
#
RUN apt-get install -y socat
RUN pip install redis pyyaml

#
# - add our internal package containing our python tools
# - install it (that will install a few scripts on the path)
#
ADD resources/tools /opt/python/tools
RUN cd /opt/python/tools && python setup.py install

#
# - add our spiffy pod script
# - add the slave script
# - add the supervisor config files
# - start supervisor
#
ADD resources/pod /opt/slave/pod
ADD resources/slave.py /opt/slave/
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
