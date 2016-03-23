from enum import Enum
import socket
import sys
import time
import math
class Connection(Enum): #state of the connection
    CLOSED = 0
    LISTEN = 1
    CONNECTED = 2

class RTP:
    MAXSIZE = 900

    def __init__(self, ip_addr, udp_port, rtp_port, server, receiveWindow):
        self.ip_addr = ip_addr
        self.pktQ = {}                                              #dictionary, key is client address & port tuple, value is list of packets                                               
        self.rtp_port = rtp_port
        self.udp_port = udp_port
        self.server = server
        self.rwnd = receiveWindow
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   #s is the socket
        self.s.bind(('', udp_port))
        self.seqn = 0 # sequence number
        self.state = {}                                             #dictionary, key is client address & port tuple, value is connection state
        self.files = {}                                             #dictionary, key is client address & port tuple, value is list of file segments in order
        self.prevpkts = {}                                          #dictionary, key is client address & port tuple, value is list of the previous packet for each client

    def connect(self, ip_dest, uPort, dPort): #client-side establishment of connection
        synpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, 0)
        synpkt_hdr.SYN = True
        synpkt_hdr.sPort_udp = self.udp_port
        synpkt_hdr.dPort_udp = uPort
        synpkt = RTPpkt(synpkt_hdr, None, False)
        addr = ip_dest, uPort
        self.s.sendto(synpkt.toByteArray(), addr)
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
        self.state[ip_dest, uPort, dPort] = Connection.CONNECTED

    def accept(self, ip_client, uPort, dPort): #server-side acceptance of connection
        synack_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_client, dPort, self.seqn)
        synack_hdr.ACK = True
        synack_hdr.SYN = True
        synack_hdr.sPort_udp = self.udp_port
        synack_hdr.dPort_udp = uPort
        synack = RTPpkt(synack_hdr, None, False)
        self.queue(synack)
        self.state[ip_client, uPort, dPort] = Connection.CONNECTED
        print('accepted')


    def queue(self, pkt): #queues a packet to sending packet list
        rtp_addr = pkt.hdr.ip_dest, pkt.hdr.dPort_udp, pkt.hdr.dPort
        if (rtp_addr not in self.pktQ):
            self.pktQ[rtp_addr] = []
        self.pktQ[rtp_addr].append(pkt)
    
    def sendpkts(self): #server-side iteration over pktQ and send one for each client
        for (ip_dest, uPort, dPort) in self.pktQ:
            if (self.pktQ[ip_dest, uPort, dPort]):
                sndpkt = self.pktQ[ip_dest, uPort, dPort].pop(0)
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
            self.queue(finack)
            self.state.pop((ip_dest, uPort, dPort), None)
        else: #client-side close connection, sends FIN, receive FINACK
            finpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            finpkt_hdr.FIN = True
            finpkt_hdr.sPort_udp = self.udp_port
            finpkt_hdr.dPort_udp = uPort
            finpkt = RTPpkt(finpkt_hdr, None, False)
            self.s.sendto(finpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            data = ''


#Server-side listen and transfer, returns None if accepted or closed a connection
#Also returns None if a client sends to an unconnected server
#Otherwise returns the packet it received.
#This method handles CLIENT-SIDE FILE POSTING automatically
#This method needs to be called in an infinite loop, as it only receives and sends one packet to each client per call
    def listen(self): 
        #scan for new packets first
        data, addr = self.s.recvfrom(1024)
        if (data):
            rcvpkt = RTPpkt(None, data, True)
            print(rcvpkt.length)
            #Duplicate detection: drop packet from same client with identical seqn as the previous packet
            if (((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.prevpkts) and self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].hdr.seqn == rcvpkt.hdr.seqn and self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].hdr.timestamp == rcvpkt.hdr.timestamp):
                self.sendpkts()
                return
            if (rcvpkt.hdr.SYN):
                self.accept(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            elif (rcvpkt.hdr.FIN and not rcvpkt.hdr.ACK):
                self.close(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            elif (((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.state) and self.state[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] == Connection.CONNECTED):
                if (rcvpkt.hdr.BEG):
                    self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] = [rcvpkt.truncate(data)]
                elif (not rcvpkt.hdr.FIN):
                    if((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.files):
                        self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].append(rcvpkt.truncate(data))
                else:
                    content = ''
                    for segment in self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort][1:]:
                        content += segment
                    content += rcvpkt.truncate(data)
                    with open('post_' + self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort][0], 'w') as f:
                        f.write(content)
                    self.files.pop((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort))
                self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] = rcvpkt
                self.sendpkts()
                return (rcvpkt.truncate(data), rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] = rcvpkt
        self.sendpkts()

        

    def getFile(self, filename, ip_dest, uPort, dPort): #client-side get file form server
        content = ''
        fin = False
        while (not fin):
            data = ''
            while (not data):
                data, addr = self.s.recvfrom(1024)
            rcvpkt = RTPpkt(None, data, True)
            fin = rcvpkt.hdr.FIN
            content += rcvpkt.truncate(data)
        with open('get_' + filename, 'w') as f:
            f.write(content)
            
#both client and server can use this to send a single message
    def send(self, message, ip_dest, uPort, dPort):
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt = RTPpkt(sndpkt_hdr, message, False)
        if (self.server):
            self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
        else:
            self.queue(sndpkt)

#only used by the client, listen() returns the received packet from clients.
    def recv(self, ip_dest, uPort, dPort):
        data = ''
        while (not data):
            data, addr = self.s.recvfrom(1024)
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
                self.queue(sndpkt)
            else:
                self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                self.seqn += 1

class RTPpkt:
    def __init__(self, header, data, is_raw_data):
        #data is in the form of String, raw_data is in the form of byte array 
        if (is_raw_data):
            self.checksum = (data[0] << 8) + data[1] 
            self.length = (data[2] << 8) + data[3] 
            self.hdr = self.parseHeader(data)
            self.data = self.truncate(data)
        else:
            self.hdr = header
            self.data = data
            self.checksum = 0
            self.length = 0
            self.length = len(self.toByteArray())
            self.checkSum()

#calculates checksum, stores it in self.checksum
    def checkSum(self):
        self.checksum = sum(self.toByteArray()[3:]) % 0xffff

#Coding header in packet bytes: bytes 4-7 are ip_src, bytes 8-9 are udp port, bytes 10-11 are rtp port of source. Bytes 12-19 are similarly structured for destination
#Bytes 20-23 hold sequence number, bytes 24-25 hold offset number, byte 26 is flags, bytes 27-30 hold timestamp. Length of non-payload: 30 Bytes
    def parseHeader(self, raw_data):
        ip_src = str(raw_data[4]) + '.' + str(raw_data[5]) + '.' + str(raw_data[6]) + '.' + str(raw_data[7])
        sPort = (raw_data[10] << 8) + raw_data[11]
        ip_dest = str(raw_data[12]) + '.' + str(raw_data[13]) + '.' + str(raw_data[14]) + '.' + str(raw_data[15])
        dPort = (raw_data[18] << 8) + raw_data[19]
        seqn = (raw_data[20] << 24) + (raw_data[21] << 16) + (raw_data[22] << 8) + raw_data[23]
        hdr = RTPhdr(ip_src, sPort, ip_dest, dPort, seqn)
        hdr.offset = (raw_data[24] << 8) + raw_data[25]
        hdr.sPort_udp = (raw_data[8] << 8) + raw_data[9]
        hdr.dPort_udp = (raw_data[16] << 8) + raw_data[17]
        hdr.SYN = raw_data[26] ^ 8 < raw_data[26]
        hdr.ACK = raw_data[26] ^ 4 < raw_data[26]
        hdr.BEG = raw_data[26] ^ 2 < raw_data[26]
        hdr.FIN = raw_data[26] ^ 1 < raw_data[26]
        hdr.timestamp = (raw_data[27] << 24) + (raw_data[28] << 16) + (raw_data[29] << 8) + raw_data[30]
        return hdr

#      Returns the byte array of the packet, checksum needs to be 
#      converted to one byte and appended to the front of the byte array, 
#      header bytes need to be encoded and appended after the checksum byte 
#      and the length byte, data bytes last. IT IS POSSIBLE FOR DATA TO BE None.
    def toByteArray(self):
        content = []
        content.append(self.checksum >> 8)                                          #bit 0
        content.append(self.checksum - ((self.checksum >> 8) << 8))                 
        content.append(self.length >> 8)                                            #bit 2
        content.append(self.length - ((self.length >> 8) << 8)) 
        content.append(int(self.hdr.ip_src.split('.')[0]))                               #bit 4
        content.append(int(self.hdr.ip_src.split('.')[1]))                               
        content.append(int(self.hdr.ip_src.split('.')[2]))
        content.append(int(self.hdr.ip_src.split('.')[3]))
        content.append(self.hdr.sPort_udp >> 8)
        content.append(self.hdr.sPort_udp - ((self.hdr.sPort_udp >> 8) << 8))
        content.append(self.hdr.sPort >> 8)
        content.append(self.hdr.sPort - ((self.hdr.sPort >> 8) << 8))
        content.append(int(self.hdr.ip_dest.split('.')[0]))                              #bit 12
        content.append(int(self.hdr.ip_dest.split('.')[1]))
        content.append(int(self.hdr.ip_dest.split('.')[2]))
        content.append(int(self.hdr.ip_dest.split('.')[3]))
        content.append(self.hdr.dPort_udp >> 8)
        content.append(self.hdr.dPort_udp - ((self.hdr.dPort_udp >> 8) << 8))
        content.append(self.hdr.dPort >> 8)
        content.append(self.hdr.dPort - ((self.hdr.dPort >> 8) << 8))               
        content.append(self.hdr.seqn >> 24)                                         #bit 20
        content.append((self.hdr.seqn >> 16) - ((self.hdr.seqn >> 24) << 8))
        content.append((self.hdr.seqn >> 8) - ((self.hdr.seqn >> 16) << 8))
        content.append(self.hdr.seqn - ((self.hdr.seqn >> 8) << 8))
        content.append(self.hdr.offset >> 8)                                        #bit 24
        content.append(self.hdr.offset - ((self.hdr.seqn >> 8) << 8))
        content.append((int(self.hdr.SYN) << 3) + (int(self.hdr.ACK) << 2) + (int(self.hdr.BEG) << 1) + int(self.hdr.FIN))
        content.append(self.hdr.seqn >> 24)                                         #bit 27
        content.append((self.hdr.seqn >> 16) - ((self.hdr.seqn >> 24) << 8))
        content.append((self.hdr.seqn >> 8) - ((self.hdr.seqn >> 16) << 8))
        content.append(self.hdr.seqn - ((self.hdr.seqn >> 8) << 8))                 #bit 30
        if(self.data):
            for char in self.data:
                content.append(ord(char))
        return bytes(content)

#returns the payload of a packet byte array in string format    
    def truncate(self, raw_data):
        return(raw_data[31 : (raw_data[2] << 8) + raw_data[3]].decode())

class RTPhdr:
    def __init__(self, ip_src, sPort, ip_dest, dPort, seqn):
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

    def updateTimestamp(self):
        self.timestamp = int(time.time())