from DDSlogger import logger, config
import threading
import queue
import time
from eventHandler import handleEvents
import sys

class PerfectFailureDetector:
    """
        # 2.6.2 Perfect Failure Detection
    """

    def __init__(self, processes, timeout, pl) -> None:
        self.pl = pl
        self.pid = pl.pid
        self.processes = processes
        self.alive = set(processes)
        self.detected = set()
        self.crashEvents = None
        self.msg_counter_rq = 0
        self.msg_counter_rp = 0

        deliverHReqEventHandlerThread = threading.Thread(target=handleEvents, args=(self.pl.getTaggedDeliverEvents('HeartbeatRequest'), self.onEventDeliverHReq))
        deliverHReqEventHandlerThread.start()

        deliverHRepEventHandlerThread = threading.Thread(target=handleEvents, args=(self.pl.getTaggedDeliverEvents('HeartbeatReply'), self.onEventDeliverHRep))
        deliverHRepEventHandlerThread.start()
        
        timeoutEventHandlerThread = threading.Thread(target=self.onEventTimeout, args=(timeout, ))  # this thread should die with its parent process
        timeoutEventHandlerThread.start()


    def onEventTimeout(self, seconds : float) -> None:
        while True:
            for p in self.processes:
                if p not in self.alive and p not in self.detected:
                    self.detected.add(p)
                    self.Crash(p)
                else:
                    self.pl.send(p, ['MT:HeartbeatRequest', 'MID:'+str(self.msg_counter_rq)])
                    self.msg_counter_rq += 1
            self.alive.clear()
            time.sleep(seconds)
            if config['LOG'].getboolean('perfectfailuredector'):
                logger.info('pid:'+self.pid+' - '+'P: expired timeout')

    def onEventDeliverHReq(self, q, message) -> None:
        try:
            self.pl.send(q, ['MT:HeartbeatReply', 'MID:'+str(self.msg_counter_rp)])
            self.msg_counter_rp += 1
            if config['LOG'].getboolean('perfectfailuredector'):
                logger.info('pid:'+self.pid+' - '+'P: delivered HeartbeatRequest from ' + str(q))
        except Exception as ex: 
            _, _, exc_tb = sys.exc_info()
            logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(ex))+' : '+str(ex))
            
    def onEventDeliverHRep(self, p, message) -> None:
        try:
            self.alive.add(p)
            if config['LOG'].getboolean('perfectfailuredector'):
                logger.info('pid:'+self.pid+' - '+'P: delivered HeartbeatReply from '+str(p))
        except Exception as ex: 
            _, _, exc_tb = sys.exc_info()
            logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(ex))+' : '+str(ex))
 
    def Crash(self, p) -> None:
        if config['LOG'].getboolean('perfectfailuredector'):
            logger.info('pid:'+self.pid+' - '+'P: detected Crash of '+str(p))
        if self.crashEvents != None:
            self.crashEvents.put(p)
        
    def getCrashEvents(self):
        self.crashEvents =  queue.Queue()
        return self.crashEvents