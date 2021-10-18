# From https://github.com/mininet/mininet/wiki/Introduction-to-Mininet

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink
#from mininet.node import CPULimitedHost

import networkx as nx
from ipaddress import IPv4Network

import configparser
import logging

# logger configuration
config = configparser.ConfigParser()
config['LOG'] = {}
config['LOG']['level'] = str(logging.DEBUG)
config['LOG']['fairlosslink'] = 'false'
config['LOG']['stubbornlink'] = 'false'
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

class ThreeHosts(Topo):

    def build(self):
        h1 = self.addHost('h1', ip='192.168.0.1/30')
        h2 = self.addHost('h2', ip='192.168.0.2/30')
        h3 = self.addHost('h3', ip='192.168.0.6/30')

        self.addLink(h1,h2)
        self.addLink(h1,h3, intfName1='h1-eth1', params1={ 'ip' : '192.168.0.5/30' })
        self.addLink(h2,h3, intfName1='h2-eth1', params1={ 'ip' : '192.168.0.9/30' }, intfName2='h3-eth1', params2={ 'ip' : '192.168.0.10/30' })


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

def simpleTest(n_processes):
    "Create and test a simple network"
    topo = SingleSwitchTopo(n=n_processes)
    net = Mininet(topo=topo, link=TCLink)
    net.start()
    generateProcessConfigurationFiles(net)
    #for host in net.hosts:
    #    host.cmd('python3 process.py &') # run process.py on host
    CLI(net)
    net.stop()

def simpleTest2():
    topo = ThreeHosts()
    net = Mininet(topo=topo, link=TCLink)
    net.start()
    """
    generateProcessConfigurationFiles(net)
    for host in net.hosts:
        host.cmd('python3 process.py &') # run process.py on host
    """
    CLI(net)
    net.stop()

def testNetworkxTopology():
    G = nx.cycle_graph(10)
    for i in range(3):
        for node in G.nodes:
            for edge in G.edges(node):
                print(node,edge)
        print()

if __name__ == '__main__':
    # Tell mininet to print useful information
    setLogLevel('info')
    #simpleTest(n_processes=5) 
    #simpleTest2()
    testNetworkxTopology()