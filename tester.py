from Paxos_PauloCompliant import helper as hp
import time
import argparse
from apscheduler.schedulers.background import BackgroundScheduler
import datetime as dt

ap = argparse.ArgumentParser()
ap.add_argument("conf", type= str)
args = vars(ap.parse_args())



count = 0

readSock, multicast_group, writeSock = hp.init("proposers", args["conf"])


def count_messages():

	global count

	while True:
		data, _ = readSock.recvfrom(65536)
		msg = hp.Message.read_message(data)
		if msg.phase == "CATCHUPREQ":
			count += 1
		print(f"Total CATCHUPREQ received: {count}")


sched = BackgroundScheduler()
sched.add_job(count_messages)
sched.start()

time.sleep(2)

for i in reversed(range(100)):

	time.sleep(0.0001)
	print(f"Sent decision {i}")
	msg_decision = hp.Message.create_decision(i, 666, i)
	writeSock.sendto(msg_decision, hp.send_to_role("learners"))






