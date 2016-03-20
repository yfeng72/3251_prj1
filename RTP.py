from enum import Enum
import socket
import sys
import time
import math
class RTP:
    MAXSIZE = 2048
    class Connection(Enum): #state of the connection
        CLOSED = 0
        LISTEN = 1
        CONNECTED = 2

    def __init__(self, ip_addr, udp_port, rtp_port, server, receiveWindow):
        self.ip_addr = ip_addr
        self.clients = []
        self.pktQ = {}
        self.connections = {}
        self.servers = []
        self.rtp_port = rtp_port
        self.udp_port = udp_port
        self.server = server
        self.rwnd = receiveWindow
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # s is the socket
        self.seqn = 0 # sequence number
        self.tthresh = 0 # Threshld for RTT timeout
        self.filename = []
        self.sendBuffer = []
        self.recvBuffer = []
        self.state = {}

    def connect(self, ip_dest, uPort, dPort): #client-side establishment of connection
        synpkt_hdr = RTPhdr(ip_src, self.rtp_port, ip_dest, dPort, 0)
        synpkt_hdr.SYN = True
        synpkt_hdr.timestamp = int(time.time())
        synpkt_hdr.sPort_udp = self.udp_port
        synpkt_hdr.dPort_udp = uPort
        synpkt = RTPpkt(synpkt_hdr, None, False)
        synpkt.checkSum()
        addr = ip_dest, uPort
        self.s.sendto(synpkt.getByteArray(), addr)
        self.seqn += 1
        self.state[ip_dest, uPort, dPort] = Connection.LISTEN
        data = None
        while (!data):
            data, udp_addr = s.recvfrom(4096)
        synack = RTPpkt(None, data, True)
        if (synack.SYN == True and synack.ACK == True):
            ackpkt_hdr = RTPhdr(ip_src, self.rtp_port, ip_dest, dPort, self.seqn)
            ackpkt_hdr.ACK = True
            ackpkt_hdr.timestamp = int(time.time())
            ackpkt_hdr.sPort_udp = self.udp_port
            ackpkt_hdr.dPort_udp = uPort
            ackpkt = RTPpkt(ackpkt_hdr, None, False)
            addr = ip_dest, uPort
            self.s.sendto(ackpkt.getByteArray(), addr)
            self.seqn += 1
            self.state[ip_dest, uPort, dPort] = Connection.CONNECTED
        else:
            print('Connection Failed\n')

    def accept(self, ip_client, uPort, dPort): #server-side acceptance of connection
        synack_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_client, dPort, self.seqn)
        synack_hdr.ACK = True
        synack_hdr.SYN = True
        synack_hdr.sPort_udp = self.udp_port
        synack_hdr.dPort_udp = uPort
        synack_hdr.timestamp = int(time.time())
        synack = RTPpkt(synack_hdr, None, False)
        queue(synack)
        self.state[ip_dest, uPort, dPort] = Connection.CONNECTED


    def queue(self, pkt): #queues a packet to sending packet list
        rtp_addr = pkt.hdr.ip_dest, pkt.hdr.dPort_udp, pkt.hdr.dPort
        self.pktQ[rtp_addr].append(pkt)
    
    def sendpkts(self): #server-side iteration over pktQ and send one for each client
        for (ip_dest, uPort, dPort) in self.pktQ:
            if (pktQ[ip_dest, uPort, dPort]):
                sndpkt = pktQ[ip_dest, uPort, dPort].pop(0)
                s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                self.seqn += 1

    def close(self, ip_dest, uPort, dPort):
        if (self.isServer): #server-side close connection, sends FIN, ACK
            finack_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            finack_hdr.FIN = True
            finack_hdr.ACK = True
            finack_hdr.sPort_udp = self.udp_port
            finack_hdr.dPort_udp = uPort
            finack = RTPpkt(finack_hdr, None, False)
            queue(finack)
            self.state[ip_dest, uPort, dPort] = Conection.CLOSED
        else: #client-side close connection, sends FIN, receive FINACK
            finpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            finpkt_hdr.FIN = True
            finpkt_hdr.sPort_udp = self.udp_port
            finpkt_hdr.dPort_udp = uPort
            finpkt = RTPpkt(finpkt_hdr, None, False)
            s.sendto(finpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            data = ''
            while (!data): #wait for FINACK from server
                data = s.recvfrom(4096)
            finack = RTPpkt(None, data, True)
            if (finack.hdr.FIN == True and finack.hdr.ACK == True):
                self.state[ip_dest, uPort, dPort] = Connection.CLOSED


    def listen(self): #server-side listen and transfer
        #scan for new packets first
        data, addr = s.recvfrom(4096)
        if (data):
            rcvpkt = RTPpkt(None, data, True)
            if (rcvpkt.hdr.SYN):
                accept(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            elif (rcvpkt.hdr.FIN and not rcvpkt.hdr.ACK):
                close(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
        sendpkts()

    def getFile(self):
        
    def sendFile(self, filename):
        content = ''
        segment = ''
        count = 0
        with open(filename, 'r') as f:
            content = f.read()
        count = int(math.ceil(len(content) / float(MAXSIZE - 1)))
        for pktn in range(count):
            pkt_hdr = RTPhdr(rtp_port, dPort, pktn)
            pkt_hdr.seqn = seqn
            pkt_hdr.timestamp = int(time.time())
            pkt_hdr.offset = pktn
            pkt_hdr.BEG = (pktn == 0)
            pkt_hdr.FIN = (pktn == count - 1)
            segment = content[pktn * MAXSIZE : len(content)] if (pktn == count - 1) else content[pktn * MAXSIZE : (pktn + 1) * MAXSIZE]
            sndpkt = RTPpkt(pkt_hdr, segment, False)
            queue(sndpkt)

class RTPpkt:
    def RTPpkt(header, data, is_raw_data):
        #data is in the form of String, raw_data is in the form of byte array 
        if (is_raw_data):
            self.hdr = parseHeader(data.decode())
            self.data = truncate(data.decode())
            self.checksum = 0
            self.checkSum()
        else:
            self.hdr = header
            self.data = data
            self.checksum = 0
            self.checkSum()

    def checkSum():
        #TODO: updates the checksum of the packet, store it in self.checksum
    def parseHeader(raw_data):
        #TODO: parse the header from raw data, returns RTPhdr object
    def toByteArray():
        #TODO: returns the byte array of the packet, checksum needs to be 
        #      converted to one byte and appended to the front of the byte array, 
        #      header bytes need to be encoded and appended after the checksum byte, 
        #      then the data bytes. IT IS POSSIBLE FOR DATA TO BE None
    def truncate(raw_data):
        #TODO: truncates raw data, returns payload

class RTPhdr:
    def RTPhdr(ip_src, sPort, ip_dest, dPort, seqn):
        self.ip_src = ip_src
        self.sPort = sPort
        self.ip_dest = ip_dest
        self.dPort = dPort
        self.sPort_udp = 0
        self.dPort_udp = 0
        self.seqn = seqn
        self.offset = 0 #used for file transfer
        self.SYN = False
        self.ACK = False
        self.BEG = False
        self.FIN = False
        self.timestamp = 0