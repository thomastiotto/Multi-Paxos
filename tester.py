import helper as hp
import time

readSock, multicast_group, writeSock = hp.init("proposers")

msg_decision = hp.Message.create_decision(5, 666, "ste")
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(2)

msg_decision = hp.Message.create_decision(2, 666, "kebab")
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(2)

msg_decision = hp.Message.create_decision(4, 666, "ano")
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(2)

msg_decision = hp.Message.create_decision(1, 666, "culo")
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(2)

msg_decision = hp.Message.create_decision(3, 666, "alice")
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

# readSock, multicast_group, writeSock = hp.init("clients")
#
# msg = hp.Message.create_proposal(666, 7)
# writeSock.sendto(msg, hp.send_to_role("proposers"))
