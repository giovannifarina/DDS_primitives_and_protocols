# Dependable Distributed Systems: Simulation Environment

This repository contains the simulation framework presented during the course of [Dependable Distributed Computing at Sapienza Univerisità di Roma](https://bonomi.diag.uniroma1.it/teaching/a-a-2021-2022).

This framework aims at providing a pedagogical tool to verify correctness of distributed system protocols.

Part of the framework is based on the book:

[Christian Cachin, Rachid Guerraoui, Luís E. T. Rodrigues: **Introduction to Reliable and Secure Distributed Programming** (2. ed.). Springer 2011, ISBN 978-3-642-15259-7, pp. I-XIX, 1-367](https://doi.org/10.1007/978-3-642-15260-3)

**<span style="color:red">This documentation is currently under expansion.</span>**

### Dependencies

This simulation environment is coded in Python and relies on [Mininet](http://mininet.org/) to setup a virtual network where to deploy distributed protocols. The following dependencies need to be satisfied on the executing machine:

- Python 3
<!--- - [networkx](https://networkx.org/) Python module (employed in future releases) -->
- [Mininet](http://mininet.org/)

### Structure

#### [process.py](https://github.com/giovannifarina/DDS_primitives_and_protocols/blob/main/process.py)
The module *process.py* contains the code executed by every single process (virtual machine).

#### [link.py](https://github.com/giovannifarina/DDS_primitives_and_protocols/blob/main/link.py)
The module *link.py* contains the implementation of some of the link abstractions seen during the course.

The *FairLossLink* classes are software module that actually manage the network connections over Internet, implementing a fair-loss link abstraction.
There are two implementations available:
- *FairLossLink_vTCP_simple*
- *FairLossLink_vTCP_MTC*

Both the implementations establish a TCP connection for each message to exchange.

*FairLossLink_vTCP_simple* relies on three threads managing the message exchanges: 1) one accepting all incoming connection, 2) one receiving the messages coming from open connections, 3) one sending all messages enqueue to transmit

*FairLossLink_vTCP_MTC* is an improved version of *FairLossLink_vTCP_simple* that relies on multiple threads sending and receiving messages.

Notice that both the implementations are not efficient in latency and overhead.

The *StubbornLink* class implements a stubborn link abstraction.

The *PerfectLink* class implements a perfect link abstraction. 
Notice that the implementation compares messages through the '==' operator. Two messages carrying the same contents are thus assumed equivalent and additional content (e.g. an identifier) could be necessary to distinguish two messages equivalent in contents but semantically different.

#### [DS_simulation.py](https://github.com/giovannifarina/DDS_primitives_and_protocols/blob/main/DS_simulation.py)
The module *DS_simulation.py* orchestrates the simulation.

Specifically:
- it deploys the virtual network via mininet
- it generates the network information that will be retrieved by the processes setting up their network connections
- it starts the protocol execution on every virtual machine
- it waits for mininet commands


#### [eventHandler.py](https://github.com/giovannifarina/DDS_primitives_and_protocols/blob/main/eventHandler.py)

The module *eventHadler.py* supports event-driven programming (details below).

#### [DDSLogger.py](https://github.com/giovannifarina/DDS_primitives_and_protocols/blob/main/DDSlogger.py)

The module *DDSlogger.py* supports logging functionalities (details below).

### Event Handling
The pseudo-codes analyzed in the course are defined following the event-driven programming paradigm. 

An [event](https://en.wikipedia.org/wiki/Event_(computing)) is an action or occurrence recognized by software that may be handled by the software.

An event in the framework is a tuple containing information.
Events are exchanged (between their producers and consumers) through Python [queue](https://docs.python.org/3/library/queue.html). Every queue collects a single kind of event. When an event is triggered, the related information is collected inside a tuple and stored in the related queue.

An event handler is a function taking care of processing a specific event.
The module [eventHandler.py](https://github.com/giovannifarina/DDS_primitives_and_protocols/blob/main/eventHandler.py) defines the function *handleEvents(eventQueue, handlerFunction)* that contineously pops an event from the *eventQueue* and delivers it (i.e. executes) the event handler *handlerFunction*.
The *handlerFunction* must have a parameter for every information stored inside an event (the information inside the event are passed as parameters to the *handlerFunction* in the same order they are stored in tuple).

**To setup the event handling, a thread for each type of event needs to be started.** Each of such thread runs the *handleEvents* function with arguments the specific event handler and queue.

### Message Format

Messages are represented by Python lists.
The FairLossLink implementations store the message (list) inside a JSON object and encode it in UTF-8 before sending. The framework supports the following data types as message content: int, str, float, list, dict, True, False, None ([reference](https://docs.python.org/3/library/json.html#encoders-and-decoders)).

<!--
Distributed applications may exchange several kind of messages. To cope with this need, the first element of a message may store a message tag. A message tag is a str having the prefix 'MT:', such as 'MT:REQUEST' or 'MT:RESPONSE'.
-->

### Logging

The simulation framework integrates a logging primitive enabling to track the distributed protocol progress and to facilitate debugging.

A Python module that wants to access the logger has to execute the following line

```
from DDSlogger import logger
```

The logger is then accessible through the methods

```
logger.debug()
logger.info()
logger.warning()
logger.error()
logger.critical()
``` 

with different logging levels ([reference](https://docs.python.org/3/library/logging.html)).

The logger configuration is set in [DS_simulation.py](https://github.com/giovannifarina/DDS_primitives_and_protocols/blob/main/DS_simulation.py) that generates a configuration files *DDS.ini*.
You can declare arbistrary flags to tune the logging behavior (see 'fairlosslink', 'stubbornlink', etc. flags).

The logger outputs all the logs inside *DDS.log* file.
The file is wiped at every execution of *DS_simulation.py*.

**Note that *print* command is not effective.**

### How to code
At the current state, every process is able to communicate with any other process by default.

1. in *DS_simulation.py* edit the *n_processes* parameter of the function call *simpleTest* to set the number of processes/virtual machine to deploy.
2. in *DS_simulation.py* edit the logger flag to setup the logger behaviour (after the comment 'logger configuration').
3. in *process.py* edit after the comments 'SETTING UP PRIMITIVES' and 'PROTOCOL' to setup the primitives to deploy and the protocol to execute
4. Define new protocols/modules!

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
