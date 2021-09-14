import netifaces
import link
import random
import time
import os.path
import configparser

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
pl = link.PerfectLink(sl)

# PROTOCOL

for t in range(10):
    time.sleep(3)
    dest = random.sample(neighborID_to_addr.keys(),1)[0]
    pl.send(dest,'msg'+str(t))