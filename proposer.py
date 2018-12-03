import helper as hp
import time
from apscheduler.schedulers.background import BackgroundScheduler
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

# TODO il leader si deve salvare i messaggi dei clients in una coda

class Proposer:

	def __init__(self):

		self.QUORUM_SIZE = 2

		self.switch_handler = {
			"PROPOSAL":    self.handle_proposal,
			"PHASE1A":     None,
			"PHASE1B":     self.handle_1b,
			"PHASE2A":     None,
			"PHASE2B":     self.handle_2b,
			"DECISION":    self.handle_decision,
			"LEADERALIVE": self.handle_leader_alive
		}

		self.role = "proposers"
		self.id = args["id"]
		self.c_rnd = 0
		self.v = None

		#leader election stuff
		self.last_leader = 1 #default leader is the one with id 1
		self.last_leader_alive_msg = None

		self.state = {} # TODO implementare stato usando dizionario indicizzato per istanza

		self.v_rnd_received_1b = [] #TODO da sistemare i buffer
		self.v_val_received_1b = []
		self.largest_v_rnd = None
		self.v_rnd_received_2b = []

		# setup sockets
		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)


	def handle_proposal(self, msg_prop):

		# global c_rnd, v, largest_v_rnd, v_rnd_received_1b, v_val_received_1b, v_rnd_received_2b

		# proposer's proposal
		self.v = msg_prop["v_val"]

		# start new instance with round 0 # TODO farlo
		self.c_rnd = time.time() # TODO time non va bene!  usare interi da 0

		# reset memory for new round
		self.v_rnd_received_1b = []
		self.v_val_received_1b = []
		self.largest_v_rnd = None
		self.v_rnd_received_2b = []

		logging.debug("Proposer {} \n\tReceived message PROPOSAL from Client {} v_val={}".format(self.id, msg_prop["sender_id"], self.v))

		msg_1a = hp.create_message(sender_id=self.id, phase="PHASE1A", c_rnd=self.c_rnd)
		self.writeSock.sendto(msg_1a, hp.send_to_role("acceptors"))

		logging.debug("Proposer {} \n\tSent message 1A to Acceptors c_rnd={} v_val={}".format(self.id, self.c_rnd, self.v))

		return


	def handle_1b(self, msg_1b):

		# global largest_v_rnd, v_rnd_received_1b, c_val, v_val_received_1b # TODO refactor

		# only look at messages addressed to me and for current round
		# if msg_1b["sender_id"] != self.id or msg_1b["rnd"] != self.c_rnd:
		# 	return

		logging.debug("Proposer {} \n\tReceived message 1B from Acceptor sender_id={} rnd={} v_rnd={} v_val={}".format(self.id, msg_1b["sender_id"], msg_1b["rnd"], msg_1b["v_rnd"], msg_1b["v_val"]))

		# record messages in this round
		self.v_rnd_received_1b.append(msg_1b["v_rnd"])
		self.v_val_received_1b.append(msg_1b["v_val"])

		# if we have enough messages
		if len(self.v_rnd_received_1b) >= self.QUORUM_SIZE:

			# find largest v_rnd and save its index in the list
			k = max(self.v_rnd_received_1b)
			k_index = self.v_rnd_received_1b.index(k)

			if k == 0:
				msg_2a = hp.create_message(phase="PHASE2A", sender_id=self.id, c_rnd=self.c_rnd, c_val=self.v)
			else:
				# use index of largest v_rnd to get the corresponding v_val
				msg_2a = hp.create_message(phase="PHASE2A", sender_id=self.id, c_rnd=self.c_rnd, c_val=self.v_val_received_1b[k_index])

			self.writeSock.sendto(msg_2a, hp.send_to_role("acceptors"))

			logging.debug("Proposer {} \n\tSent message 2A to Acceptors c_rnd={} c_val={}".format(self.id, self.c_rnd, self.v_val_received_1b[k_index]))

		return


	def handle_2b(self, msg_2b):

		# global v_rnd_received_2b, v_val_received_2b # TODO refactor

		# only look at messages addressed to me and for current round
		# if msg_2b["sender_id"] != self.id:
		# 	return

		logging.debug("Proposer {} \n\tReceived message 2B from Acceptor {} v_rnd={} v_val={}".format(self.id, msg_2b["sender_id"],
		                                                                                      msg_2b["v_rnd"], msg_2b["v_val"]))

		# record messages in this round
		self.v_rnd_received_2b.append(msg_2b["v_rnd"])

		# if we have enough messages
		if len(self.v_rnd_received_2b) >= self.QUORUM_SIZE:
			if all(item == self.c_rnd for item in self.v_rnd_received_2b):
				msg_decision = hp.create_message(sender_id=self.id, phase="DECISION", v_val=msg_2b["v_val"])
				self.writeSock.sendto(msg_decision, hp.send_to_role("learners"))

				logging.debug("Proposer {} \n\tSent message DECISION to Learners v_val={}".format(self.id, msg_2b["v_val"]))

		return


	def handle_decision(self, msg):
		return

	#################################################################
	# Begin leader election
	#################################################################

	# Save the last LEADERALIVE message received
	def handle_leader_alive(self, msg_alive):

		if msg_alive["sender_id"] == self.id: # don't save own leader alive messages or risk never yelding
			return
		else:
			self.last_leader_alive_msg = msg_alive

		return


	# The current leader sends a LEADERALIVE heartbeat
	def leader_send_alive(self):

		if self.is_leader():
			# logging.debug("Time {}\tLeader {} \n\tSending LEADERALIVE".format(int(time.time()),self.id))

			msg_alive = hp.create_message(sender_id=self.id, phase="LEADERALIVE", time=time.time())
			self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

		return


	# All other proposers check that the leader is still alive by looking at last LEADERALIVE received
	def leader_check_alive(self):

		# If I never received a LEADERALIVE then proposer 1 was never started or crashed so I elect myself
		if self.last_leader_alive_msg == None:
			if not self.is_leader():
				logging.debug("Time {}\tProposer {} \n\tNo current leader".format(int(time.time()),self.id, self.last_leader))
				logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()),self.id, self.id))

			self.last_leader = self.id  # elect myself as new leader

			msg_alive = hp.create_message(sender_id=self.id, phase="LEADERALIVE", time=time.time())
			self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

			# add faux LEADERALIVE message
			# self.last_leader_alive_msg = hp.read_message(hp.create_message(sender_id=self.id, phase="LEADERALIVE", time=time.time()+2))

			return

		leader_timeout = time.time() - self.last_leader_alive_msg["time"] # check time passed since last LEADERALIVE

		# if last LEADERALIVE message is older than 3s I elect myself as leader
		if leader_timeout > 3:
			if not self.is_leader():
				logging.debug("Time {}\tProposer {} \n\tLeader timeout".format(int(time.time()),self.id, self.last_leader))
				logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()),self.id, self.id))

			self.last_leader = self.id  # elect myself as new leader

			msg_alive = hp.create_message(sender_id=self.id, phase="LEADERALIVE", time=time.time())
			self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

			return
		else:
			# if last LEADERALIVE sender has greater ID than me I elect myself
			if self.id < self.last_leader_alive_msg["sender_id"]:
				if not self.is_leader():
					logging.debug("Time {}\tProposer {} \n\tI'm smallest proposer".format(int(time.time()), self.id, self.last_leader))
					logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()),self.id, self.id))

				self.last_leader = self.id  # elect myself as new leader

				msg_alive = hp.create_message(sender_id=self.id, phase="LEADERALIVE", time=time.time())
				self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))
			else:
				if not self.is_leader():
					logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()), self.id, self.last_leader_alive_msg["sender_id"]))
				self.last_leader = self.last_leader_alive_msg["sender_id"]

				return


	def is_leader(self):

		if self.last_leader == self.id:
			return True
		else:
			return False


	#################################################################
	# End leader election
	#################################################################


	def run(self):

		# the current leader sends a heartbeat every second to say it's still alive
		alive_sched = BackgroundScheduler()
		alive_sched.add_job(self.leader_send_alive, 'interval', seconds = 1)
		alive_sched.start()

		# check that the leader is still alive
		check_alive_sched = BackgroundScheduler()
		check_alive_sched.add_job(self.leader_check_alive, 'interval', seconds=3)
		check_alive_sched.start()

		logging.debug("I'm {} {} and my address is ({})".format(self.role, self.id, self.multicast_group))

		while True:

			# logging.debug("Proposer {} \n\tWaiting for message".format(self.id))

			data, _ = self.readSock.recvfrom(1024)
			msg = hp.read_message(data)
			# handle message with correct function
			self.switch_handler[msg["phase"]](msg)


if __name__ == "__main__":

	proposer = Proposer()
	proposer.run()
