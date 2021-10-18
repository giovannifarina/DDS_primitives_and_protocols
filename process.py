import netifaces
import random
import time
import os.path
import configparser
from DDSlogger import logger

import link
import failure_detector

# HARDWARE DEPENDENT CONFIGURATION

# get ip in a mininet simulation
ip_addresses = [netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'] for iface in netifaces.interfaces() if netifaces.AF_INET in netifaces.ifaddresses(iface)]
for ip in ip_addresses:
    if ip != '127.0.0.1':
        break

processes = []
# get pid in a mininet simulation
with open('pid_IPaddr_map.txt', 'r') as fd:
    for line in fd:
        pid_i, addr_i = line.split()
        if addr_i == ip:
            pid = pid_i
        processes.append(pid_i)
processes = tuple(processes)

# get neighbors in a mininet simulation
neighborID_to_addr = {}
with open('outLinks.txt', 'r') as fd:
    line = fd.readline()
    if line == '* *\n':
        with open('pid_IPaddr_map.txt', 'r') as fd:
            for line in fd:
                nid, addr = line.split()
                #if addr != ip:
                neighborID_to_addr[nid] = addr
        
# SETTING UP PRIMITIVES

# setting up link
service_port = 3210
fll = link.FairLossLink_vTCP_simple(pid, service_port, neighborID_to_addr) # Implementation 1 of ffl
#fll = link.FairLossLink_vTCP_MTC(pid, service_port, neighborID_to_addr, n_threads_in=1, n_threads_out=2) # Implementation 2 of ffl
#sl = link.StubbornLink(fll, 30)
#pl = link.PerfectLinkOnStubborn(sl=sl)
pl = link.PerfectLinkPingPong(fll, timeout = 5)
P = failure_detector.PerfectFailureDetector(processes=processes, timeout=15, pl=pl)

# PROTOCOL
"""
counter = 0
while True:
    if pid == '0':
        time.sleep(5)
        dest = str(counter%len(neighborID_to_addr))
        #fll.send(dest,['Hello!'])
        #sl.send(dest,['Hello!'])
        pl.send(dest,['MID:'+str(counter), 'Hello!'])
        counter += 1
"""