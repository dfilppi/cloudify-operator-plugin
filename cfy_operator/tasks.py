########
# Copyright (c) 2019 Cloudify Platform All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from cloudify import ctx
from cloudify_rest_client import CloudifyClient
from cloudify import manager
from .operator import Operator
from flask import Flask, abort, request, jsonify
from threading import Thread
from datetime import datetime
import logging
import logging.handlers
import time
import os

def start(**kwargs):
    ''' Starts the operator process
    '''
    logger = configure_logging()
                       
    logger.info("Starting LDAP operator")

    # For DEBUGGING locally
    if ctx._local:
        client = CloudifyClient(
            host = '10.239.2.83',
            username = 'admin',
            password = 'admin',
            tenant = 'default_tenant')
    else:
        client = manager.get_rest_client()

    r,w = os.pipe()
    pid = os.fork()
    if pid > 0:
        # wait for pid on pipe
        os.close(w)
        for i in range(10):
            pid = os.read(r, 10)
            if pid == "":
                time.sleep(1)
                logger.debug("waiting for pid")
                continue
            else:
                ctx.instance.runtime_properties["pid"] = str(pid)
                break
        if pid == "":
            logger.error("ERROR: Failed to get child PID")
        os.close(r)
        return

    os.close(r)
    os.chdir("/tmp")
    os.setsid()
    os.umask(0)
    close_fds([w])

    pid = os.fork()
    if pid > 0:
        os.write(w,str(pid))
        os.close(w)
        os._exit(0)
    os.close(w)

    # Needed by Flask
    os.open("/dev/null", os.O_RDONLY)
    os.open("/dev/null", os.O_WRONLY)

    # Start REST server
    app = Flask(__name__)

    # init stats
    stats = {}
    stats['errcnt'] = 0
    stats['actions'] = []

    # init config
    config = {}
    config['log_location'] = '/tmp/log'

    try:
        set_routes(app, ctx.node.properties, stats, config, logger)
        rest = Thread(target=app.run, kwargs={"debug":False})
        rest.start()
    except Exception as e:
        logger.error(str(e))
        os._exit(0)

    # TODO Deep copy of properties to runtime_properties.
    #      To enable changes at runtime
    Operator().operate(client, ctx.node.properties, stats, logger)

    os._exit(0)


def stop(**kwargs):
    ''' Stops the operator process
    '''
    pid = ctx.instance.runtime_properties['pid']

    ctx.logger.info("stopping process {}".format(pid))

    res = os.system("kill "+str(pid))
    if res != 0:
        ctx.logger.error("kill failed for pid ".format(pid))


def operate(client, properties, stats):
    ''' OPERATOR MAIN LOOP '''
    while True:
        pass


def close_fds(leave_open=[0, 1, 2]):
    fds = os.listdir(b'/proc/self/fd')
    for fdn in fds:
        fd = int(fdn)
        if fd not in leave_open:
            try:
                os.close(fd)
            except Exception:
                pass


def configure_logging():
    ''' adjust below for logging needs '''

    LOGDIR_NAME = 'operator.logs'
    LOGFILE_NAME = LOGDIR_NAME + '/cfy_operator.log'  #implementation should change this
    LOGFORMAT = '%(asctime)s %(levelname)s %(message)s'

    try:
        os.mkdir("operator.logs")
    except:
        pass
    logging.basicConfig(level=logging.DEBUG,
                       format=LOGFORMAT,
                       filename=LOGFILE_NAME,
                       filemode='w+')
    logger = logging.getLogger('cfy_operator')
    handler = logging.handlers.RotatingFileHandler(
              LOGFILE_NAME, maxBytes=10**6, backupCount=2)
    logger.addHandler( handler)
    return logger


############################
# REST API
############################

def set_routes(app, properties, stats, config, logger):
    @app.route('/')
    def some_route():
        return 'usage: TBD'

    @app.route('/loglevel', methods=['GET','POST'])
    def loglevel():
      try:
        if request.method == 'GET':
            return '{"loglevel": ' + str(logger.getEffectiveLevel()) + '}'
        elif request.method == 'POST':
            body = request.json
            if not body:
                logger.error('unknown media type')
                abort(415)
            logger.info("body="+str(body))
            if 'loglevel' not in body: 
                logger.error('loglevel key missing')
                abort(400)
            logger.setLevel(int(body['loglevel']))
      except Exception as e:
        logger.error("exception :"+e.message)

