import netifaces
import random
import time
import os.path
import configparser
from DDSlogger import logger

import link
import failure_detector

# HARDWARE DEPENDENT CONFIGURATION

# get one of the VM' IPs in a mininet simulation
ip_addresses = [netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'] for iface in netifaces.interfaces() if netifaces.AF_INET in netifaces.ifaddresses(iface)]
for ip in ip_addresses:
    if ip != '127.0.0.1':
        break

processes = []
# get pid in a mininet simulation
with open('pid_IPaddr_map.txt', 'r') as fd:
    for line in fd:
        line_content = line.split()
        pid_i = line_content[0]
        addrs_i = line_content[1:]
        if ip in addrs_i:
            pid = pid_i
        processes.append(pid_i)
processes = tuple(processes)

# get neighbors in a mininet simulation
neighborID_to_addr = {}
with open('outLinks.txt', 'r') as fd:
    for line in fd:
        if line == '* *\n':
            with open('pid_IPaddr_map.txt', 'r') as fd:
                for line in fd:
                    nid, addr = line.split()
                    #if addr != ip:
                    neighborID_to_addr[nid] = addr
            break
        else:
            line_content = line.split()
            if line_content[0] == pid:
                for npid_naddr in line_content[1:]:
                    npid, nadd = npid_naddr.split(':')
                    neighborID_to_addr[npid] = nadd
                break
neighborID_to_addr[pid] = '127.0.0.1'
logger.debug(str(pid)+' : '+str(neighborID_to_addr))

# SETTING UP PRIMITIVES

# setting up link
service_port = 3210
fll = link.FairLossLink_vTCP_simple(pid, service_port, neighborID_to_addr) # Implementation 1 of ffl
#fll = link.FairLossLink_vTCP_MTC(pid, service_port, neighborID_to_addr, n_threads_in=1, n_threads_out=2) # Implementation 2 of ffl
#sl = link.StubbornLink(fll, 30)
#pl = link.PerfectLinkOnStubborn(sl=sl)
pl = link.PerfectLinkPingPong(fll, timeout = 5)
P = failure_detector.PerfectFailureDetector(processes=processes, timeout=20, pl=pl)

# PROTOCOL

"""
counter = 0
while True:
    if pid == '0':
        for npid in neighborID_to_addr:
            time.sleep(5)
            pl.send(npid,['MID:'+str(counter), 'Hello!'])
        counter += 1
"""