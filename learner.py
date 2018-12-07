import helper as hp
import logging
import argparse
from apscheduler.schedulers.background import BackgroundScheduler

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
			"DECISION": self.handle_decision,
			"CATCHUPLEARNER": self.handle_catchup
		}

		self.role = "learners"
		self.id = args["id"]

		self.decision_queue = []
		self.next_instance = 1

		self.catchup_queue = []

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)


	def learner_catchup(self): # TODO implementare logica di catchup, probabilmente la cosa migliore è chiedere agli acceptors la greatest instance decisa e una volta ricevuta quella da un quorum chiedere i valori fino a lì

		while all():
			logging.debug(f"Learner {self.id}\n\tCATCHUPLEARNER instance {instance_request}")

			msg_catchup = hp.Message.create_catchuplearner(instance_request, self.id)
			self.writeSock.sendto(msg_catchup, hp.send_to_role("proposers"))


	def handle_catchup(self, msg_catchup):

		self.catchup_queue.append(msg_catchup)
		self.catchup_queue = sorted(self.catchup_queue, key=lambda k: k.instance_num)



	def handle_decision(self, msg_dec):

		logging.debug("Learner {}, Instance {} \n\tReceived DECISION from Proposer {} v_val={}".format(self.id,
		                                                                                               msg_dec.instance_num,
		                                                                                               msg_dec.sender_id,
		                                                                                               msg_dec.v_val))

		# if message is the correct one then deliver it instantly else add it to a queue
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

		# sort queue by instance number and check if first element is the next one to deliver
		self.decision_queue = sorted(self.decision_queue, key=lambda k: k.instance_num)

		while len(self.decision_queue) > 0 and self.decision_queue[0].instance_num == self.next_instance:
			if args["debug"] is None:
				print(self.decision_queue[0].v_val)
			else:
				logging.debug("Learner {}, Instance {} \n\tDecided v_val={}".format(self.id,
				                                                                    self.decision_queue[0].instance_num,
				                                                                    self.decision_queue[0].v_val))
			self.next_instance += 1
			self.decision_queue.pop(0) # delete the delivered message from queue


	def receive(self):

		while True:

			# logging.debug("Learner {} \n\tWaiting for message".format(self.id))

			data, _ = self.readSock.recvfrom(1024)
			msg = hp.Message.read_message(data)
			self.switch_handler[msg.phase](msg)


	def run(self):

		catchup_sched = BackgroundScheduler()
		catchup_sched.add_job(self.receive())
		catchup_sched.start()

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))


if __name__ == '__main__':

	learner = Learner()
	learner.run()