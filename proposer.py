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

# TODO i proposer devono scambiarsi lo state così se uno crasha gli altri ricominciano dall'istanza corretta?

class Proposer:

	def __init__(self):

		self.QUORUM_SIZE = 2

		self.switch_handler = {
			"PROPOSAL":    self.handle_proposal,
			"PHASE1A":     None,
			"PHASE1B":     self.handle_1b,
			"PHASE2A":     None,
			"PHASE2B":     self.handle_2b,
			"DECISION":    None,
			"LEADERALIVE": self.handle_leader_alive
		}

		self.role = "proposers"
		self.id = args["id"]

		#leader election stuff
		self.leader_number = 4
		self.last_leader = self.leader_number # default leader is the one with greatest id
		self.last_leader_alive_msg = None

		# instance stuff
		self.state = {}
		self.instance = None # TODO se un leader muore gli altri dovrebbero ricominciare dall'ultima istanza
		self.last_instance = 0

		# setup sockets
		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)


	def handle_proposal(self, msg_prop):

		self.last_instance += 1

		if self.is_leader():
			# start new instance with c_rnd=my_id*instance_number and v as proposal
			self.state[self.last_instance] = hp.Instance(self.last_instance, self.id, msg_prop.v_val)

			logging.debug("Proposer {} \n\tReceived message PROPOSAL from Client {} v_val={}".format(self.id,
			                                                                                         msg_prop.sender_id,
			                                                                                         msg_prop.v_val))

			msg_1a = hp.Message.create_1a(self.last_instance, self.id, self.state[self.last_instance].c_rnd)
			self.writeSock.sendto(msg_1a, hp.send_to_role("acceptors"))

			logging.debug("Proposer {}, Instance {} \n\tSent message 1A to Acceptors c_rnd={}".format(self.id, self.last_instance, self.state[self.last_instance].c_rnd))

		return


	def handle_1b(self, msg_1b):

		# only look at messages addressed to me and for current round
		# if msg_1b["sender_id"] != self.id or msg_1b["rnd"] != self.c_rnd:
		# 	return
		if self.is_leader():
			logging.debug("Proposer {}, Instance {} \n\tReceived message 1B from Acceptor {} rnd={} v_rnd={} v_val={}".format(self.id,
			                                                                                                                  msg_1b.instance_num,
			                                                                                                                  msg_1b.sender_id,
			                                                                                                                  msg_1b.rnd,
			                                                                                                                  msg_1b.v_rnd,
			                                                                                                                  msg_1b.v_val))

		instance = msg_1b.instance_num
		instance_state = self.state[instance]

		if instance_state.c_rnd == msg_1b.rnd:
			instance_state.quorum_1b += 1

		# save largest (v_rnd, v_val) tuple
		if msg_1b.v_rnd >= instance_state.largest_v_rnd:
			instance_state.largest_v_rnd = msg_1b.v_rnd
			instance_state.largest_v_val = msg_1b.v_val

		# if we have enough messages
		if instance_state.quorum_1b >= self.QUORUM_SIZE:

			# send the client's value if not previous values are present
			if instance_state.largest_v_rnd == 0:
				v = instance_state.v
			else:
				# send largest v_val received in this instance
				v = instance_state.largest_v_val

			msg_2a = hp.Message.create_2a(instance, self.id, instance_state.c_rnd, v)
			self.writeSock.sendto(msg_2a, hp.send_to_role("acceptors"))

			logging.debug("Proposer {}, Instance {} \n\tSent message 2A to Acceptors c_rnd={} c_val={}".format(self.id,
			                                                                                                    instance,
				                                                                                                instance_state.c_rnd,
				                                                                                                v))

		return


	def handle_2b(self, msg_2b): # TODO anche se non è leader deve registrarsi l'ultima istanza per rimanere sincronizzato

		# only look at messages addressed to me and for current round
		# if msg_2b["sender_id"] != self.id:
		# 	return

		logging.debug("Proposer {}, Instance {} \n\tReceived message 2B from Acceptor {} v_rnd={} v_val={}".format(self.id,
		                                                                                                           msg_2b.instance_num,
		                                                                                                           msg_2b.sender_id,
		                                                                                                           msg_2b.v_rnd,
		                                                                                                           msg_2b.v_val))
		instance = msg_2b.instance_num
		instance_state = self.state[instance]

		# record messages in this round
		instance_state.quorum_2b.append(msg_2b)

		# if we have a quorum of messages with v_rnd = c_rnd then we can decide
		if sum(instance_state.c_rnd == item.v_rnd for item in instance_state.quorum_2b) >= self.QUORUM_SIZE:

			# find the first element with c_rnd = v_rnd to get its v_val
			v = next((x for x in instance_state.quorum_2b if x.v_rnd == instance_state.c_rnd), None)

			msg_decision = hp.Message.create_decision(instance, self.id, v.v_val)
			self.writeSock.sendto(msg_decision, hp.send_to_role("learners"))

			logging.debug("Proposer {}, Instance {} \n\tSent message DECISION to Learners v_val={}".format(self.id,
			                                                                                               instance,
			                                                                                               v.v_val))

		return


	#################################################################
	# Begin leader election
	#################################################################

	# TODO ogni proposer deve tenere traccia dell'ultima istanza decisa in modo da poter ricominciare da lì se diventa leader

	# Save the last LEADERALIVE message received
	def handle_leader_alive(self, msg_alive):

		if msg_alive.sender_id == self.id: # don't save own leader alive messages or risk never yelding
			return
		else:
			self.last_leader_alive_msg = msg_alive

		return


	# The current leader sends a LEADERALIVE heartbeat
	def leader_send_alive(self):

		if self.is_leader():
			# logging.debug("Time {}\tLeader {} \n\tSending LEADERALIVE".format(int(time.time()),self.id))

			# send LEADERALIVE adding the last instance this leader has started
			msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
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

			msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
			self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

			return

		leader_timeout = time.time() - self.last_leader_alive_msg.time # check time passed since last LEADERALIVE

		# if last LEADERALIVE message is older than 3s I elect myself as leader
		if leader_timeout > 3:
			if not self.is_leader():
				logging.debug("Time {}\tProposer {} \n\tLeader timeout".format(int(time.time()),self.id, self.last_leader))
				logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()),self.id, self.id))

			self.last_leader = self.id  # elect myself as new leader

			msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
			self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

			return
		else:
			# if last LEADERALIVE sender has smaller ID than me I elect myself
			if self.id > self.last_leader_alive_msg.sender_id:
				if not self.is_leader():
					logging.debug("Time {}\tProposer {} \n\tI'm largest proposer".format(int(time.time()), self.id, self.last_leader))
					logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()),self.id, self.id))

				self.last_leader = self.id  # elect myself as new leader

				msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
				self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))
			else:
				if not self.is_leader():
					logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()), self.id, self.last_leader_alive_msg.sender_id))
				self.last_leader = self.last_leader_alive_msg.sender_id

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
			msg = hp.Message.read_message(data)
			# handle message with correct function
			self.switch_handler[msg.phase](msg)


if __name__ == "__main__":

	proposer = Proposer()
	proposer.run()
