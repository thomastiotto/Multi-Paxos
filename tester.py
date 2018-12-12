import helper as hp
import time

# TODO test con due leader e vedere cosa viene deciso
# TODo test con istanza non decisa e vederew cosa fa learner

#
# msg = hp.Message.create_proposal(666, 7)
# writeSock.sendto(msg, hp.send_to_role("proposers"))

# readSock, multicast_group, writeSock = hp.init("learners")
#
# msg = hp.Message.create_catchuprequest(1, 666)
# writeSock.sendto(msg, hp.send_to_role("acceptors"))

# readSock, multicast_group, writeSock = hp.init("acceptors")
#
# msg = hp.Message.create_catchupreply(1, 666, 2, {1: 1, 2: 2, 3: 3})
# writeSock.sendto(msg, hp.send_to_role("learners"))
#
# msg = hp.Message.create_catchupreply(1, 666, 3, {1: 1, 3: 3})
# writeSock.sendto(msg, hp.send_to_role("learners"))

# time.sleep(2)
#



readSock, multicast_group, writeSock = hp.init("proposers")

time.sleep(2)

msg_decision = hp.Message.create_decision(0, 666, 0)
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(2)

msg_decision = hp.Message.create_decision(2, 666, 2)
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(2)

msg_decision = hp.Message.create_decision(3, 666, 3)
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

time.sleep(2)

msg_decision = hp.Message.create_decision(1, 666, 1)
writeSock.sendto(msg_decision, hp.send_to_role("learners"))

#
# time.sleep(2)
#
# msg_decision = hp.Message.create_decision(4, 666, 4)
# writeSock.sendto(msg_decision, hp.send_to_role("learners"))





