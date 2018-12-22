import PaxosHelper as hp
import time
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import argparse

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


class Proposer:

	def __init__(self):

		self.switch_handler = {
			"PROPOSAL":    self.handle_proposal,
			"PHASE1B":     self.handle_1b,
			"PHASE2B":     self.handle_2b,
			"LEADERALIVE": self.handle_leader_alive,
			"CATCHUPREQ":  self.handle_catchupreq,
			"INSTANCEREPL": self.handle_instancerepl,
			"DECISION":      self.handle_decision
		}

		self.role = "proposers"
		self.id = args["id"]

		# leader election stuff
		self.last_leader = 4  # default leader is the one with greatest id
		self.last_leader_alive_msg = None
		self.leader_print_flag = True # used to limit outputs when a proposer is not leader

		# instance stuff
		self.state = {}
		self.instance = None
		self.last_instance = 0
		self.last_instance_dict = {}
		self.instance_received = False # when True, the Proposer has received the greatest instance from a quorum of Acceptors

		# save decisions for cheap replies to learners
		self.past_decisions = {}

		# setup sockets
		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role, args["conf"])

		if self.id == hp.NUM_PROPOSERS:
			self.get_greatest_instance()

	# each proposer keeps track of decided value in each instance so it can quickly send it to a Learner who is catching up
	def handle_decision(self, msg_decision):

		logging.debug(f"Proposer {self.id} \n\tReceived message DECISION from Leader {msg_decision.sender_id} v_val={msg_decision.v_val}")

		# save decision for future quick catchup replies
		self.past_decisions[msg_decision.instance_num] = msg_decision.v_val

		return

	# reply to a Learner catchup request
	def handle_catchupreq(self, msg_catchupreq):

		logging.debug(f"Proposer {self.id} \n\tReceived message CATCHUPREQ from Learner {msg_catchupreq.sender_id} for instance {msg_catchupreq.instance_num}")

		# if we already have a quick decision saved, send it to the Learner or else start a new instance of Paxos
		if self.is_leader() and self.instance_received and msg_catchupreq.instance_num in self.past_decisions:
			msg_decision = hp.Message.create_decision(msg_catchupreq.instance_num, self.id, self.past_decisions[msg_catchupreq.instance_num])
			self.writeSock.sendto(msg_decision, hp.send_to_role("learners"))

			logging.debug(f"Proposer {self.id}, Instance {msg_catchupreq.instance_num} \n\tSent quick reply to Learners v_val={self.past_decisions[msg_catchupreq.instance_num]}")
		else:
			# create new instance or overwrite it (we don't need info saved in old instance)
			old_c_rnd = self.state[msg_catchupreq.instance_num].c_rnd
			self.state[msg_catchupreq.instance_num] = hp.Instance(msg_catchupreq.instance_num, self.id, old_c_rnd + hp.NUM_PROPOSERS, None) # the c_rnd is guaranteed to be larger than the last, so the Acceptros will reply

			if self.is_leader() and self.instance_received:
				msg_1a = hp.Message.create_1a(msg_catchupreq.instance_num, self.id, old_c_rnd + hp.NUM_PROPOSERS)
				self.writeSock.sendto(msg_1a, hp.send_to_role("acceptors"))

			logging.debug(f"Proposer {self.id}, Instance {msg_catchupreq.instance_num} \n\tSent message 1A to Acceptors c_rnd={old_c_rnd + hp.NUM_PROPOSERS}")

		return

	# handle a proposal request from a Client by starting a new instance of Paxos
	def handle_proposal(self, msg_prop):

		# start new instance with c_rnd=my_id*instance_number and v as proposal
		self.state[self.last_instance] = hp.Instance(self.last_instance, self.id, None, msg_prop.v_val)

		logging.debug("Proposer {} \n\tReceived message PROPOSAL from Client {} v_val={}".format(self.id,
		                                                                                         msg_prop.sender_id,
		                                                                                         msg_prop.v_val))

		if self.is_leader() and self.instance_received:
			msg_1a = hp.Message.create_1a(self.last_instance, self.id, self.state[self.last_instance].c_rnd)
			self.writeSock.sendto(msg_1a, hp.send_to_role("acceptors"))

			logging.debug(
					"Proposer {}, Instance {} \n\tSent message 1A to Acceptors c_rnd={}".format(self.id, self.last_instance,
					                                                                            self.state[self.last_instance].c_rnd))
		self.last_instance += 1

		return

	def handle_1b(self, msg_1b):

			logging.debug(
				"Proposer {}, Instance {} \n\tReceived message 1B from Acceptor {} rnd={} v_rnd={} v_val={}".format(
					self.id,
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
			if instance_state.quorum_1b >= hp.QUORUM_SIZE:

				# send the client's value if no previous values are present in Acceotors
				if instance_state.largest_v_rnd == 0:
					v = instance_state.v
				else:
					# send largest v_val received in this instance
					v = instance_state.largest_v_val

				if self.is_leader() and self.instance_received:
					msg_2a = hp.Message.create_2a(instance, self.id, instance_state.c_rnd, v)
					self.writeSock.sendto(msg_2a, hp.send_to_role("acceptors"))

					logging.debug(
						"Proposer {}, Instance {} \n\tSent message 2A to Acceptors c_rnd={} c_val={}".format(self.id,
						                                                                                     instance,
						                                                                                     instance_state.c_rnd,
						                                                                                     v))

			return

	def handle_2b(self, msg_2b):

		logging.debug(
			"Proposer {}, Instance {} \n\tReceived message 2B from Acceptor {} v_rnd={} v_val={}".format(self.id,
			                                                                                             msg_2b.instance_num,
			                                                                                             msg_2b.sender_id,
			                                                                                             msg_2b.v_rnd,
			                                                                                             msg_2b.v_val))

		instance = msg_2b.instance_num
		instance_state = self.state[instance]

		# record messages in this round
		instance_state.quorum_2b.append(msg_2b)

		# if we have a quorum of messages with v_rnd = c_rnd then we can decide
		if sum(instance_state.c_rnd == item.v_rnd for item in instance_state.quorum_2b) >= hp.QUORUM_SIZE:
			# find the first element with c_rnd = v_rnd to get its v_val
			v = next((x for x in instance_state.quorum_2b if x.v_rnd == instance_state.c_rnd), None)

			if self.is_leader() and self.instance_received:
				msg_decision = hp.Message.create_decision(instance, self.id, v.v_val)
				self.writeSock.sendto(msg_decision, hp.send_to_role("learners"))
				self.writeSock.sendto(msg_decision, hp.send_to_role("proposers"))

				logging.debug("Proposer {}, Instance {} \n\tSent message DECISION to Learners and Proposers v_val={}".format(self.id,
			                                                                                               instance,
			                                                                                               v.v_val))

		return

	#################################################################
	# Begin leader election
	#################################################################

	# handle request to get the latest instance, seen by a quorum of Acceptors
	def handle_instancerepl(self, msg_instancerepl):

		logging.debug(f"Proposer {self.id} \n\tReceived message INSTANCEREPL from Acceptor {msg_instancerepl.sender_id} with instance {msg_instancerepl.instance_num}")

		if msg_instancerepl.sender_id not in self.last_instance_dict: # check that acceptor ids are unique
			self.last_instance_dict[msg_instancerepl.sender_id] = msg_instancerepl.instance_num

		# if received enough replies then extract the maximum instance seen by acceptors
		if len(self.last_instance_dict) >= hp.QUORUM_SIZE:
			self.last_instance = max(self.last_instance_dict.values()) + 1
			self.last_instance_dict = {}
			self.instance_received = True # leader is now ready to run Paxos

			logging.debug(f"Proposer {self.id} \n\tStarting from instance {self.last_instance}")

		return

	# request greatest instance from acceptors when becoming leader
	def get_greatest_instance(self):

		logging.debug(f"Proposer {self.id} \n\tSent message INSTANCEREQ")

		msg_greatestinstance = hp.Message.create_instancereq(self.id)
		self.writeSock.sendto(msg_greatestinstance, hp.send_to_role("acceptors"))

		return

	# save the last LEADERALIVE message received to check for leader timeout
	def handle_leader_alive(self, msg_alive):

		if msg_alive.sender_id == self.id:  # don't save own leader alive messages or risk never yelding
			return
		else:
			self.last_leader_alive_msg = msg_alive

		return

	# the current leader sends a LEADERALIVE heartbeat
	def leader_send_alive(self):

		if self.is_leader():
			# logging.debug("Time {}\tLeader {} \n\tSending LEADERALIVE".format(int(time.time()),self.id))

			# send LEADERALIVE adding the last instance that this leader has started
			msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
			self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

		return

	# all other proposers check that the leader is still alive by looking at last LEADERALIVE received
	def leader_check_alive(self):

		# check if the current leader has received enough instance messages to run Paxos
		if self.is_leader() and not self.instance_received:
			self.get_greatest_instance()

		# if I never received a LEADERALIVE then proposer 4 was never started or crashed so I elect myself
		if self.last_leader_alive_msg == None:
			if not self.is_leader():
				logging.debug(
					"Time {}\tProposer {} \n\tNo current leader".format(int(time.time()), self.id, self.last_leader))
				logging.debug(
					"Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()), self.id, self.id))

				self.last_leader = self.id  # elect myself as new leader
				self.get_greatest_instance()
				self.leader_print_flag = True

				msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
				self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

			return

		# if last LEADERALIVE message is older than 3s I elect myself as leader
		if hp.Message.has_timedout(self.last_leader_alive_msg, 3):
			if not self.is_leader():
				logging.debug(
					"Time {}\tProposer {} \n\tLeader timeout".format(int(time.time()), self.id, self.last_leader))
				logging.debug(
					"Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()), self.id, self.id))

				self.last_leader = self.id  # elect myself as new leader
				self.get_greatest_instance()
				self.leader_print_flag = True

				msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
				self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))

			return
		else:
			# if last LEADERALIVE sender has smaller ID than me I elect myself
			if self.id > self.last_leader_alive_msg.sender_id:
				if not self.is_leader():
					logging.debug("Time {}\tProposer {} \n\tI'm largest proposer".format(int(time.time()), self.id,
					                                                                     self.last_leader))
					logging.debug(
						"Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()), self.id, self.id))

					self.last_leader = self.id  # elect myself as new leader
					self.get_greatest_instance()
					self.leader_print_flag = True

					msg_alive = hp.Message.create_leaderalive(self.last_instance, self.id)
					self.writeSock.sendto(msg_alive, hp.send_to_role("proposers"))
			else:
				if not self.is_leader():
					if self.leader_print_flag:
						logging.debug("Time {}\tProposer {} \n\tProposer {} is now leader".format(int(time.time()), self.id,
					                                                                          self.last_leader_alive_msg.sender_id))
						self.leader_print_flag = False

				self.last_leader = self.last_leader_alive_msg.sender_id

				return

	# return True if I am leader
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
		alive_sched.add_job(self.leader_send_alive, 'interval', seconds=1)
		alive_sched.start()

		# check that the leader is still alive
		check_alive_sched = BackgroundScheduler()
		check_alive_sched.add_job(self.leader_check_alive, 'interval', seconds=3)
		check_alive_sched.start()

		logging.debug("I'm {} {} and my address is ({})".format(self.role, self.id, self.multicast_group))

		while True:
			# logging.debug("Proposer {} \n\tWaiting for message".format(self.id))

			data, _ = self.readSock.recvfrom(65536)
			msg = hp.Message.read_message(data)
			# handle message with correct function
			self.switch_handler[msg.phase](msg)


if __name__ == "__main__":
	proposer = Proposer()
	proposer.run()
