from enum import Enum
import socket
import sys
import time

class RTP:
    MAXSIZE = 1024
    class Connection(Enum): #state of the connection
        CLOSED = 0
        LISTEN = 1
        CONNECTED = 2

    def __init__(self, ip_addr, sPort, dPort, server):
        self.ip_addr = ip_addr
        self.sPort = sPort
        self.dPort = dPort
        self.server = server
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # s is the socket
        self.seqn = 0 # sequence number
        self.tthresh = 0 # Threshld for RTT timeout
        self.filename = ''
        self.sendBuffer = []
        self.recvBuffer = []
        self.state = Connection.CLOSED

    def connect(self, sPort, dPort): #establish the connection
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

    def sendpkt(data): #sends a packet
        sndpkt_hdr = RTPhdr(sPort,dPort, self.seqn)
        sndpkt_hdr.BEG = True
        sndpkt_hdr.FIN = True
        sndpkt_hdr.timestamp = time.time()
        sndpkt = RTPpkt(sndpkt_hdr, data)
        sndpkt.checkSum()
        send(sndpkt)

    def send(data):
        self.seqn += 1
        addr = self.ip_addr, self.dPort
        self.s.sendto(sndpkt, addr)

    def startServer(): #starts server
        self.state = Connection.LISTEN
    
    def listen(): #listen and trasfer files for both client and server
        while (((not self.server and self.state == Connection.LISTEN) or (self.server and self.state != Connection.CLOSED)):
            data, addr = self.s.recvfrom(1024)
            data = data.strip()
            rcvpkt = RTPpkt(data)
            rcvpkt_hdr = rcvpkt.hdr
            if (rcvpkt_hdr.checkSum() == rcvpkt.chksum):
                if (server and rcvpkt_hdr.SYN == True):
                    response_hdr = RTPhdr(self.sPort, self.dPort, 0)
                    response_hdr.ACK = True
                    response_hdr.SYN = True
                    response_hdr.BEG = True
                    response_hdr.FIN = True
                    response_hdr.timestamp = time.time()
                    response_hdr.seqn = self.seqn
                    response = RTPpkt(response_hdr, None)
                    response.checkSum()
                    addr = self.ip_addr, self.dPort
                    self.s.sendto(response, addr)
                if (not server and (rcvpkt_hdr.SYN and rcvpkt_hdr.ACK) == True):
                    self.state = Connection.CONNECTED
                elif (server and rcvpkt_hdr.SYN):
                    self.state = Connection.CONNECTED
                while (not rcvpkt_hdr.FIN):
                    data, addr = self.s.recvfrom(1024)
                    data = data.strip()
                    rcvpkt = RTPpkt(data)
                    rcvpkt_hdr = rcvpkt.hdr
                    if (rcvpkt_hdr.chksum == rcvpkt_hdr.checkSum()):
                        recvBuffer.append(rcvpkt)
                if (server and self.state == Connection.CONNECTED and rcvpkt.data.strip() != ''):
                    sendFile(rcvpkt.data)
                if (not server and self.state == Connection.LISTEN):
                    recvBuffer.append(rcvpkt)
                if (not server and self.state == Connection.LISTEN and rcvpkt_hdr.FIN == True):
                    output = ''
                    for pkt in recvBuffer:
                        output += pkt.data
                    with open(self.filename, 'w') as f:
                        f.write(output)
                    recvBuffer = []
                    self.state = Connection.CLOSED
