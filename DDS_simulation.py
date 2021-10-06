# From https://github.com/mininet/mininet/wiki/Introduction-to-Mininet

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink
#from mininet.node import CPULimitedHost

import configparser
import logging

config = configparser.ConfigParser()
config['LOG'] = {}
config['LOG']['level'] = str(logging.DEBUG)
config['LOG']['fairlosslink'] = 'true'
config['LOG']['stubbornlink'] = 'true'
config['LOG']['perfectlink'] = 'true'
config['LOG']['perfectfailuredector'] = 'true'
config['LOG']['name'] = 'DDS'
config['LOG']['fileName'] = 'DDS.log'
with open('DDS.ini', 'w') as configfile:
    config.write(configfile)

from DDSlogger import logger

# generate a distributed system composed by n hosts all connected to a single switch
class SingleSwitchTopo(Topo):
    "Single switch connected to n hosts."
    def build(self, n=2):
        switch = self.addSwitch('s1')
        # Python's range(N) generates 0..N-1
        for h in range(n):
            host = self.addHost('h%s' % (h + 1))
            self.addLink(host, switch, bw=10, delay='150ms', loss=0)

# generate configuration files for mininet simulations
#§NOTE it currently handle only complete communication networks
def generateProcessConfigurationFiles(net):
    with open('pid_IPaddr_map.txt', 'w') as fd:
        pid = 0
        for host in net.hosts:
            fd.write(str(pid)+' '+str(host.IP())+'\n') #§NOTE it can fail with multiple IP addresses
            pid += 1
    with open('outLinks.txt', 'w') as fd:
        fd.write('* *\n') # encoding for fully connected communication network

def simpleTest():
    "Create and test a simple network"
    topo = SingleSwitchTopo(n=4)
    net = Mininet(topo=topo, link=TCLink)
    net.start()
    generateProcessConfigurationFiles(net)
    for host in net.hosts:
        host.cmd('python3 process.py &') # run process.py on host
    CLI(net)
    net.stop()


if __name__ == '__main__':
    # Tell mininet to print useful information
    setLogLevel('info')
    simpleTest()
    
