import socket
import struct
import os
import pickle
import time

role_ports = {"clients":   0,
              "proposers": 0,
              "acceptors": 0,
              "learners":  0
              }

multicast_address = ""

first_setup = True


def init(role):
	global first_setup

	if first_setup:
		read_conf()
		first_setup = False

	return multicast_setup(multicast_address, role_ports[role])  # return sockets



# setup receiving multicast socket and a socket used to send data to other roles
def multicast_setup(address, port):
	multicast_group = (address, port)

	# Create the datagram socket
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

	# Set the time-to-live for messages to 1 so they do not
	# go past the local network segment.
	sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))

	# Reuse address to test on localhost
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	# add the process to the multicast group
	sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
	                struct.pack('4sL', socket.inet_aton(multicast_address), socket.INADDR_ANY))

	# non-blocking socket
	# sock.settimeout(0.2)

	# bind to multicast socket
	sock.bind((address, port))

	# Create the datagram socket
	sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

	# Set the time-to-live for messages to 1 so they do not
	# go past the local network segment.
	sock2.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))

	# non-blocking socket
	sock2.settimeout(0.2)

	return sock, multicast_group, sock2


# multicast to particular role
def send_to_role(role):
	return (multicast_address, role_ports[role])


# read parameters from configuration file
def read_conf():
	# open configuration file
	working_directory = os.getcwd()
	file_path = working_directory + '/conf.txt'
	f = open(file_path, "r")

	if f.mode == "r":
		contents = f.read().splitlines()
		for i in contents:  # populate role_ports dictionary
			role, address, port = i.split(" ")
			role_ports[role] = int(port)

			global multicast_address  # set multicast IP address
			multicast_address = address


class Message():

	def __init__(self, instance_num, sender_id, phase, receiver_id=None, rnd=None, c_rnd=None, c_val=None, v_rnd=None, v_val=None, time=None):
		self.instance_num = instance_num
		self.sender_id = sender_id
		self.phase = phase
		self.receiver_id = receiver_id
		self.rnd = rnd
		self.c_rnd = c_rnd
		self.c_val = c_val
		self.v_rnd = v_rnd
		self.v_val = v_val
		self.time = time


	@classmethod
	def create_proposal(cls, sender_id, v_val):
		instance = -1
		msg = cls(instance, sender_id, "PROPOSAL", v_val=v_val)

		return pickle.dumps(msg)

	@classmethod
	def create_1a(cls, instance, sender_id, c_rnd):
		msg = cls(instance, sender_id, "PHASE1A", c_rnd=c_rnd)

		return pickle.dumps(msg)

	@classmethod
	def create_1b(cls, instance, sender_id, rnd, v_rnd, v_val):
		msg = cls(instance, sender_id, "PHASE1B", rnd=rnd, v_rnd=v_rnd, v_val=v_val)

		return pickle.dumps(msg)

	@classmethod
	def create_2a(cls, instance, sender_id, c_rnd, v):
		msg = cls(instance, sender_id, "PHASE2A", c_rnd=c_rnd, c_val=v)

		return pickle.dumps(msg)

	@classmethod
	def create_2b(cls, instance, sender_id, v_rnd, v_val):
		msg = cls(instance, sender_id, "PHASE2B", v_rnd=v_rnd, v_val=v_val)

		return pickle.dumps(msg)

	@classmethod
	def create_decision(cls, instance, sender_id, v_val):
		msg = cls(instance, sender_id, "DECISION", v_val=v_val)

		return pickle.dumps(msg)

	@classmethod
	def create_leaderalive(cls, instance, sender_id):
		msg = cls(instance, sender_id, "LEADERALIVE", time=time.time())

		return pickle.dumps(msg)

	@classmethod
	def create_catchuprequest(cls, instance, sender_id):
		msg = cls(instance, sender_id, "CATCHUPREQ", time=time.time())

		return pickle.dumps(msg)

	@classmethod
	def create_catchupreply(cls, instance, sender_id, v_val):
		msg = cls(instance, sender_id, "CATCHUPREPL", time=time.time(), v_val=v_val)

		return pickle.dumps(msg)

	@staticmethod
	def read_message(data):
		msg = pickle.loads(data)

		return msg


class Instance():

	def __init__(self, instance, proc_id=None, v=None):

		self.instance_num = instance

		###### PROPOSER ######
		self.v = v
		self.c_rnd = proc_id * instance
		self.c_val = None
		self.largest_v_rnd = 0
		self.largest_v_val = None
		self.quorum_1b = 0
		self.quorum_2b = []

		###### ACCEPTOR ######
		self.v_val = None
		self.v_rnd = 0
		self.rnd = 0