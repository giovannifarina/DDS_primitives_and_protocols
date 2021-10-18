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
    """
        This class builds a mininet topology where all processes are connected to a single switch
    """
    def build(self, n=2):
        switch = self.addSwitch('s1')
        # Python's range(N) generates 0..N-1
        for h in range(n):
            host = self.addHost('%s' % (h + 1))
            #self.addLink(host, switch, bw=10, delay='150ms', loss=0)
            self.addLink(host, switch)

class subnetwork_generator():
    """
        This class provides pair of IPs to assign to a bidirectional link endpoints
    """
    
    def __init__(self) -> None:
        self.forth_block = 0
        self.third_block = 0
        self.base_addr = '192.168.'
    
    # it supports up to 16384 edges
    def getIPaddrPair(self):
        if self.forth_block == 256 and self.third_block == 255:
            raise RuntimeError('No more available addresses')
        if self.forth_block == 256:
            self.third_block += 1
            self.forth_block = 0
        self.forth_block += 1
        firstAddr = self.base_addr+str(self.third_block)+'.'+str(self.forth_block)
        self.forth_block += 1
        secondAddr = self.base_addr+str(self.third_block)+'.'+str(self.forth_block)
        self.forth_block += 2
        return (firstAddr, secondAddr)

class CustomTopology(Topo):

    def __init__(self, ngraph : nx.Graph, *args, **params):
        self.ngraph = ngraph
        super().__init__(*args, **params)

    def build(self):  

        map_id_host = {}
        for node in self.ngraph:
            map_id_host[node] = self.addHost(str(node))

        for u, v in self.ngraph.edges:
            self.addLink(map_id_host[u], map_id_host[v])



# generate configuration files for mininet simulations
def generateProcessConfigurationFilesComplete(net):
    with open('pid_IPaddr_map.txt', 'w') as fd:
        pid = 0
        for host in net.hosts:
            fd.write(str(pid)+' '+str(host.IP())+'\n') #§NOTE it can fail with multiple IP addresses
            pid += 1
    with open('outLinks.txt', 'w') as fd:
        fd.write('* *\n') # encoding for fully connected communication network

def generateProcessConfigurationFiles(G : nx.Graph):
    with open('pid_IPaddr_map.txt', 'w') as fd:
        for node in G.nodes:
            ips = []
            for u,v in G.edges(node):
                if u < v:
                    ips.append(G.edges[u, v]['addresses'][0])
                else:
                    ips.append(G.edges[u, v]['addresses'][1])
            ips_line = " ".join(ips)
            fd.write(str(node)+' '+ips_line+'\n')
    with open('outLinks.txt', 'w') as fd:
        for node in G.nodes:
            neighbors = []
            for u,v in G.edges(node):
                if u < v:
                    neighbors.append(str(v)+':'+G.edges[u, v]['addresses'][1])
                else:
                    neighbors.append(str(v)+':'+G.edges[u, v]['addresses'][0])
            fd.write(str(node)+' '+" ".join(neighbors)+'\n') 


def TestOnCompleteTopologySingleSwitch(n_processes):
    topo = SingleSwitchTopo(n=n_processes)
    net = Mininet(topo=topo, link=TCLink)
    net.start() # starts controller and switch
    generateProcessConfigurationFilesComplete(net)
    for host in net.hosts:
        host.cmd('python3 process.py &') # run process.py on host
    CLI(net)
    net.stop()

def TestOnCustomTopology(G : nx.Graph):
    G = nx.convert_node_labels_to_integers(G) # help in automatically assingn interger pid
    assignIPtoGraph(G) # generate IP configurations

    topo = CustomTopology(G)
    net = Mininet(topo=topo, link=TCLink)
    #net.start()

    generateProcessConfigurationFiles(G)

    # ASSIGN IPs
    for host in net.hosts:
        counter = 0
        for u,v in G.edges(int(host.name)):
            IPaddrs = G.edges[u, v]['addresses']
            if u > v:
                IPaddrs = (IPaddrs[1], IPaddrs[0])
            host.cmd('ifconfig '+host.name+'-eth'+str(counter)+' '+IPaddrs[0]+' netmask 255.255.255.252')
            counter += 1  
    for host in net.hosts:          
        host.cmd('python3 process.py &') # run process.py on host

    CLI(net)
    net.stop()

def assignIPtoGraph(G):
    """
        Add an attribute on every edges containing a pair of IPs
    """
    sg = subnetwork_generator()
    for u,v in G.edges:
        G.edges[u, v]['addresses'] = sg.getIPaddrPair()
    """
    for u in G.nodes:
        for _,v in G.edges(u):
            if u < v:
                G.nodes[u]['IP'] = G.edges[u, v]['addresses'][0]
            else:
                G.nodes[u]['IP'] = G.edges[u, v]['addresses'][1]
            break
    """


if __name__ == '__main__':
    setLogLevel('info') # mininet logger
    
    # Complete topology on single switch
    TestOnCompleteTopologySingleSwitch(n_processes=3)
    
    # Custom Topology
    # Some graph topology generators are available at https://networkx.org/documentation/stable/reference/generators.html
    # You can define your own topology defining and populating a nx.Graph()
    #G = nx.cycle_graph(5) # ring topology
    #TestOnCustomTopology(G)
