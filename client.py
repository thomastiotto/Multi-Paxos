import helper as hp
import os
import logging
import argparse

# parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("id", type=int)
ap.add_argument("-v", "--values")
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

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)


	def run(self):

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))

		while True:
			if args["values"] is not None:
				# open input values file
				working_directory = os.getcwd()
				file_path = working_directory + args["values"]
				f = open(file_path, "r")

				if f.mode == "r":
					contents = f.read().splitlines()
					for value in contents:
						msg_proposal = hp.Message.create_proposal(self.id, value)
						self.writeSock.sendto(msg_proposal, hp.send_to_role("proposers"))
						logging.debug("Client {} \n\tSent PROPOSAL {} to Proposers".format(self.id, value))
					args["values"] = None # don't loop forever sending values from file
			else:
				value = input('\nEnter value to send to proposer:')
				msg_proposal = hp.Message.create_proposal(self.id, value)
				self.writeSock.sendto(msg_proposal, hp.send_to_role("proposers"))
				logging.debug("Client {} \n\tSent PROPOSAL {} to Proposers".format(self.id, value))



if __name__ == "__main__":

	prop = Client()
	prop.run()