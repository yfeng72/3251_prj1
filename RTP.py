from enum import Enum
import socket
import sys
import time
import math
class Connection(Enum): #state of the connection
    CLOSED = 0
    LISTEN = 1
    CONNECTED = 2

MAXSIZE = 900

class RTP:
    def __init__(self, ip_addr, udp_port, rtp_port, server, receiveWindow):
        self.ip_addr = ip_addr
        self.pktQ = {}                                              #dictionary, key is client address & port tuple, value is list of packets                                               
        self.rtp_port = rtp_port
        self.udp_port = udp_port
        self.server = server
        self.rwnd = min(receiveWindow, MAXSIZE)
        self.cwnd = {}                                              #dictionary, congestion window size for each host
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   #s is the socket
        self.s.bind(('', udp_port))
        self.s.setblocking(0)
        self.seqn = 0 # sequence number
        self.state = {}                                             #dictionary, key is client address & port tuple, value is connection state
        self.files = {}                                             #dictionary, key is client address & port tuple, value is list of file segments in order
        self.prevpkts = {}                                          #dictionary, key is client address & port tuple, value is list of the previous packet for each client
        self.filename = {}
        self.timers = {}

    def connect(self, ip_dest, uPort, dPort): #client-side establishment of connection
        synpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, 0)
        synpkt_hdr.SYN = True
        synpkt_hdr.sPort_udp = self.udp_port
        synpkt_hdr.dPort_udp = uPort
        synpkt = RTPpkt(synpkt_hdr, None, False)
        addr = ip_dest, uPort
        self.s.sendto(synpkt.toByteArray(), addr)
        self.seqn += 1
        data = ''
        while (not data):
            if (int(time.time()) > (sndpkt.hdr.timestamp + 2)):
                self.s.sendto(synpkt.toByteArray(), addr)
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                pass
        synack = RTPpkt(None, data, True)
        if (synack.examineChksum() and synack.hdr.SYN and synack.hdr.ACK):
            ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, 0)
            ackpkt_hdr.ACK = True
            ackpkt_hdr.sPort_udp = self.udp_port
            ackpkt_hdr.dPort_udp = uPort
            ackpkt_hdr.ackn = synack.hdr.seqn
            ackpkt = RTPpkt(ackpkt_hdr, None, False)
            self.s.sendto(ackpkt.toByteArray(), addr)
            self.seqn += 1
            self.state[ip_dest, uPort, dPort] = Connection.CONNECTED

    def accept(self, ip_client, uPort, dPort, cwnd): #server-side acceptance of connection
        synack_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_client, dPort, self.seqn)
        synack_hdr.ACK = True
        synack_hdr.SYN = True
        synack_hdr.sPort_udp = self.udp_port
        synack_hdr.dPort_udp = uPort
        synack = RTPpkt(synack_hdr, None, False)
        self.queue(synack)
        self.state[ip_client, uPort, dPort] = Connection.CONNECTED
        self.cwnd[ip_client, uPort, dPort] = cwnd


    def queue(self, pkt): #queues a packet to sending packet list
        rtp_addr = pkt.hdr.ip_dest, pkt.hdr.dPort_udp, pkt.hdr.dPort
        if (rtp_addr not in self.pktQ):
            self.pktQ[rtp_addr] = []
        self.pktQ[rtp_addr].append(pkt)
    
    def sendpkts(self): #server-side iteration over pktQ and send one for each client
        fin = False     
        for (ip_dest, uPort, dPort) in self.pktQ:
            if (self.pktQ[ip_dest, uPort, dPort]):
                sndpkt = self.pktQ[ip_dest, uPort, dPort].pop(0)
                sndpkt.hdr.seqn = self.seqn
                sndpkt.hdr.updateTimestamp()
                self.seqn += 1
                self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                time.sleep(0)
                fin = sndpkt.hdr.FIN
        return fin


    def close(self, ip_dest, uPort, dPort):
        if (self.server): #server-side close connection, sends FINACK
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
            currentTime = time.time()
            while (1):
                try:
                    data, addr = self.s.recvfrom(1024)
                except:
                    if (time.time() > currentTime + 2):
                        self.s.sendto(finpkt.toByteArray(), (ip_dest, uPort))
                        currentTime = time.time()
                    continue
                finack = RTPpkt(None, data, True)
                if (finack.examineChksum() and finack.hdr.dPort == self.rtp_port and finack.hdr.FIN and finack.hdr.ACK):
                    break


#Server-side listen and transfer, returns None if accepted or closed a connection
#Also returns None if a client sends to an unconnected server
#Otherwise returns the packet it received.
#This method handles CLIENT-SIDE FILE POSTING automatically
#This method needs to be called in an infinite loop, as it only receives and sends one packet to each client per call
    def listen(self): 
        self.sendpkts()
        #scan for new packets first
        try:
            data, addr = self.s.recvfrom(1024)
        except:
            return
        if (not data):
            print('no data');
            return
        if (data):
            rcvpkt = RTPpkt(None, data, True)
            #Duplicate detection: drop packet from same client with identical seqn as the previous packet
            if (((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.prevpkts) and (rcvpkt.hdr.seqn in self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort])):
                return
            if (rcvpkt.hdr.SYN):
                self.accept(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            elif (rcvpkt.hdr.FIN and not rcvpkt.hdr.ACK):
                self.close(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            elif (((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.state) and self.state[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] == Connection.CONNECTED):
                if ((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) not in self.files):
                    self.files[(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)] = []
                if (rcvpkt.hdr.GET):
                    self.sendFile(rcvpkt.data.decode(), rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort, False)
                elif (rcvpkt.hdr.BEG):
                    self.filename[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] = rcvpkt.data.decode()
                elif (not rcvpkt.hdr.FIN):
                    if((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.files):
                        self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].append(rcvpkt)
                else:
                    self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].append(rcvpkt)
                    content = []
                    for segment in self.files[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort]:
                        content.extend(segment.data)
                    with open('post_' + self.filename[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort], 'wb') as f:
                        f.write(bytes(content))
                    self.files.pop((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort))
                if (not (rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.prevpkts):
                    self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] = [rcvpkt.hdr.seqn]
                else:
                    self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].append(rcvpkt.hdr.seqn)
                return (rcvpkt.data, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            if (not (rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) in self.prevpkts):
                self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort] = [rcvpkt.hdr.seqn]
            else:
                self.prevpkts[rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort].append(rcvpkt.hdr.seqn)
        

    def getPost(self, getName, postName, ip_dest, uPort, dPort): #client-side get-post
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt_hdr.GET = True
        sndpkt = RTPpkt(sndpkt_hdr, postName.encode(), False)
        self.seqn += 1
        sndpkt.hdr.seqn = self.seqn
        self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
        prevseqn = []
        pkts = []
        fin = False
        beg = False
        pflag = False
        gflag = False
        content = []
        segment = ''
        count = 0
        with open(postName, 'rb') as f:
            content = f.read()
        count = int(math.ceil(len(content) / float(MAXSIZE - 1)))
        segments = []
        namepkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        namepkt_hdr.sPort_udp = self.udp_port
        namepkt_hdr.dPort_udp = uPort
        namepkt_hdr.BEG = True
        namepkt_hdr.sPort_udp = self.udp_port
        namepkt_hdr.dPort_udp = uPort
        namepkt = RTPpkt(namepkt_hdr, postName.encode(), False)
        pkts.append(namepkt)     
        for pktn in range(count):
            pkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            pkt_hdr.offset = pktn % 255
            pkt_hdr.BEG = (pktn == 0) and (self.server)
            pkt_hdr.FIN = (pktn == count - 1)
            pkt_hdr.ACK = True
            pkt_hdr.sPort_udp = self.udp_port
            pkt_hdr.dPort_udp = uPort
            segment = content[pktn * MAXSIZE : len(content)] if (pktn == count - 1) else content[pktn * MAXSIZE : (pktn + 1) * MAXSIZE]
            sndpkt = RTPpkt(pkt_hdr, segment, False)
            pkts.append(sndpkt)
        content = []
        while (not pflag or not gflag):
            if (len(pkts)):
                sndpkt = pkts.pop(0)
                self.seqn += 1
                sndpkt.hdr.seqn = self.seqn
                time.sleep(0)
                self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                if (sndpkt.hdr.FIN):
                    pflag = True
            data = ''
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                continue
            if (data):
                rcvpkt = RTPpkt(None, data, True)
                if (not rcvpkt.hdr.dPort == self.rtp_port):
                    continue
                if (rcvpkt.hdr.seqn not in prevseqn):
                    prevseqn.append(rcvpkt.hdr.seqn)
                    content.extend(rcvpkt.data)
                if (rcvpkt.hdr.FIN):
                    with open('get_' + getName, 'wb') as f:
                        f.write(bytes(content))
                    gflag = True

#checks for ACK and reorders packet for window size 1, returns when ACK is received
    def checkACK(self, sndpkt):
        currentTime = time.time()
        while (1):
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                if (time.time() > currentTime + 2):
                    self.s.sendto(sndpkt, (sndpkt.hdr.ip_dest, sndpkt.hdr.dPort_udp))
                    currentTime = time.time()
                continue
            ackpkt = RTPpkt(None, data, True)
            if (ackpkt.examineChksum() and ackpkt.hdr.dPort == self.rtp_port and ackpkt.hdr.ACK and ackpkt.hdr.ackn == sndpkt.hdr.seqn):
                return ackpkt


#Client-side get file form server, ACK packets' offset numbers are set to maximum sequentially received offset number + 1
    def getFile(self, filename, ip_dest, uPort, dPort): 
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt_hdr.GET = True
        sndpkt = RTPpkt(sndpkt_hdr, filename.encode(), False)
        self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
        self.seqn += 1
        ackpkt = checkACK(sndpkt)
        segments = {}
        offset = 0
        fin = False
        while (not fin):
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                continue
            rcvpkt = RTPpkt(None, data, True)
            if (rcvpkt.hdr.dPort != self.rtp_port or not rcvpkt.examineChksum()):
                continue
            if (rcvpkt.hdr.offset < offset + self.rwnd + 1 and rcvpkt.hdr.offset >= offset):
                segments[rcvpkt.hdr.offset] = (rcvpkt.data, rcvpkt.FIN)
            offsetn = offset
            while (offsetn < offset + self.rwnd):
                if (not offsetn in segments):
                    break
            ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            ackpkt_hdr.sPort_udp = self.udp_port
            ackpkt_hdr.dPort_udp = uPort
            ackpkt_hdr.ACK = True
            ackpkt_hdr.offset = offsetn
            ackpkt = RTPpkt(ackpkt_hdr, None, False)
            self.s.sendto(ackpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            for i in range(offset, offsetn):
                with open(filename, 'ab') as f:
                    f.write(bytes(segments[i][0]))
                fin = segments.pop(i)[1]
                if (fin):
                    break
            offset = offsetn - 1

            
#both client and server can use this to send a single message
    def send(self, message, ip_dest, uPort, dPort):
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt = RTPpkt(sndpkt_hdr, message.encode(), False)
        currentTime = time.time()
        while (1):
            if (not self.server):
                self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                self.seqn += 1
                try:
                    ackpkt = self.s.recvfrom(buffersize)
                except:
                    if (time.time() > currentTime + 2):
                        self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                        currentTime = time.time()
                if (ackpkt.examineChksum() and ackpkt.hdr.dPort == self.rtp_port and ackpkt.hdr.ackn == sndpkt.hdr.seqn):
                    break
            else:
                self.queue(sndpkt)
                break

#only used by the client, listen() returns the server-side received packet from clients.
    def recv(self, ip_dest, uPort, dPort):
        data = ''
        while (1):
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                continue
            rcvpkt = RTPpkt(None, data, True)
            if (rcvpkt.examineChksum() and rcvpkt.hdr.dPort == self.rtp_port and not rcvpkt.hdr.ACK):
                break
        ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        ackpkt_hdr.ACK = 1
        ackpkt_hdr.ackn = rcvpkt.hdr.seqn
        ackpkt_hdr.sPort_udp = self.udp_port
        ackpkt_hdr.dPort_udp = uPort
        ackpkt = (ackpkt_hdr, None, False)
        self.s.sendto(ackpkt.toByteArray(), (ip_dest, uPort))
        return (rcvpkt.truncate(data))

#for both client and server to send/post a file to each other      
    def sendFile(self, filename, ip_dest, uPort, dPort, getPost):
        content = []
        segment = ''
        count = 0
        with open(filename, 'rb') as f:
            content = f.read()
        count = int(math.ceil(len(content) / float(MAXSIZE - 1)))
        segments = []
        if (not self.server):
            namepkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            namepkt_hdr.sPort_udp = self.udp_port
            namepkt_hdr.dPort_udp = uPort
            namepkt_hdr.BEG = True
            namepkt_hdr.sPort_udp = self.udp_port
            namepkt_hdr.dPort_udp = uPort
            namepkt = RTPpkt(namepkt_hdr, filename.encode(), False)
            if (not getPost):
                self.s.sendto(namepkt.toByteArray(), (ip_dest, uPort))
                self.seqn += 1
            else:
                self.queue(namepkt)
                segments.append(namepkt)      
        for pktn in range(count):
            pkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            pkt_hdr.offset = pktn % 255
            pkt_hdr.BEG = (pktn == 0) and (self.server)
            pkt_hdr.FIN = (pktn == count - 1)
            if (not self.server):
                pkt_hdr.ACK = True
            pkt_hdr.sPort_udp = self.udp_port
            pkt_hdr.dPort_udp = uPort
            segment = content[pktn * MAXSIZE : len(content)] if (pktn == count - 1) else content[pktn * MAXSIZE : (pktn + 1) * MAXSIZE]
            sndpkt = RTPpkt(pkt_hdr, segment, False)
            if (self.server):
                self.queue(sndpkt)
            else:
                if (not getPost):
                    self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
                else:
                    self.queue(sndpkt)
                    segments.append(sndpkt)

class RTPpkt:
    def __init__(self, header, data, is_raw_data):
        #data is in the form of String, raw_data is in the form of byte array 
        if (is_raw_data):
            self.checksum = (data[0] << 8) + data[1] 
            self.length = (data[2] << 8) + data[3] 
            self.hdr = self.parseHeader(data)
            self.data = data[37 : (data[2] << 8) + data[3]]
        else:
            self.hdr = header
            self.data = data
            self.checksum = 0
            self.length = 0
            self.length = len(self.toByteArray())
            self.checkSum()
#Made for comparing and sorting purposes, compare two packets based on their seqn only    
    def __lt__(self, other):
        return self.hdr.seqn < other.hdr.seqn
    def __le__(self, other):
        return self.hdr.seqn <= other.hdr.seqn
    def __eq__(self, other):
        return self.hdr.seqn == other.hdr.seqn
    def __ne__(self, other):
        return self.hdr.seqn != other.hdr.seqn
    def __gt__(self, other):
        return self.hdr.seqn > other.hdr.seqn
    def __ge__(self, other):
        return self.hdr.seqn >= other.hdr.seqn
    def __hash__(self):
        return self.hdr.seqn * 17 + self.checksum * 3
#calculates checksum, stores it in self.checksum
    def checkSum(self):
        self.checksum = sum(self.toByteArray()[2:]) % 0xffff

#Coding header in packet bytes: bytes 4-7 are ip_src, bytes 8-9 are udp port, bytes 10-11 are rtp port of source. Bytes 12-19 are similarly structured for destination
#Bytes 20-23 hold sequence number, bytes 24-25 hold offset number, byte 26 is flags, bytes 27-30 hold timestamp. Length of non-payload: 40 Bytes
    def parseHeader(self, raw_data):
        ip_src = str(raw_data[4]) + '.' + str(raw_data[5]) + '.' + str(raw_data[6]) + '.' + str(raw_data[7])
        sPort = (raw_data[10] << 8) + raw_data[11]
        ip_dest = str(raw_data[12]) + '.' + str(raw_data[13]) + '.' + str(raw_data[14]) + '.' + str(raw_data[15])
        dPort = (raw_data[18] << 8) + raw_data[19]
        seqn = (raw_data[20] << 24) + (raw_data[21] << 16) + (raw_data[22] << 8) + raw_data[23]
        hdr = RTPhdr(ip_src, sPort, ip_dest, dPort, seqn)
        hdr.offset = (raw_data[24] << 24) + (raw_data[25] << 16) + (raw_data[26] << 8) + raw_data[27]
        hdr.sPort_udp = (raw_data[8] << 8) + raw_data[9]
        hdr.dPort_udp = (raw_data[16] << 8) + raw_data[17]
        hdr.POS = raw_data[28] ^32 < raw_data[28]
        hdr.GET = raw_data[28] ^16 < raw_data[28]
        hdr.SYN = raw_data[28] ^ 8 < raw_data[28]
        hdr.ACK = raw_data[28] ^ 4 < raw_data[28]
        hdr.BEG = raw_data[28] ^ 2 < raw_data[28]
        hdr.FIN = raw_data[28] ^ 1 < raw_data[28]
        hdr.timestamp = (raw_data[29] << 24) + (raw_data[30] << 16) + (raw_data[31] << 8) + raw_data[32]
        hdr.ackn = (raw_data[33] << 24) + (raw_data[34] << 16) + (raw_data[35] << 8) + raw_data[36]
        hdr.rwnd = (raw_data[37] << 16) + (raw_data[38] << 8) + raw_data[39]
        return hdr

#      Returns the byte array of the packet, checksum needs to be 
#      converted to one byte and appended to the front of the byte array, 
#      header bytes need to be encoded and appended after the checksum byte 
#      and the length byte, data bytes last. IT IS POSSIBLE FOR DATA TO BE None.
    def toByteArray(self):
        content = []
        content.append(self.checksum >> 8)                                          #byte 0
        content.append(self.checksum - ((self.checksum >> 8) << 8))                 
        content.append(self.length >> 8)                                            #byte 2
        content.append(self.length - ((self.length >> 8) << 8)) 
        content.append(int(self.hdr.ip_src.split('.')[0]))                          #byte 4
        content.append(int(self.hdr.ip_src.split('.')[1]))                               
        content.append(int(self.hdr.ip_src.split('.')[2]))
        content.append(int(self.hdr.ip_src.split('.')[3]))
        content.append(self.hdr.sPort_udp >> 8)
        content.append(self.hdr.sPort_udp - ((self.hdr.sPort_udp >> 8) << 8))
        content.append(self.hdr.sPort >> 8)
        content.append(self.hdr.sPort - ((self.hdr.sPort >> 8) << 8))
        content.append(int(self.hdr.ip_dest.split('.')[0]))                         #byte 12
        content.append(int(self.hdr.ip_dest.split('.')[1]))
        content.append(int(self.hdr.ip_dest.split('.')[2]))
        content.append(int(self.hdr.ip_dest.split('.')[3]))
        content.append(self.hdr.dPort_udp >> 8)
        content.append(self.hdr.dPort_udp - ((self.hdr.dPort_udp >> 8) << 8))
        content.append(self.hdr.dPort >> 8)
        content.append(self.hdr.dPort - ((self.hdr.dPort >> 8) << 8))               
        content.append(self.hdr.seqn >> 24)                                         #byte 20
        content.append((self.hdr.seqn >> 16) - ((self.hdr.seqn >> 24) << 8))
        content.append((self.hdr.seqn >> 8) - ((self.hdr.seqn >> 16) << 8))
        content.append(self.hdr.seqn - ((self.hdr.seqn >> 8) << 8))
        content.append(self.hdr.offset >> 24)                                       #byte 24
        content.append((self.hdr.offset >> 16) - ((self.hdr.offset >> 24) << 8))
        content.append((self.hdr.offset >> 8) - ((self.hdr.offset >> 16) << 8))
        content.append(self.hdr.offset - ((self.hdr.offset >> 8) << 8))
        content.append((int(self.hdr.POS) << 5) + (int(self.hdr.GET) << 4) + (int(self.hdr.SYN) << 3) + (int(self.hdr.ACK) << 2) + (int(self.hdr.BEG) << 1) + int(self.hdr.FIN))
        content.append(self.hdr.timestamp >> 24)                                    #byte 29
        content.append((self.hdr.timestamp >> 16) - ((self.hdr.timestamp >> 24) << 8))
        content.append((self.hdr.timestamp >> 8) - ((self.hdr.timestamp >> 16) << 8))
        content.append(self.hdr.timestamp - ((self.hdr.timestamp >> 8) << 8))       #byte 32
        content.append(self.hdr.ackn >> 24)                                         #byte 33        
        content.append((self.hdr.ackn >> 16) - ((self.hdr.ackn >> 24) << 8))
        content.append((self.hdr.ackn >> 8) - ((self.hdr.ackn >> 16) << 8))
        content.append(self.hdr.ackn - ((self.hdr.ackn >> 8) << 8))                 #byte 36
        content.append(self.hdr.rwnd >> 16)                                         #byte 37
        content.append((self.hdr.rwnd >> 8) - ((self.hdr.rwnd >> 16) << 8))
        content.append(self.hdr.rwnd - ((self.hdr.rwnd >> 8) << 8))                 #byte 39
        if(self.data):
            for char in self.data:
                content.append(char)
        return bytes(content)

#returns the payload of a packet byte array in string format    
    def truncate(self, raw_data):
        return(raw_data[37 : (raw_data[2] << 8) + raw_data[3]].decode())

    def examineChksum(self):
        return((sum(self.toByteArray()[2:]) % 0xffff) == self.checksum)

class RTPhdr:
    def __init__(self, ip_src, sPort, ip_dest, dPort, seqn):
        self.ip_src = ip_src
        self.sPort = sPort
        self.ip_dest = ip_dest
        self.dPort = dPort
        self.sPort_udp = 0
        self.dPort_udp = 0
        self.seqn = seqn
        self.ackn = 0
        self.offset = 0 #used for file transfer
        self.POS = False
        self.SYN = False
        self.ACK = False
        self.BEG = False
        self.FIN = False
        self.GET = False
        self.rwnd = 0
        self.timestamp = int(time.time())

    def updateTimestamp(self):
        self.timestamp = int(time.time())