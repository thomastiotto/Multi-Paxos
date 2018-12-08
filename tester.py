import helper as hp
import time

# readSock, multicast_group, writeSock = hp.init("clients")
#
# msg = hp.Message.create_proposal(666, 7)
# writeSock.sendto(msg, hp.send_to_role("proposers"))

# readSock, multicast_group, writeSock = hp.init("learners")
#
# msg = hp.Message.create_catchuprequest(1, 666)
# writeSock.sendto(msg, hp.send_to_role("acceptors"))

readSock, multicast_group, writeSock = hp.init("learners")

msg = hp.Message.create_catchupreply(1, 666, {1: 1, 2: 2})
writeSock.sendto(msg, hp.send_to_role("learners"))

msg = hp.Message.create_catchupreply(1, 666, {1: 1, 2: 2, 3: 3})
writeSock.sendto(msg, hp.send_to_role("learners"))

time.sleep(5)

readSock, multicast_group, writeSock = hp.init("proposers")

msg_decision = hp.Message.create_decision(5, 666, 5)
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(5)

msg_decision = hp.Message.create_decision(4, 666, 4)
writeSock.sendto(msg_decision, hp.send_to_role("learners"))



