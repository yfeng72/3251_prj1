from RTP import *
from sys import *


if len(sys.argv) != 3:
    print("Requires the port number to listen on, as well as the window size.")
    exit()
else:
    port = int(sys.argv[1])
    window = int(sys.argv[2])
    receipt = None
    RTPserv = RTP(None, port, port, True, window)
    while True:
        receipt = RTPserv.listen()
            
