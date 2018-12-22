import socket
import struct
import sys

multicast_group = '224.3.29.71'
port = 10000
server_address = ('', port)

# Create the socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except AttributeError:
	pass  # Some systems don't support SO_REUSEPORT
sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 20)
sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)

# Bind to the server address
sock.bind(server_address)

# Tell the operating system to add the socket to the multicast group
# on all interfaces.
group = socket.inet_aton(multicast_group)
mreq = struct.pack('4sL', group, socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

# Receive/respond loop
while True:
	print(sys.stderr, '\nwaiting to receive message')
	data, address = sock.recvfrom(1024)

	print(sys.stderr, 'received %s bytes from %s' % (len(data), address))
	print(sys.stderr, data.decode())

	print(sys.stderr, 'sending acknowledgement to', address)
	sock.sendto('ack'.encode(), address)