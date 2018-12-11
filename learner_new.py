import helper as hp
import logging
import argparse
from apscheduler.schedulers.background import BackgroundScheduler
import time
from collections import defaultdict

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
			"DECISION": self.handle_decision
		}

		self.role = "learners"
		self.id = args["id"]

		self.decision_dict = {}
		self.last_received = 0
		self.last_delivered = 0
		self.max_received = 0

		self.catching_up = True
		self.catchup_instance = 0
		self.catchup_store = []
		self.last_instance_round = 0

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)

		# self.catchup_request()

		self.run()

	# self.greatest_instance = self.get_greatest_instance()

	#################################################################
	# Begin catchup values
	#################################################################

	def catchup_request(self, catchup_instance):

		if self.catching_up:
			logging.debug("Time {}\tLearner {} \n\tSending CATCHUPREQ for instance {}".format(int(time.time()), self.id,
			                                                                                  catchup_instance))

			msg_catchupreq = hp.Message.create_catchuprequest(catchup_instance, self.id)
			self.writeSock.sendto(msg_catchupreq, hp.send_to_role("proposers"))

		return

	def handle_decision(self, msg_dec):

		logging.debug("Learner {}, Instance {} \n\tReceived DECISION from Proposer {} v_val={}".format(self.id,
		                                                                                               msg_dec.instance_num,
		                                                                                               msg_dec.sender_id,
		                                                                                               msg_dec.v_val))

		self.last_received = msg_dec.instance_num
		self.decision_dict[msg_dec.instance_num] = msg_dec

		self.deliver()

		# nag for missing values every time
		for inst in range(self.last_delivered, self.last_received):
			if not self.instance_is_received(inst):
				self.catchup_request(inst)

	def instance_is_received(self, instance):

		if instance in self.decision_dict:
			return True
		else:
			return False

	def deliver(self):

		for next_decision in sorted(self.decision_dict.keys()):
			# decide on value if it's the next one I'm expecting
			if next_decision == self.last_delivered + 1:
				self.last_delivered += 1

				if args["debug"] is None:
					print(self.decision_dict[next_decision].v_val)
				else:
					logging.debug("Learner {} \n\tInstance {}, decided {}".format(self.id,
					                                                              next_decision,
					                                                              self.decision_dict[
						                                                              next_decision].v_val))

	def check_all_received(self):

		for inst in self.decision_dict:
			if not self.instance_is_received(inst):
				self.catchup_request(inst)

		self.deliver()

		return

	#################################################################
	# End catchup values
	#################################################################

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

		# periodically check if all messages are received and nag if not
		received_sched = BackgroundScheduler()
		received_sched.add_job(self.check_all_received(), 'interval', seconds=1)
		received_sched.start()

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))


if __name__ == '__main__':
	learner = Learner()
# learner.run()
