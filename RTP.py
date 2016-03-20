from enum import Enum
import socket
import sys
import time
import math
class RTP:
    MAXSIZE = 900
    class Connection(Enum): #state of the connection
        CLOSED = 0
        LISTEN = 1
        CONNECTED = 2

    def __init__(self, ip_addr, udp_port, rtp_port, server, receiveWindow):
        self.ip_addr = ip_addr
        self.pktQ = {}
        self.connections = {}
        self.rtp_port = rtp_port
        self.udp_port = udp_port
        self.server = server
        self.rwnd = receiveWindow
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # s is the socket
        self.seqn = 0 # sequence number
        self.state = {}
        self.files = {}

    def connect(self, ip_dest, uPort, dPort): #client-side establishment of connection
        synpkt_hdr = RTPhdr(ip_src, self.rtp_port, ip_dest, dPort, 0)
        synpkt_hdr.SYN = True
        synpkt_hdr.sPort_udp = self.udp_port
        synpkt_hdr.dPort_udp = uPort
        synpkt = RTPpkt(synpkt_hdr, None, False)
        addr = ip_dest, uPort
        self.s.sendto(synpkt.getByteArray(), addr)
        self.seqn += 1
        self.state[ip_dest, uPort, dPort] = Connection.LISTEN
        data = None
        syn = False
        ack = False
        while ((not syn) or (not ack)):
            data, udp_addr = self.s.recvfrom(1024)
            if (not data):
                continue
            synack = RTPpkt(None, data, True)
            syn = synack.hdr.SYN
            ack = synack.hdr.ACK
        ackpkt_hdr = RTPhdr(ip_src, self.rtp_port, ip_dest, dPort, self.seqn)
        ackpkt_hdr.ACK = True
        ackpkt_hdr.sPort_udp = self.udp_port
        ackpkt_hdr.dPort_udp = uPort
        ackpkt = RTPpkt(ackpkt_hdr, None, False)
        addr = ip_dest, uPort
        self.s.sendto(ackpkt.getByteArray(), addr)
        self.seqn += 1
        self.state[ip_dest, uPort, dPort] = Connection.CONNECTED

    def accept(self, ip_client, uPort, dPort): #server-side acceptance of connection
        synack_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_client, dPort, self.seqn)
        synack_hdr.ACK = True
        synack_hdr.SYN = True
        synack_hdr.sPort_udp = self.udp_port
        synack_hdr.dPort_udp = uPort
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
                sndpkt.hdr.updateTimestamp()
                self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                self.seqn += 1

    def close(self, ip_dest, uPort, dPort):
        if (self.server): #server-side close connection, sends FIN, ACK
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
            self.s.sendto(finpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            data = ''
            while (not data): #wait for FINACK from server
                data = self.s.recvfrom(1024)
            finack = RTPpkt(None, data, True)
            if (finack.hdr.FIN == True and finack.hdr.ACK == True):
                self.state[ip_dest, uPort, dPort] = Connection.CLOSED

#Server-side listen and transfer, returns None if accepted or closed a connection
#Also returns None if a client sends to an unconnected server
#Otherwise returns the packet it received.
#This method handles client file posting automatically
    def listen(self): 
        #scan for new packets first
        data, addr = self.s.recvfrom(1024)
        if (data):
            rcvpkt = RTPpkt(None, data, True)
            if (rcvpkt.hdr.SYN):
                accept(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            elif (rcvpkt.hdr.FIN and not rcvpkt.hdr.ACK):
                close(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            elif (self.state[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] == Connection.CONNECTED):
                if (rcvpkt.hdr.BEG):
                    self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] = [rcvpkt.truncate(data)]
                elif (not rcvpkt.hdr.FIN):
                    self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].append(rcvpkt.truncate(data))
                else:
                    content = ''
                    for segment in self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort][1:]:
                        content += segment
                    content += rcvpkt.truncate(data)
                    with open('post_' + self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort][0], 'w') as f:
                        f.write(content)
                    self.files.pop((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort))
                sendpkts()
                return (rcvpkt.truncate(data), rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
        sendpkts()

        

    def getFile(self, filename, ip_dest, uPort, dPort): #client-side get file form server
        content = ''
        fin = False
        while (not fin):
            data = ''
            while (not data):
                data = self.s.recvfrom(1024)
            rcvpkt = RTPpkt(None, data, True)
            fin = rcvpkt.hdr.FIN
            content += rcvpkt.truncate(data)
        with open('get_' + filename, 'w') as f:
            f.write(content)
            
#both client and server can use this to send a message
    def send(self, message, ip_dest, uPort, dPort):
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
        self.seqn += 1

#only for the client, listen() returns the received packet for servers.
    def recv(self, ip_dest, uPort, dPort):
        data = ''
        while (not data):
            data = self.s.recvfrom(1024)
        rcvpkt = RTPpkt(None, data, True)
        return (rcvpkt.truncate(data))

#for both client and server to send/post a file to each other      
    def sendFile(self, filename, ip_dest, uPort, dPort):
        content = ''
        segment = ''
        count = 0
        with open(filename, 'r') as f:
            content = f.read()
        count = int(math.ceil(len(content) / float(MAXSIZE - 1)))
        if (not server):
            namepkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            namepkt_hdr.sPort_udp = self.udp_port
            namepkt_hdr.dPort_udp = uPort
            namepkt_hdr.BEG = True
            namepkt_hdr.sPort_udp = self.udp_port
            namepkt_hdr.dPort_udp = uPort
            namepkt = RTPpkt(namepkt_hdr, filename, False)
            self.s.sendto(namepkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
        for pktn in range(count):
            pkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            pkt_hdr.offset = pktn
            pkt_hdr.BEG = (pktn == 0) and (not server)
            pkt_hdr.FIN = (pktn == count - 1)
            if (not server):
                pkt_hdr.ACK = True
            pkt_hdr.sPort_udp = self.udp_port
            pkt_hdr.dPort_udp = uPort
            segment = content[pktn * MAXSIZE : len(content)] if (pktn == count - 1) else content[pktn * MAXSIZE : (pktn + 1) * MAXSIZE]
            sndpkt = RTPpkt(pkt_hdr, segment, False)
            if (server):
                queue(sndpkt)
            else:
                self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                self.seqn += 1

class RTPpkt:
    def RTPpkt(header, data, is_raw_data):
        #data is in the form of String, raw_data is in the form of byte array 
        if (is_raw_data):
            self.checksum = (data[0] << 8) + data[1] 
            self.length = (data[1] << 8) + data[2] 
            self.hdr = parseHeader(data)
            self.data = truncate(data)
        else:
            self.hdr = header
            self.data = data
            self.checkSum()
            self.length = len(self.toByteArray())

    def checkSum():
        #TODO: updates the checksum of the packet, store it in self.checksum
        pass
    def parseHeader(raw_data):
        #TODO: parse the header from raw data, returns RTPhdr object
        pass
    def toByteArray():
        #TODO: returns the byte array of the packet, checksum needs to be 
        #      converted to one byte and appended to the front of the byte array, 
        #      header bytes need to be encoded and appended after the checksum byte 
        #      and the length byte, data bytes last. IT IS POSSIBLE FOR DATA TO BE None.
        
    def truncate(raw_data):
        #TODO: truncates raw data, returns payload in String format
        pass

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
        self.timestamp = int(time.time())

    def updateTimestamp():
        self.timestamp = int(time.time())