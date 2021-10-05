from DDSlogger import logger
import sys

def handleEvents(eventQueue, handlerFunction):
    try:
        while True:
            e = eventQueue.get()
            handlerFunction(*e)
    except Exception as ex:
        _, _, exc_tb = sys.exc_info()
        logger.debug('Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(ex))+' : '+str(ex))