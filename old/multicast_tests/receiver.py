from Paxos_v3 import helper as hp
import sys
import json


# get command-line arguments
role = sys.argv[1]

readSock, multicast_group, writeSock = hp.init(role)

print("I'm {} and my address is ({})".format(sys.argv[1],multicast_group))


# Receive/respond loop
while True:
	print('\nwaiting to receive message')
	data, address = readSock.recvfrom(1024)

	print('received {} bytes from {}'.format(len(data), address))
	print(json.loads(data.decode()))
	# print(data.decode())

	print('sending acknowledgement to', hp.send_to_role("acceptors"))
	writeSock.sendto(json.dumps('ack').encode(), hp.send_to_role("acceptors"))

