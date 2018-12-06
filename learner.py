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
		self.switch_handler = {
			"PROPOSAL": None,
			"PHASE1A":  None,
			"PHASE1B":  None,
			"PHASE2A":  None,
			"PHASE2B":  None,
			"DECISION": self.handle_decision
		}

		self.role = "learners"
		self.id = args["id"]

		self.decision_queue = []
		self.next_instance = 1

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)



	def handle_decision(self, msg_dec): # TODO implementare logica di catchup

		logging.debug("Learner {}, Instance {} \n\tReceived DECISION from Proposer {} v_val={}".format(self.id,
		                                                                                               msg_dec.instance_num,
		                                                                                               msg_dec.sender_id,
		                                                                                               msg_dec.v_val))


		if msg_dec.instance_num == self.next_instance:
			if args["debug"] is None:
				print(msg_dec.v_val)
			else:
				logging.debug("Learner {}, Instance {} \n\tDecided v_val={}".format(self.id,
				                                                                    msg_dec.instance_num,
				                                                                    msg_dec.v_val))
			self.next_instance += 1
		else:
			self.decision_queue.append(msg_dec) # add message to the queue

		self.decision_queue = sorted(self.decision_queue, key=lambda k: k.instance_num)

		while len(self.decision_queue) > 0 and self.decision_queue[0].instance_num == self.next_instance:
			if args["debug"] is None:
				print(self.decision_queue[0].v_val)
			else:
				logging.debug("Learner {}, Instance {} \n\tDecided v_val={}".format(self.id,
				                                                                    self.decision_queue[0].instance_num,
				                                                                    self.decision_queue[0].v_val))
			self.next_instance += 1
			self.decision_queue.pop(0)


	def run(self):

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))

		while True:

			# logging.debug("Learner {} \n\tWaiting for message".format(self.id))

			data, _ = self.readSock.recvfrom(1024)
			msg = hp.Message.read_message(data)
			self.switch_handler[msg.phase](msg)


if __name__ == '__main__':

	learner = Learner()
	learner.run()