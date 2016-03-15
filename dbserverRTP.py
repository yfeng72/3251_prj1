from RTP import *
from sys import *

def main():
    if len(sys.argv) != 3:
        print "Requires the port number to listen on, as well as the window size."
        return -1
    else:
        port = int(sys.argv[1])
        window = int(sys.argv[2])
