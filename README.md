# Dependable Distributed Systems: Simulation Environment

This repository contains the simulation code presented during the course of [Dependable Distributed Computing at Sapienza Univerisità di Roma](https://bonomi.diag.uniroma1.it/teaching/a-a-2021-2022).

This framework aims at providing a simple pedagogical tool to verify correctness of distributed system protocols.

Part of the framework is based on the book:

[Christian Cachin, Rachid Guerraoui, Luís E. T. Rodrigues: **Introduction to Reliable and Secure Distributed Programming** (2. ed.). Springer 2011, ISBN 978-3-642-15259-7, pp. I-XIX, 1-367](https://doi.org/10.1007/978-3-642-15260-3)

**This documentation is currently under expansion.**

### Dependecies

This simulation environment is coded in Python and relies on [Mininet](http://mininet.org/) to setup a virtual network where to deploy the distributed protocol. The following dependencies need to be satisfied on the executing machine:

- Python 3
- [networkx](https://networkx.org/) Python module (employed in future releases)
- [Mininet](http://mininet.org/)

### How to code

### Structure

#### process.py
The module process.py contains the main code executed by every single process (virtual machine).

#### link.py
The module link.py contains the implementation of some of the link abstraction seen during the course.

The *FairLossLink* class is the software module that actually manage the network connections over Internet.
There are two implementations available:
- *FairLossLink_vTCP_simple*
- *FairLossLink_vTCP_MTC*

Both the implementations establish a TCP connection for each message to exchange.

*FairLossLink_vTCP_simple* relies on three threads managing the message exchanges: 1) one accepting all incoming connection, 2) one receiving the messages coming from open connections, 3) one sending all messages enqueue to transmit

*FairLossLink_vTCP_MTC* is an improved version of *FairLossLink_vTCP_simple* that relies on multiple threads sending and receiving messages.

Notice that both the implementations are not efficient in latency and overhead.

...

### Event Handling

### Message Format

<!---
### Reference
```
@book{DBLP:books/daglib/0025983,
  author    = {Christian Cachin and
               Rachid Guerraoui and
               Lu{\'{\i}}s E. T. Rodrigues},
  title     = {Introduction to Reliable and Secure Distributed Programming {(2.}
               ed.)},
  publisher = {Springer},
  year      = {2011},
  url       = {https://doi.org/10.1007/978-3-642-15260-3},
  doi       = {10.1007/978-3-642-15260-3},
  isbn      = {978-3-642-15259-7},
  timestamp = {Wed, 14 Nov 2018 10:12:21 +0100},
  biburl    = {https://dblp.org/rec/books/daglib/0025983.bib},
  bibsource = {dblp computer science bibliography, https://dblp.org}
}
```
-->