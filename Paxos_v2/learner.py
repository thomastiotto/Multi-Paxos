from Paxos_v3 import helper as hp
import logging
import argparse
from apscheduler.schedulers.background import BackgroundScheduler
import time

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

		self.QUORUM_SIZE = 2
		self.NUM_ACCEPTORS = 3

		self.switch_handler = {
			"DECISION": self.handle_decision,
			"CATCHUPREPL": self.handle_catchup_reply
		}

		self.role = "learners"
		self.id = args["id"]

		self.decision_queue = []
		self.next_instance = 1

		self.catching_up = True
		self.catchup_instance = 0
		self.catchup_store = []
		self.last_instance_round = 0

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)

		self.catchup_request()

		self.run()

		# self.greatest_instance = self.get_greatest_instance()


	#################################################################
	# Begin catchup values
	#################################################################


	def catchup_request(self):

		if self.catching_up:
			logging.debug("Time {}\tLearner {} \n\tSending CATCHUPREQ".format(int(time.time()), self.id))

			self.catchup_instance += 1
			msg_catchupreq = hp.Message.create_catchuprequest(self.catchup_instance, self.id)
			self.writeSock.sendto(msg_catchupreq, hp.send_to_role("acceptors"))
			self.catchup_store = []

		return


	def handle_catchup_reply(self, msg_catchuprepl):

		if self.catching_up:

			if msg_catchuprepl.v_rnd >= self.last_instance_round:
				self.last_instance_round = msg_catchuprepl.v_rnd

			if msg_catchuprepl.instance_num == self.catchup_instance:
				logging.debug(f"Time {int(time.time())}\tLearner {self.id} \n\tReceived CATCHUREPL from Acceptor {msg_catchuprepl.sender_id}")
				for key, item in msg_catchuprepl.v_val.items():
					logging.debug(f"{item}")

				if msg_catchuprepl.v_val: # don't save empty dict
					self.catchup_store.append(msg_catchuprepl)

				if len(self.catchup_store) >= self.QUORUM_SIZE:

					catchup_union = {}
					for item in self.catchup_store:
						catchup_union.update(item.v_val)

					for key, item in catchup_union.items():
						fake_decision = hp.Message.create_decision(key, -1, item)
						self.decision_queue.append(hp.Message.read_message(fake_decision))

				self.deliver_decision()

			return


	#################################################################
	# End catchup values
	#################################################################


	def deliver_decision(self):

		# sort queue by instance number and check if first element is the next one to deliver
		self.decision_queue = sorted(self.decision_queue, key=lambda k: k.instance_num)

		while len(self.decision_queue) > 0 and self.decision_queue[0].instance_num == self.next_instance:

			if self.catching_up and self.decision_queue[0].instance_num == self.last_instance_round:
				self.catching_up = False

			if args["debug"] is None:
				print(self.decision_queue[0].v_val)
			else:
				logging.debug("Learner {}, Instance {} \n\tDecided v_val={}".format(self.id,
				                                                                    self.decision_queue[0].instance_num,
				                                                                    self.decision_queue[0].v_val))
			self.next_instance += 1
			self.decision_queue.pop(0)  # delete the delivered message from queue

		return


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

		self.deliver_decision()


	def receive(self):

		while True:

			# logging.debug("Learner {} \n\tWaiting for message".format(self.id))

			data, _ = self.readSock.recvfrom(65536)
			msg = hp.Message.read_message(data)
			self.switch_handler[msg.phase](msg)


	def run(self):

		catchup_sched = BackgroundScheduler()
		catchup_sched.add_job(self.receive())
		catchup_sched.start()

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))






if __name__ == '__main__':

	learner = Learner()
	# learner.run()