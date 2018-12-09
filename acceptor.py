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


class Acceptor():

	def __init__(self):

		self.switch_handler = {
			"PHASE1A":  self.handle_1a,
			"PHASE2A":  self.handle_2a,
			"CATCHUPREQ": self.handle_catchupreq
		}

		self.role = "acceptors"
		self.id = args["id"]

		self.state = {}
		self.greatest_instance = 0

		self.readSock, self.multicast_group, self.writeSock = hp.init(self.role)


	def handle_catchupreq(self, msg_catchupreq):

		v_val_data = {}
		for key, item in self.state.items():
			v_val_data[item.instance_num] = item.v_val

		msg_catchuprepl = hp.Message.create_catchupreply(msg_catchupreq.instance_num, self.id, self.greatest_instance, v_val_data)
		self.writeSock.sendto(msg_catchuprepl, hp.send_to_role("learners"))

		return


	def handle_1a(self, msg_1a):

		logging.debug("Acceptor {}, Instance {}\n\tReceived message 1A from Proposer {} c_rnd={}".format(self.id,
		                                                                                                 msg_1a.instance_num,
		                                                                                                 msg_1a.sender_id,
		                                                                                                 msg_1a.c_rnd))

		instance = msg_1a.instance_num

		# start logging new instance
		self.state[instance] = hp.Instance(instance, self.id) # TODO check se istanza esiste già
		instance_state = self.state[instance]

		if msg_1a.c_rnd > instance_state.rnd:
			instance_state.rnd = msg_1a.c_rnd

			# msg_1b = hp.create_message(instance_num=instance ,sender_id=self.id, phase="PHASE1B", rnd=instance_state.rnd, v_rnd=instance_state.v_rnd, v_val=instance_state.v_val)
			msg_1b = hp.Message.create_1b(instance, self.id, instance_state.rnd, instance_state.v_rnd, instance_state.v_val)
			self.writeSock.sendto(msg_1b, hp.send_to_role("proposers"))

			logging.debug("Acceptor {}, Instance {}\n\tSent message 1B to Proposer {} rnd={} v_rnd={} v_val={}".format(self.id, instance, msg_1a.sender_id, instance_state.rnd, instance_state.v_rnd, instance_state.v_val))

		return


	def handle_2a(self, msg_2a):

		logging.debug("Acceptor {}, Instance {} \n\tReceived message 2A from Proposer {} c_rnd={} c_val={}".format(self.id, msg_2a.instance_num, msg_2a.sender_id, msg_2a.c_rnd, msg_2a.c_val))

		instance = msg_2a.instance_num
		instance_state = self.state[instance]

		# discard old proposals
		if msg_2a.c_rnd >= instance_state.rnd:
			instance_state.v_rnd = msg_2a.c_rnd
			instance_state.v_val = msg_2a.c_val

			# save largest instance to send to learners in CATCHUPREPL
			if msg_2a.instance_num >= self.greatest_instance:
				self.greatest_instance = msg_2a.instance_num

			msg_2b = hp.Message.create_2b(instance, self.id, instance_state.v_rnd, instance_state.v_val)
			self.writeSock.sendto(msg_2b, hp.send_to_role("proposers"))

			logging.debug("Acceptor {}, Instance {} \n\tSent message 2B to Proposer {} v_rnd={} v_val={}".format(self.id, instance, msg_2a.sender_id, instance_state.v_rnd, instance_state.v_val))

		return


	def run(self):

		logging.debug("I'm {} and my address is ({})".format(self.role, self.multicast_group))

		while True:

			# logging.debug("Acceptor {} \n\tWaiting for message".format(self.id))

			data, _ = self.readSock.recvfrom(1024)
			msg = hp.Message.read_message(data)
			self.switch_handler[msg.phase](msg)


if __name__ == "__main__":

	acceptor = Acceptor()
	acceptor.run()