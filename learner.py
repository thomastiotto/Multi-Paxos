import helper as hp
import logging
import argparse

# parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("id", type=int)
ap.add_argument("-d", "--debug")
args = vars(ap.parse_args())

# set debug level
if args["debug"] is not None:
	logging.basicConfig(level=args["debug"].upper())
logging.getLogger('apscheduler').setLevel(logging.WARNING)

class Learner:

	def __init__(self):
		self.role = "learners"
		self.id = args["id"]

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)


	def run(self):

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))

		while True:

			logging.debug("Proposer {} \n\tWaiting for message".format(self.id))

			data, _ = self.readSock.recvfrom(1024)
			msg = hp.read_message(data)

			if msg["phase"] == "DECISION": # TODO implementare logica di catchup
				print("Learner {} \n\tReceived DECISION from Proposer {} v_val={}".format(self.id, msg["sender_id"], msg["v_val"]))


if __name__ == '__main__':

	learner = Learner()
	learner.run()