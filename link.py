from genericpath import exists
import threading
import queue
import socket
import json
import configparser
import time
import os.path

import logging

# LOAD LOGGING CONFIGURATION
LOG_Enabled = False
if os.path.isfile('DDS.ini'):
    
    config = configparser.ConfigParser()
    config.read('DDS.ini')

    logger = logging.getLogger(config['LOG']['name'])
    logger.setLevel(int(config['LOG']['level']))
    fh = logging.FileHandler(config['LOG']['fileName'])
    logger.addHandler(fh)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    LOG_Enabled = True


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


class FairLossLink:
    """
        # 2.4.2 Fair-Loss Links
    """

    def __init__(self, pid, servicePort : int, dest_addresses) -> None:
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
        self.deliver_events = None  # (pid_source, message)
        
        linkInThread = threading.Thread(target=self.manage_link_in, args=())  # this thread should die with its parent process
        linkInThread.start()
        
        linkOutThread = threading.Thread(target=self.manage_link_out, args=())  # this thread should die with its parent process
        linkOutThread.start()     
        
        receiveThread = threading.Thread(target=self.receive_message, args=())  # this thread should die with its parent process
        receiveThread.start()


    ### LINK MANAGEMENT        
    def manage_link_in(self):
        while True: # if the socket fails, re-open
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: # TCP socket
                    s.bind(('', self.servicePort)) # the socket is reachable by any address the machine happens to have.
                    s.listen(10) # we want it to queue up as many as * connect requests before refusing outside connections. §EDIT
                    while True:
                        #if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
                        #    logger.info('pid:'+self.pid+' - '+'waiting for a new connection...')
                        conn, addr = s.accept()
                        self.to_receive.put((conn,addr))
            except Exception as ex:
                logger.debug('pid:'+self.pid+' - EXCEPTION, '+self.manage_link_in.__name__+str(type(ex))+':'+str(ex))


    def manage_link_out(self):
        while True:
            IpDestionation, message = self.to_send.get()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((IpDestionation, self.servicePort))
                    s.sendall(message)
                    if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
                        logger.info('pid:'+self.pid+' - '+'fll_send: sent '+str(message) +' to '+self.address_to_pid[IpDestionation])
            except Exception as ex: #§TO-DO proper exeception handling, except socket.error:
                logger.debug('pid:'+self.pid+' - EXCEPTION, '+self.manage_link_out.__name__+str(type(ex))+':'+str(ex)+' - '+str(IpDestionation))
            
    def receive_message(self):
        while True:
            #if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
            #    logger.info('pid:'+self.pid+' - waiting to receive a new message...')
            sock, addr = self.to_receive.get()
            try:
                with sock:
                    received_data = recvall(sock)
                    message = json.loads(received_data.decode('utf-8')) #§NOTE what about decoding errors?
                    self.deliver(self.address_to_pid[addr[0]], message['msg']) #§NOTE direct delivery
            except Exception as ex: 
                logger.debug('pid:'+self.pid+' - EXCEPTION, '+self.receive_message.__name__+str(type(ex))+':'+str(ex))  
        
    ### INTERFACES
    def send(self, pid_receiver, message):
        data_to_send = {'msg' : message} #§NOTE message needs to be convertible in JSON
        data_to_send_byte = json.dumps(data_to_send).encode('utf-8')
        self.to_send.put((self.pid_to_address[pid_receiver],data_to_send_byte))
        if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
            logger.info('pid:'+self.pid+' - '+'fll_send: sending '+str(message)+' to '+str(pid_receiver))
    
    def deliver(self, pid_sender, message):
        if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
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

    def __init__(self, fll : FairLossLink) -> None:
        self.fll = fll
        self.pid = fll.pid
        self.sent = []

        self.fllDeliverEvents = self.fll.getDeliverEvents()
        self.deliver_events = None   
        self.send_events = queue.Queue()

        # handle timeout events
        timeoutEventHandlerThread = threading.Thread(target=self.onEventTimeout, args=(30, ))  # this thread should die with its parent process
        timeoutEventHandlerThread.start()
        
        # handle fll_deliver events
        fllDeliverEventHandlerThread = threading.Thread(target=self.onEventFllDeliver, args=())  # this thread should die with its parent process
        fllDeliverEventHandlerThread.start()  

        # handle fll_deliver events
        sendEventHandlerThread = threading.Thread(target=self.onEventFlSend, args=())  # this thread should die with its parent process
        sendEventHandlerThread.start()  


    ### EVENT HANDLERS
    def onEventTimeout(self, seconds : float) -> None:
        while True:
            time.sleep(seconds)
            for pid_receiver, message in self.sent:
                self.fll.send(pid_receiver, message)


    def onEventFllDeliver(self):
        while True:
            #if config['LOG'].getboolean('stubbornlink'):
            #    logger.info('pid:'+self.pid+' - waiting deliveries')
            pid_sender, message = self.fllDeliverEvents.get()
            self.deliver(pid_sender, message)

    def onEventFlSend(self):
        while True:
            pid_receiver, message = self.send_events.get()
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
        self.tagged_deliver_events = {}
        self.deliver_events = None
        self.slDeliverEvents = self.sl.getDeliverEvents()
        
        slDeliverEventHandlerThread = threading.Thread(target=self.onEventSlDeliver, args=())  # this thread should die with its parent process
        slDeliverEventHandlerThread.start()   

        plSendEventHandlerThread = threading.Thread(target=self.onEventPlSend, args=())  # this thread should die with its parent process
        plSendEventHandlerThread.start() 


    ### EVENT HANDLERS
    def onEventSlDeliver(self):  
        while True:
            #if config['LOG'].getboolean('perfectlink'):
            #    logger.info('pid:'+self.pid+' - waiting deliveries')
            pid_sender_message_tuple = self.slDeliverEvents.get()
            if pid_sender_message_tuple not in self.delivered:
                self.delivered.append(pid_sender_message_tuple)
                self.deliver(pid_sender_message_tuple[0], pid_sender_message_tuple[1])

    def onEventPlSend(self):
        try:
            while True:
                pid_receiver,message = self.send_events.get()
                self.sl.send(pid_receiver,message)
        except Exception as ex: 
            logger.debug('pid:'+self.pid+' - EXCEPTION, '+str(type(ex))+':'+str(ex))

    ### INTERFACES    
    def send(self, pid_receiver, message):
        if config['LOG'].getboolean('perfectlink'):
            logger.info('pid:'+self.pid+' - '+'pl_send: sending '+str(message)+' to '+str(pid_receiver))
        self.send_events.put((pid_receiver,message))
    
    def deliver(self, pid_sender, message):
        if config['LOG'].getboolean('perfectlink'):
            logger.info('pid:'+self.pid+' - '+'pl_deliver: delivered '+str(message)+' from '+str(pid_sender))
        if isinstance(message,list) and len(message) > 0 and \
        isinstance(message[0],str) and len(message[0])>7 and message[0][:7] == 'MSGTAG:' \
        and message[0][7:] in self.tagged_deliver_events:
            self.tagged_deliver_events[message[0][7:]].put((pid_sender,message))
        elif self.deliver_events != None:
            self.deliver_events.put((pid_sender,message))
        # original version
        #if self.deliver_events != None:
        #    self.deliver_events.put((pid_sender,message))

    ### INTERCONNECTION
    def getDeliverEvents(self):
        self.deliver_events = queue.Queue()
        return self.deliver_events

    def getTaggedDeliverEvents(self, msg_tag : str) -> queue.Queue:
        self.tagged_deliver_events[msg_tag] = queue.Queue()
        return self.tagged_deliver_events[msg_tag]