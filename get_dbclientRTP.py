import socket
import sys
import RTP

def main():
    if (len(sys.argv) < 3):
        print ("Requires an IP address and port number to send to, as well as the window size.")
        return (-1)
    HOST_IP = socket.gethostbyname(socket.gethostname())
    HOST_PORT = int(sys.argv[1][sys.argv[1].index(':') + 1:]) + 1
    UDP_IP = sys.argv[1][:sys.argv[1].index(':')]
    UDP_PORT = int(sys.argv[1][sys.argv[1].index(':') + 1:])
    RTP_PORT = int(sys.argv[1][sys.argv[1].index(':') + 1:])
    rwnd = 1
    BUFFER_SIZE = 1024
    #build message
    MESSAGE = sys.argv[2] + ','
    for s in sys.argv[3:]:
        MESSAGE += s + ','
    MESSAGE = MESSAGE[:-1]
    r = RTP.RTP(HOST_IP, HOST_PORT, HOST_PORT, False, rwnd)
    r.connect(UDP_IP, UDP_PORT, RTP_PORT)
    r.send(MESSAGE, UDP_IP, UDP_PORT, RTP_PORT)
    #send message
    data = r.recv(UDP_IP, UDP_PORT, RTP_PORT)
    
    #receive message
    r.close(UDP_IP, UDP_PORT, RTP_PORT) 
    print ("From server: ", data)

main()