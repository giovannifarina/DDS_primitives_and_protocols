import netifaces
import link
import random
import time
import os.path
import configparser
import logging

# load logging configuration if available
LOG_Enabled = False
if os.path.isfile('DDS.ini'):
    
    config = configparser.ConfigParser()
    config.read('DDS.ini')

    # logging §TO-CHECK
    logger = logging.getLogger(config['LOG']['name'])
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(config['LOG']['fileName'])
    logger.addHandler(fh)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    LOG_Enabled = True


# get ip in a mininet simulation
ip_addresses = [netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'] for iface in netifaces.interfaces() if netifaces.AF_INET in netifaces.ifaddresses(iface)]
for ip in ip_addresses:
    if ip != '127.0.0.1':
        break

# get pid in a mininet simulation
with open('pid_IPaddr_map.txt', 'r') as fd:
    for line in fd:
        pid, addr = line.split()
        if addr == ip:
            break

# get neighbors in a mininet simulation
neighborID_to_addr = {}
with open('outLinks.txt', 'r') as fd:
    line = fd.readline()
    if line == '* *\n':
        with open('pid_IPaddr_map.txt', 'r') as fd:
            for line in fd:
                nid, addr = line.split()
                if addr != ip:
                    neighborID_to_addr[nid] = addr
        

# setting up link
service_port = 3210
fll = link.FairLossLink(pid, service_port, neighborID_to_addr)
sl = link.StubbornLink(fll)

# PROTOCOL

for t in range(1):
    time.sleep(2)
    dest = random.sample(neighborID_to_addr.keys(),1)[0]
    sl.send(dest,'msg'+str(t))