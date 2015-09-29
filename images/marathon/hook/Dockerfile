FROM autodeskcloud/pod:1.0.6

#
# - install redis
# 
RUN pip install redis

#
# - add our spiffy pod script + the flask endpoint code & its resources
# - add our supervisor script
# - start supervisor
#
ADD resources/pod /opt/hook/pod
ADD resources/hook.py /opt/hook/
ADD resources/templates /opt/hook/templates
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf