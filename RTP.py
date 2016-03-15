from enum import Enum
import socket
import sys
import time

class RTP:
    MAXSIZE = 255
    class Connection(Enum):
        CLOSED = 0
        LISTEN = 1
        CONNECTED = 2

    def __init__(self, ip_addr, sPort, dPort, server):
        self.ip_addr = ip_addr
        self.sPort = sPort
        self.dPort = dPort
        self.server = server
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # s is the socket
        self.seqn = 0
        self.chksum = 0
        self.tthresh = 0 # Threshld for RTT timeout
        self.filename = ''
        self.sendBuffer = []
        self.recvBuffer = []
        self.state = Connection.CLOSED

    def connect(self, sPort, dPort):
        synpkt_hdr = RTPhdr(sPort, dPort, 0)
        synpkt_hdr.SYN = True
        synpkt_hdr.BEG = True
        synpkt_hdr.FIN = True
        synpkt_hdr.timestamp = time.time()
        synpkt = RTPpkt(synpkt_hdr, None)
        synpkt.checkSum()
        sndpkt = synpkt.getByteArray()
        addr = self.ip_addr, self.dPort
        self.s.sendto(sndpkt, addr)
        seqn += 1
        self.state = Connection.LISTEN
        listen()
