from genericpath import exists
import threading
import queue
import socket
import json
import configparser
import time
import os.path

import logging

# load logging configuration if available
LOG_Enabled = False
if os.path.isfile('DDS.ini'):
    
    config = configparser.ConfigParser()
    config.read('DDS.ini')

    # logging §TO-CHECK
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
        self.delivered_queue = queue.Queue()  # (pid_source, message)
        
        linkInThread = threading.Thread(target=self.manage_link_in, args=())  # this thread should die with its parent process
        linkInThread.start()
        
        linkOutThread = threading.Thread(target=self.manage_link_out, args=())  # this thread should die with its parent process
        linkOutThread.start()     
        
        receiveThread = threading.Thread(target=self.receive_message, args=())  # this thread should die with its parent process
        receiveThread.start()

        
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
                logger.debug('pid:'+self.pid+' - EXCEPTION, '+self.manage_link_out.__name__+str(type(ex))+':'+str(ex))


    def manage_link_out(self):
        while True:
            IpDestionation, message = self.to_send.get()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((IpDestionation, self.servicePort))
                    s.sendall(message)
                    if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
                        logger.info('pid:'+self.pid+' - '+'fl_send: sent '+str(message) +' to '+self.address_to_pid[IpDestionation])
            except Exception as ex: #§TO-DO proper exeception handling, except socket.error:
                logger.debug('pid:'+self.pid+' - EXCEPTION, '+self.manage_link_out.__name__+str(type(ex))+':'+str(ex)+' - '+str(IpDestionation))
            
    #§CHECK
    def receive_message(self):
        while True:
            #if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
            #    logger.info('pid:'+self.pid+' - waiting to receive a new message...')
            sock, addr = self.to_receive.get()
            try:
                with sock:
                    received_data = recvall(sock)
                    message = json.loads(received_data.decode('utf-8')) #§NOTE what about decoding errors?
                    self.deliver(self.address_to_pid[addr[0]], message) #§NOTE direct delivery
            except Exception as ex: 
                logger.debug('pid:'+self.pid+' - EXCEPTION, '+self.manage_link_out.__name__+str(type(ex))+':'+str(ex))  
        
    def send(self, pid_receiver, message):
        data_to_send = {'msg' : message} #§NOTE message needs to be convertible in JSON
        data_to_send_byte = json.dumps(data_to_send).encode('utf-8')
        self.to_send.put((self.pid_to_address[pid_receiver],data_to_send_byte))
        if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
            logger.info('pid:'+self.pid+' - '+'ffl_send: sending '+str(message)+' to '+str(pid_receiver))
    
    def deliver(self, pid_sender, message):
        if LOG_Enabled and config['LOG'].getboolean('fairlosslink'):
            logger.info('pid:'+self.pid+' - '+'fl_deliver: delivered '+str(message)+' from '+str(pid_sender))
        self.delivered_queue.put((pid_sender,message))


class StubbornLink:
    """
        2.4.3 Stubborn Links
    """

    def __init__(self, fll : FairLossLink) -> None:
        self.fll = fll
        self.pid = fll.pid
        self.sent = []

        stubbornSendingThread = threading.Thread(target=self.starttimer, args=(5, ))  # this thread should die with its parent process
        stubbornSendingThread.start()
        
        getFLDeliveriesThread = threading.Thread(target=self.getFLDeliveries, args=())  # this thread should die with its parent process
        getFLDeliveriesThread.start()  

        self.delivered_queue = None   


    def starttimer(self, seconds : float) -> None:
        while True:
            time.sleep(seconds)
            for pid_receiver, message in self.sent:
                self.fll.send(pid_receiver, message)

    def getFLDeliveries(self):
        while True:
            #if config['LOG'].getboolean('stubbornlink'):
            #    logger.info('pid:'+self.pid+' - waiting deliveries')
            pid_sender, message = self.fll.delivered_queue.get()
            self.deliver(pid_sender, message)

        
    def send(self, pid_receiver, message):
        if config['LOG'].getboolean('stubbornlink'):
            logger.info('pid:'+self.pid+' - '+'sl_send: sending '+str(message)+' to '+str(pid_receiver))
        self.fll.send(pid_receiver,message)
        self.sent.append((pid_receiver,message))
    
    def deliver(self, pid_sender, message):
        if config['LOG'].getboolean('stubbornlink'):
            logger.info('pid:'+self.pid+' - '+'sl_deliver: delivered '+str(message)+' from '+str(pid_sender))
        if self.delivered_queue != None:
            self.delivered_queue.put((pid_sender,message))

    def getDeliveries(self):
        self.delivered_queue = queue.Queue()
        return self.delivered_queue

class PerfectLink:
    """
    2.4.4 Perfect Links
    """

    def __init__(self, sl : StubbornLink) -> None:
        self.sl = sl
        self.pid = sl.pid
        self.delivered = []
        
        getSLDeliveriesThread = threading.Thread(target=self.getSLDeliveries, args=())  # this thread should die with its parent process
        getSLDeliveriesThread.start()     


    def getSLDeliveries(self):
        slDeliveriesQueue = self.sl.getDeliveries()
        while True:
            #if config['LOG'].getboolean('perfectlink'):
            #    logger.info('pid:'+self.pid+' - waiting deliveries')
            pid_sender_message_tuple = slDeliveriesQueue.get()
            if pid_sender_message_tuple not in self.delivered:
                self.delivered.append(pid_sender_message_tuple)
                self.deliver(pid_sender_message_tuple[0], pid_sender_message_tuple[1])
        
    def send(self, pid_receiver, message):
        if config['LOG'].getboolean('perfectlink'):
            logger.info('pid:'+self.pid+' - '+'pl_send: sending '+str(message)+' to '+str(pid_receiver))
        self.sl.send(pid_receiver,message)
    
    def deliver(self, pid_sender, message):
        if config['LOG'].getboolean('perfectlink'):
            logger.info('pid:'+self.pid+' - '+'pl_deliver: delivered '+str(message)+' from '+str(pid_sender))