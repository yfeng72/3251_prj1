from RTP import *
from sys import *

def main():
    if len(sys.argv) != 3:
        print "Requires an IP address and port number to send to, as well as the window size."
        return -1
    else:
        arg1 = sys.args[1].split(":")
        ip = int(arg1[0])
        port = int(arg1[1])
        window = int(sys.argv[2])
