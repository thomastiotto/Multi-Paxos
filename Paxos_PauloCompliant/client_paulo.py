import PaxosHelper as hp
import logging
import argparse
import sys
import time

# parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("id", type=int)
ap.add_argument("conf", type=str)
ap.add_argument("-d", "--debug")
args = vars(ap.parse_args())

# set debug level
if args["debug"] is not None:
	logging.basicConfig(level=args["debug"].upper())
logging.getLogger('apscheduler').setLevel(logging.WARNING)


class Client:

	def __init__(self):

		self.role = "clients"
		self.id = args["id"]

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role, args["conf"])


	def run(self):

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))

		for value in sys.stdin:
			value = value.strip()

			msg_proposal = hp.Message.create_proposal(self.id, value)
			self.writeSock.sendto(msg_proposal, hp.send_to_role("proposers"))

			logging.debug("Client {} \n\tSent PROPOSAL {} to Proposers".format(self.id, value))

			time.sleep(0.001)



if __name__ == "__main__":

	prop = Client()
	prop.run()