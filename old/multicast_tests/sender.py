from Paxos_v3 import helper as hp
import sys
import socket
import json

# get command-line arguments
role = sys.argv[1]

readSock, multicast_group, writeSock = hp.init(role)

print("I'm {} and my address is ({})".format(sys.argv[1],multicast_group))

message = 'very important data'

dict = {}
dict["command"] = "comando1"
dict["param"] = "param1"
dict["optional"] = "opt"

try:

	# Send data to the specified multicast group
	print('sending {!r}'.format(dict))
	# sent = writeSock.sendto(message.encode(), hp.send_to_role("clients"))
	sent = writeSock.sendto(json.dumps(dict).encode(), hp.send_to_role("clients"))


	# Look for responses from all recipients
	while True:
		print('waiting to receive ack')
		try:
			data, server = readSock.recvfrom(1024)
		except socket.timeout:
			print('timed out, no more responses')
			break
		else:
			# print('received {!r} from {}'.format(data.decode(), server))
			print('received {!r} from {}'.format(json.loads(data.decode()), server))
			break

finally:
	print('closing socket')
	readSock.close()