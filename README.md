# Multi-Paxos implementation in Python 3

**Distributed Algorithms 2018 course project - Università della Svizzera Italiana**

*Thomas Tiotto*

### Folder structure
```
.
├── README
├── core
│   ├── acceptor.py
│   ├── client.py
│   ├── learner.py
│   └── proposer.py
├── exec
│   ├── acceptor.sh
│   ├── client.sh
│   ├── learner.sh
│   └── proposer.sh
├── old # previous implementations
│   ├── Paxos_v2
│   │   └── ...
│   ├── Paxos_v3
│   │   └── ...
│   └── multicast_tests
│       └── ...
├── paxos.conf
└── ... # tests
```

The source files are found in the ```./core``` folder, the bash scripts used 
to start execution are to be found in the ```./exec``` directory and the configuration file ```paxos.conf``` 
is in the project root, together with the test launchers.

Old implementations, including multicast tests, are found in the ```./old``` folder.

### Dependencies
The only non-standard package needed to run the system is *Advanced Python Scheduler* that can be installed with:

```
pip install apscheduler
```

### Execution
From the ```./exec```  folder, a process can be started by running:

```./$ROLE$.sh $ID$ ../paxos.conf``` 

with ```$ROLE$``` one between *proposer*, *acceptor*, *learner*, *client* and ```$ID$``` a number greater than 1.
Note that in the system I assume there to be a maximum of four proposers (1 through 4) and a maximum of three acceptors 
(1 through 3).  There is an optional parameter that can be passed to print debug information, for example:
```./acceptor.sh 1 ../paxos.conf -d=debug```.

The test scripts are to be started from the root and are called with:

```./run*.sh exec $VALUES$```

with ```$VALUES$``` the number of values each client sends.

After a test has run, the results can be checked by calling:

```./check_all.sh```

### Configuration file
The system configuration is to be found in ```./paxos.conf``` and has defaults:

```
clients 239.0.0.1 5000
proposers 239.0.0.1 6000
acceptors 239.0.0.1 7000
learners 239.0.0.1 8000
```

The configuration can be changed by modifying the IP address of the system and the multicast ports assigned to each 
process role.

### Implementation details
There are five files in the project:

   - **proposer.py:** implements a process with role of Paxos Proposer
   - **acceptor.py:** implements a process with role of Paxos Acceptor
   - **learner.py:** implements a process with role of Paxos Learner
   - **PaxosHelper.py:** contains shared functionality (ex. configuration reading, Message class implementation ...)
   - **client.py:** implements a process that sends requests to the system
   
Every time a Client sends a value, the Proposer who is currently the leader is tasked with starting a new Paxos instance.
The implementation of the consensus algorithm is simple and standard.  When a majority quorum of Acceptors has accepted
a proposed value, the leader sends it as a decision to the Learners who will print the decided values in **total order**.

Following, are some implementation details of note.

#### Leader election
The dafault leader is Proposer with ID 4.  The current leader is always the alive Proposer with the highest ID.
Every second, the current leader sends a heartbeat to signal that he is still alive while, every three seconds, all other
Proposers check that the last received heartbeat is not older than 2 seconds.  If the last heartbeat has "timed out", a 
Proposer elects himself as leader but yelds this role as soon as he receives a heartbeat from another Proposer with a 
higher ID than himself.

I chose to elect the highest ID Proposer as leader so, when multiple Proposers try to propose in an instance (because the confusion 
that can happen just after a leader has died can lead multiple Proposers to elect themselves as leaders), 
the current leader will always try with the highest ```c_rnd```, as the ```c_rnd``` is defined as ```instance_num * proposer_id```,
and thus Acceptors will ignore all other Proposers. 


#### Instance synchronisation
To be sure not to run useless instances of Paxos and not to lose client proposals, when a Proposer becomes leader it 
waits to have received an *instance number confirmation* from a majority quorum of Acceptors.  When receiving such a 
request from a leader, Acceptors reply with the highest instance number they have seen; the leader then takes the maximum
among these and sets the successive instance as his starting point for new Paxos runs. 


#### Learner catchup optimisation (Learner-side)
The Learners present an optimisation on the catchup request algorithm i.e. the mechanism through
which a Learner requests a missing decision.
Every time a decision is received out-of-order, the Learner has the opportunity to ask for all missing values from the last
decision that was delivered in-order.  If a decision value in this range has already been received, it is obviously not
requested again (```self.instance_is_received()``` returns ```True```).  If it hasn't yet been received then it may
have been requested or not; if it isn't, it's added to a set of requested instances together with the current time.  If,
instead, it has already been requested (and not received as we are in the ```else``` branch) it is requested again only
if the request was sent more than 2 seconds ago.

By testing via ```./run_learner_catchup exec 50```, this catchup algorithm was seen to greatly reduce the number 
of number of requests made to Proposers.  The naïve algorithm of asking for non-received values since the last delivered
one, generated 11101 catchup requests; the optimised version generated **50**.

 
#### Learner catchup optimisation (Proposer-side) 
The naïve way to reply to a catchup request is for the current leader to propose ```None``` in the instance requested
by the Learner and return the resulting Paxos decision.  
This is very inefficient; a much better way is for every Proposer to receive a copy of every decision made by the leader
and to save it in a set.  This way when a Learner asks for a previously decided value, it can be quickly returned by reading from
the set.  

Additionally, every Proposer keeps his state synchronised by listening to every Paxos instance and evolving his state
in parallel with the leader, who will be the only one interacting with the Acceptors.

These algorithms also help in the case where the Proposer who was leader when a decision was made has now crashed, because
the newly elected leader will (hopefully) have a complete history of all previous Paxos instances and decisions.


#### Delivery
Learners must deliver decisions in total order of instance number.  Each received decision is added to the set ```self.decision_dict```
and each Learner keeps track of the last delivered instance.  When attempting to deliver, the decision set is ordered
by instance number and, if the element in the set is the next to be delivered, the pointer to the next message to deliver
is updated to the next element in the ordered set and the cycle continues until there are in-order instances.


### Implementation limitations
There may be some problem in synchronisation between Proposers when the current leader dies but this hasn't been explored.
Such a problem never arises in the tests, because a Proposer is never killed.


### Test results
Following, are the tests with the maximum number of values that the system is able to reliably pass.
The only test that fails, for any amount of values, is *Test 3 - Learners learned every value that was sent by some client* meaning 
that only liveness is violated.
- ```./run.sh exec 500```
- ```./run_catch_up.sh exec 1700```
- ```./run_1acceptor.sh exec $ANY$```
- ```./run_2acceptor.sh exec 500```

The test ```./run_loss.sh``` wan't executed as I am on a MacOS machine and thus ```iptables``` is not 
available.