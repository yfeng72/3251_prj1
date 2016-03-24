import RTP
import sys

def main():
    if len(sys.argv) != 3:
        print("Requires the port number to listen on, as well as the window size.")
        exit()
    else:
        port = int(sys.argv[1])
        window = int(sys.argv[2])
        RTPserv = RTP.RTP('127.0.0.1', port, port, True, window)
        while True:
            info = RTPserv.listen()
            
main()