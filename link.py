from genericpath import exists
import threading
import queue
import socket
import json
import time
import sys
from eventHandler import handleEvents
from abc import ABC, abstractmethod

from DDSlogger import logger, config

# HELPER FUNCTION
def recvall(sock):
    """ recvall implementation, receives data of whatever size in several chunks

    Args:
        sock (socket): connected socket

    Returns:
        [byte]: data received from the socket
    """
    BUFF_SIZE = 4096 # 4 KiB, §EDIT buffer size
    data = b''
    while True:
        part = sock.recv(BUFF_SIZE)
        data += part
        if len(part) < BUFF_SIZE:
            # either 0 or end of data
            break
    return data

# abstract class
class FairLossLink(ABC):

    @abstractmethod 
    def send(self, pid_receiver, message):
        pass

    @abstractmethod 
    def deliver(self, pid_sender, message):
        pass


class FairLossLink_vTCP_simple(FairLossLink):
    """
        # 2.4.2 Fair-Loss Links

        This implementation relies on TCP sockets and on three threads:
        1) one that keeps a listening socket open and waits for new connections
        2) one that take care of receiving sequentially messages from all incoming connections
        3) ona that transmit all messages enqueued to send
    """

    def __init__(self, pid, servicePort : int, dest_addresses : dict) -> None:
        """
        Args:
            servicePort (int): port for the incoming connections
            dest_addresses (dict): map pid -> IP address
        """
        self.pid = pid
        self.servicePort = servicePort
        self.pid_to_address = dest_addresses
        self.address_to_pid = dict((v,k) for k,v in self.pid_to_address.items())
        
        self.to_receive = queue.Queue() # (socket, sourceIP)
        self.to_send = queue.Queue()    # (destIP, messageByte)
        self.deliver_events = None      # (pid_source, message)
        
        linkInThread = threading.Thread(target=self.manage_links_in, args=())  # this thread should die with its parent process
        linkInThread.start()
        
        linkOutThread = threading.Thread(target=self.manage_links_out, args=())  # this thread should die with its parent process
        linkOutThread.start()     
        
        receiveThread = threading.Thread(target=self.receive_message, args=())  # this thread should die with its parent process
        receiveThread.start()


    ### LINK MANAGEMENT        
    def manage_links_in(self):
        while True: # if the socket fails, re-open
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: # TCP socket
                    s.bind(('', self.servicePort)) # the socket is reachable by any address the machine happens to have.
                    s.listen(1) # we want it to queue up as many as * connect requests before refusing outside connections. §EDIT
                    while True:
                        sock, addr = s.accept()
                        self.to_receive.put((sock,addr))
            except socket.error as err:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(err))+' : '+str(err))
                continue
            except Exception as ex:
                _, _, exc_tb = sys.exc_info()
                logger.debug('Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(ex))+' : '+str(ex))


    def manage_links_out(self):
        while True:
            ipDestionation, message = self.to_send.get()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2) # connect timeout
                    s.connect((ipDestionation, self.servicePort))
                    s.settimeout(None) # back to a blocking socket
                    s.sendall(message)
                    if config['LOG'].getboolean('fairlosslink'):
                        logger.info('pid:'+self.pid+' - '+'fll_send: sent '+str(message) +' to '+self.address_to_pid[ipDestionation])
            except socket.error as err:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(err))+' : '+str(err))
                continue
            except Exception as ex: #§TO-DO proper exeception handling, except socket.error:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(ex))+' : '+str(ex))
            
    def receive_message(self):
        while True:
            sock, addr = self.to_receive.get()
            try:
                with sock:
                    received_data = recvall(sock)
                    message = json.loads(received_data.decode('utf-8')) #§NOTE what about decoding errors?
                    self.deliver(self.address_to_pid[addr[0]], message['msg']) #§NOTE direct delivery
            except socket.error as err:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(err))+' : '+str(err))
                continue
            except Exception as ex:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(err))+' : '+str(err))
        
    ### INTERFACES
    def send(self, pid_receiver, message):
        data_to_send = {'msg' : message} #§NOTE message needs to be convertible in JSON
        data_to_send_byte = json.dumps(data_to_send).encode('utf-8')
        self.to_send.put((self.pid_to_address[pid_receiver],data_to_send_byte))
        if config['LOG'].getboolean('fairlosslink'):
            logger.info('pid:'+self.pid+' - '+'fll_send: sending '+str(message)+' to '+str(pid_receiver))
    
    def deliver(self, pid_sender, message):
        if config['LOG'].getboolean('fairlosslink'):
            logger.info('pid:'+self.pid+' - '+'fll_deliver: delivered '+str(message)+' from '+str(pid_sender))
        if self.deliver_events != None:
            self.deliver_events.put((pid_sender,message))

    ### INTERCONNECTION
    def getDeliverEvents(self):
        self.deliver_events = queue.Queue()
        return self.deliver_events
        

class FairLossLink_vTCP_MTC(FairLossLink):
    """
        # 2.4.2 Fair-Loss Links

        MTC: Multiple Threads Connection
        This version improves with respect to FairLossLink_vTCP_simple employing multiple threads handling the incoming and outgoing connections

    """

    def __init__(self, pid, servicePort : int, dest_addresses : dict, n_threads_in : int = 1, n_threads_out : int = 1) -> None:
        """
        Args:
            servicePort (int): port for the incoming connections
            dest_addresses (dict): map pid -> IP address
            n_threads_in (int): number of threads managing incoming connections
            n_threads_out (int): number of threads managing outgoing connections
        """
        self.pid = pid
        self.servicePort = servicePort
        self.pid_to_address = dest_addresses
        self.address_to_pid = dict((v,k) for k,v in self.pid_to_address.items())
        
        self.to_receive = queue.Queue() # (socket, sourceIP)
        self.to_send = queue.Queue()    # (destIP, messageByte)
        self.deliver_events = None      # (pid_source, message)
        
        linkInThread = threading.Thread(target=self.manage_links_in, args=(n_threads_in,))  # this thread should die with its parent process
        linkInThread.start()

        self.manage_links_out(n_threads_out)
        


    ### LINK MANAGEMENT        
    def manage_links_in(self, n_thread : int):
        # creating multiple threads that handles the incoming connections
        for i in range(n_thread):
            receiveThread = threading.Thread(target=self.receive_message, args=())  # this thread should die with its parent process
            receiveThread.start()

        while True: # if the socket fails, re-open
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: # TCP socket
                    s.bind(('', self.servicePort)) # the socket is reachable by any address the machine happens to have.
                    s.listen(1) # we want it to queue up as many as * connect requests before refusing outside connections. §EDIT
                    while True:
                        sock, addr = s.accept()
                        self.to_receive.put((sock,addr))
            except socket.error as err:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(err))+' : '+str(err))
                continue
            except Exception as ex:
                _, _, exc_tb = sys.exc_info()
                logger.debug('Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(ex))+' : '+str(ex))


    def manage_links_out(self, n_thread : int):
        for i in range(n_thread):
            sendThread = threading.Thread(target=self.send_message, args=())  # this thread should die with its parent process
            sendThread.start()
            
    def receive_message(self):
        while True:
            sock, addr = self.to_receive.get()
            try:
                with sock:
                    received_data = recvall(sock)
                    message = json.loads(received_data.decode('utf-8')) #§NOTE what about decoding errors?
                    self.deliver(self.address_to_pid[addr[0]], message['msg']) #§NOTE direct delivery
            except socket.error as err:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(err))+' : '+str(err))
                continue
            except Exception as ex:
                _, _, exc_tb = sys.exc_info()
                logger.debug('Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(ex))+' : '+str(ex))

    def send_message(self):
        while True:
            ipDestionation, message = self.to_send.get()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2) # connect timeout
                    s.connect((ipDestionation, self.servicePort))
                    s.settimeout(None) # back to a blocking socket
                    s.sendall(message)
                    if config['LOG'].getboolean('fairlosslink'):
                        logger.info('pid:'+self.pid+' - '+'fll_send: sent '+str(message) +' to '+self.address_to_pid[ipDestionation])
            except socket.error as err:
                _, _, exc_tb = sys.exc_info()
                logger.debug('pid:'+self.pid+' - Exception in '+str(sys._getframe(  ).f_code.co_name)+":"+str(exc_tb.tb_lineno)+" - "+str(type(err))+' : '+str(err))
                continue
            except Exception as ex: #§TO-DO proper exeception handling, except socket.error:
                logger.debug('pid:'+self.pid+' - EXCEPTION, '+self.manage_link_out.__name__+str(type(ex))+':'+str(ex)+' - '+str(ipDestionation))
        
    ### INTERFACES
    def send(self, pid_receiver, message):
        data_to_send = {'msg' : message} #§NOTE message needs to be convertible in JSON
        data_to_send_byte = json.dumps(data_to_send).encode('utf-8')
        self.to_send.put((self.pid_to_address[pid_receiver],data_to_send_byte))
        if config['LOG'].getboolean('fairlosslink'):
            logger.info('pid:'+self.pid+' - '+'fll_send: sending '+str(message)+' to '+str(pid_receiver))
    
    def deliver(self, pid_sender, message):
        if config['LOG'].getboolean('fairlosslink'):
            logger.info('pid:'+self.pid+' - '+'fll_deliver: delivered '+str(message)+' from '+str(pid_sender))
        if self.deliver_events != None:
            self.deliver_events.put((pid_sender,message))

    ### INTERCONNECTION
    def getDeliverEvents(self):
        self.deliver_events = queue.Queue()
        return self.deliver_events


class StubbornLink:
    """
        2.4.3 Stubborn Links
    """

    def __init__(self, fll : FairLossLink, timeout) -> None:
        self.fll = fll
        self.pid = fll.pid
        self.sent = []

        self.fllDeliverEvents = self.fll.getDeliverEvents() # interconnection
        self.send_events = queue.Queue()
        self.deliver_events = None   

        # handle timeout events
        timeoutEventHandlerThread = threading.Thread(target=self.onEventTimeout, args=(timeout, ))  # this thread should die with its parent process
        timeoutEventHandlerThread.start()
        
        # handle fll_deliver events
        fllDeliverEventHandlerThread = threading.Thread(target=handleEvents, args=(self.fllDeliverEvents, self.onEventFllDeliver))
        fllDeliverEventHandlerThread.start()

        # handle fll_deliver events
        sendEventHandlerThread = threading.Thread(target=handleEvents, args=(self.send_events, self.onEventFlSend))
        sendEventHandlerThread.start()


    ### EVENT HANDLERS
    def onEventTimeout(self, seconds : float) -> None:
        while True:
            time.sleep(seconds)
            for pid_receiver, message in self.sent:
                self.fll.send(pid_receiver, message)


    def onEventFllDeliver(self, pid_sender, message):
        self.deliver(pid_sender, message)

    def onEventFlSend(self, pid_receiver, message):
        self.fll.send(pid_receiver,message)
        self.sent.append((pid_receiver,message))
        
    ### INTERFACES
    def send(self, pid_receiver, message):
        if config['LOG'].getboolean('stubbornlink'):
            logger.info('pid:'+self.pid+' - '+'sl_send: sending '+str(message)+' to '+str(pid_receiver))
        self.send_events.put((pid_receiver, message))
    
    def deliver(self, pid_sender, message):
        if config['LOG'].getboolean('stubbornlink'):
            logger.info('pid:'+self.pid+' - '+'sl_deliver: delivered '+str(message)+' from '+str(pid_sender))
        if self.deliver_events != None:
            self.deliver_events.put((pid_sender,message))

    ### INTERCONNECTION
    def getDeliverEvents(self):
        self.deliver_events = queue.Queue()
        return self.deliver_events


class PerfectLink:
    """
    2.4.4 Perfect Links
    """

    def __init__(self, sl : StubbornLink) -> None:
        self.sl = sl
        self.pid = sl.pid
        self.delivered = []

        self.send_events = queue.Queue()
        self.tagged_deliver_events = {} # collect deliver events with a specific message tag
        self.deliver_events = None
        self.slDeliverEvents = self.sl.getDeliverEvents() 

        slDeliverEventHandlerThread = threading.Thread(target=handleEvents, args=(self.slDeliverEvents, self.onEventSlDeliver))
        slDeliverEventHandlerThread.start()

        plSendEventHandlerThread = threading.Thread(target=handleEvents, args=(self.send_events, self.onEventPlSend))
        plSendEventHandlerThread.start()

    ### EVENT HANDLERS
    def onEventSlDeliver(self, pid_sender, message):  
        pid_sender_message_tuple = (pid_sender, message)
        if pid_sender_message_tuple not in self.delivered:
            self.delivered.append(pid_sender_message_tuple)
            self.deliver(pid_sender_message_tuple[0], pid_sender_message_tuple[1])

    def onEventPlSend(self, pid_receiver, message):
        self.sl.send(pid_receiver,message)

    ### INTERFACES    
    def send(self, pid_receiver, message):
        self.send_events.put((pid_receiver,message))
        if config['LOG'].getboolean('perfectlink'):
            logger.info('pid:'+self.pid+' - '+'pl_send: sending '+str(message)+' to '+str(pid_receiver))
    
    def deliver(self, pid_sender, message):
        if config['LOG'].getboolean('perfectlink'):
            logger.info('pid:'+self.pid+' - '+'pl_deliver: delivered '+str(message)+' from '+str(pid_sender))
        if len(message) > 1 and isinstance(message[0],str) and message[0][:3] == 'MT:' and message[0] in self.tagged_deliver_events:
            self.tagged_deliver_events[message[1]].put((pid_sender,message))
        elif self.deliver_events != None:
            self.deliver_events.put((pid_sender,message))

    ### INTERCONNECTION
    def getDeliverEvents(self):
        self.deliver_events = queue.Queue()
        return self.deliver_events

    def getTaggedDeliverEvents(self, msg_tag : str) -> queue.Queue:
        """
            msg_tag (str) : get delivery events for a specific message tag (msg_tag DO NOT include the prefix 'MT:')
        """
        self.tagged_deliver_events['MT:'+msg_tag] = queue.Queue()
        return self.tagged_deliver_events['MT:'+msg_tag]