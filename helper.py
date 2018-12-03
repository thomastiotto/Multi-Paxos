import socket
import struct
import os
import json

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


def create_message(sender_id, receiver_id=None, instance_num=None, rnd=None, phase=None, c_rnd=None, c_val=None, v_rnd=None,
                   v_val=None, time=None):
	msg = (sender_id, receiver_id, instance_num, rnd, phase, c_rnd, c_val, v_rnd, v_val, time)

	return json.dumps(msg).encode()


def read_message(data):
	msg = json.loads(data.decode())
	msg_contents = {
		"sender_id":    msg[0],
		"receiver_id":  msg[1],
		"instance_num": msg[2],
		"rnd":          msg[3],
		"phase":        msg[4],
		"c_rnd":        msg[5],
		"c_val":        msg[6],
		"v_rnd":        msg[7],
		"v_val":        msg[8],
		"time":         msg[9]
	}

	return msg_contents


# def create_instance(inst_dict, instance, v):
#
# 	new_instance = instance + 1
# 	inst_dict[new_instance] = {}
# 	inst_dict[new_instance]["v"] = v
# 	inst_dict[new_instance]["c_rnd"] = 1
# 	inst_dict[new_instance]["V"] = (None, None)
# 	inst_dict[new_instance]["c_val"] = None
#
# 	return inst_dict


class Instance():

	instance = 0

	def __init__(self, v):

		self.id = Instance.instance
		self.v = v
		self.c_rnd = 1
		self.V = (None, None)
		self.c_val = None

		Instance.instance = Instance.instance + 1


