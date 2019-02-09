import time

class Operator(object):
    '''  Encapsulates the operator logic.  Operate should only
         return if exiting the operator thread is desired '''

    def __init__(self):
        pass

    def operate(self, client, properties, stats, logger):
        while True:
            logger.debug("in operate loop")
            time.sleep(1)
