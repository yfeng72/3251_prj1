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
        self.rwnd = receiveWindow
        self.cwnd = {}                                              #dictionary, congestion window size for each host
        self.destrwnd = {}
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   #s is the socket
        self.s.bind(('', udp_port))
        self.s.setblocking(0)
        self.seqn = 0 # sequence number
        self.state = {}                                             #dictionary, key is client address & port tuple, value is connection state
        self.files = {}                                             #dictionary, key is client address & port tuple, value is list of file segments in order
        self.acks = {}
        self.sentbfr = {}
        self.filebfr = {}
        self.filename = {}
        self.offsets = {}
        self.firstpkts = {}
        self.timers = {}

    def connect(self, ip_dest, uPort, dPort): #client-side establishment of connection
        synpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, 0)
        synpkt_hdr.SYN = True
        synpkt_hdr.sPort_udp = self.udp_port
        synpkt_hdr.dPort_udp = uPort
        synpkt_hdr.rwnd = self.rwnd
        synpkt = RTPpkt(synpkt_hdr, None, False)
        addr = ip_dest, uPort
        self.s.sendto(synpkt.toByteArray(), addr)
        self.seqn += 1
        data = ''
        while (not data):
            if (int(time.time()) > (synpkt.hdr.timestamp + 2)):
                synpkt.hdr.seqn = self.seqn
                synpkt.hdr.updateTimestamp()
                synpkt.checkSum()
                self.s.sendto(synpkt.toByteArray(), addr)
                self.seqn += 1
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                pass
        synack = RTPpkt(None, data, True)
        if (synack.examineChksum() and synack.hdr.SYN and synack.hdr.ACK):
            self.destrwnd[synack.hdr.sPort] = synack.hdr.rwnd
            ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, 0)
            ackpkt_hdr.ACK = True
            ackpkt_hdr.sPort_udp = self.udp_port
            ackpkt_hdr.dPort_udp = uPort
            ackpkt_hdr.ackn = synack.hdr.seqn
            ackpkt = RTPpkt(ackpkt_hdr, None, False)
            self.s.sendto(ackpkt.toByteArray(), addr)
            self.seqn += 1
            self.state[ip_dest, uPort, dPort] = Connection.CONNECTED

    def accept(self, ip_client, uPort, dPort, ackn, rwnd): #server-side acceptance of connection
        synack_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_client, dPort, self.seqn)
        synack_hdr.ACK = True
        synack_hdr.SYN = True
        synack_hdr.sPort_udp = self.udp_port
        synack_hdr.dPort_udp = uPort
        synack_hdr.ackn = ackn
        synack_hdr.rwnd = self.rwnd
        synack = RTPpkt(synack_hdr, None, False)
        self.destrwnd[dPort] = rwnd
        self.s.sendto(synack.toByteArray(), (ip_client, uPort))
        self.seqn += 1
        self.state[ip_client, uPort, dPort] = Connection.CONNECTED
        self.cwnd[dPort] = 1


    def queue(self, pkt): #queues a packet to sending packet list
        rtp_addr = pkt.hdr.ip_dest, pkt.hdr.dPort_udp, pkt.hdr.dPort
        if (rtp_addr not in self.pktQ):
            self.pktQ[rtp_addr] = []
        self.pktQ[rtp_addr].append(pkt)

#server-side iteration over pktQ and send one for each client, handles slow start, congestion control, and recovery from lost packets
    def sendpkts(self):
        faults = {}
        for (ip_dest, uPort, dPort) in self.pktQ:
            faults[dPort] = False
            #triple duplicate ACK
            if (dPort in self.acks and len(self.acks[dPort]) >= 3 and self.acks[dPort][-1][0] > 0):
                if (self.acks[dPort][-1][0] == self.acks[dPort][-2][0] and self.acks[dPort][-1][0] == self.acks[dPort][-3][0]):
                    self.cwnd[dPort] = int(self.cwnd[dPort] / 2)
                    faults[dPort] = True
                    if (self.cwnd[dPort] < 1):
                        self.cwnd[dPort] = 1
                    if (dPort in self.sentbfr):
                        for pkt in reversed(self.sentbfr[dPort]):
                            self.pktQ[ip_dest, uPort, dPort].insert(0, pkt)
                        self.sentbfr[dPort] = []
                    self.acks[dPort].pop(-1)
                    self.acks[dPort].pop(-1)
            #timeout
            if (dPort in self.sentbfr and self.sentbfr[dPort] and time.time() > self.sentbfr[dPort][-1].hdr.timestamp + 2):
                faults[dPort] = True
                self.cwnd[dPort] = 1
                if (dPort in self.sentbfr):
                    for pkt in reversed(self.sentbfr[dPort]):
                        self.pktQ[ip_dest, uPort, dPort].insert(0, pkt)
                    self.sentbfr[dPort] = []
            #send packets that are within cwnd
            if (self.pktQ[ip_dest, uPort, dPort]):
                sndpkt = self.pktQ[ip_dest, uPort, dPort][0]
                if (dPort not in self.sentbfr):
                    sndpkt.hdr.updateTimestamp()
                    sndpkt.hdr.seqn = self.seqn
                    sndpkt.checkSum()
                    self.s.sendto(sndpkt.toByteArray(), (sndpkt.hdr.ip_dest, sndpkt.hdr.dPort_udp))
                    time.sleep(.01)
                    self.seqn += 1
                    self.pktQ[ip_dest, uPort, dPort].pop(0)
                    self.sentbfr[dPort] = [sndpkt]
                elif (len(self.sentbfr[dPort]) < self.cwnd[dPort]):
                    sndpkt.hdr.updateTimestamp()
                    sndpkt.hdr.seqn = self.seqn
                    sndpkt.checkSum()
                    self.s.sendto(sndpkt.toByteArray(), (sndpkt.hdr.ip_dest, sndpkt.hdr.dPort_udp))
                    time.sleep(.01)
                    self.seqn += 1
                    self.pktQ[ip_dest, uPort, dPort].pop(0)
                    self.sentbfr[dPort].append(sndpkt)
        return faults


    def close(self, ip_dest, uPort, dPort):
        if (self.server): #server-side close connection, sends FINACK
            finack_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            finack_hdr.FIN = True
            finack_hdr.ACK = True
            finack_hdr.sPort_udp = self.udp_port
            finack_hdr.dPort_udp = uPort
            finack = RTPpkt(finack_hdr, None, False)
            self.s.sendto(finack.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            self.state.pop((ip_dest, uPort, dPort), None)
            self.pktQ.pop((ip_dest, uPort, dPort), None)
            self.sentbfr.pop(dPort, None)
            self.acks.pop(dPort, None)
        else: #client-side close connection, sends FIN, receive FINACK
            finpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            finpkt_hdr.FIN = True
            finpkt_hdr.sPort_udp = self.udp_port
            finpkt_hdr.dPort_udp = uPort
            finpkt = RTPpkt(finpkt_hdr, None, False)
            self.s.sendto(finpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            finpkt.hdr.seqn = self.seqn
            currentTime = time.time()
            while (1):
                try:
                    data, addr = self.s.recvfrom(1024)
                except:
                    if (time.time() > currentTime + 2):
                        finpkt.checkSum()
                        self.s.sendto(finpkt.toByteArray(), (ip_dest, uPort))
                        self.seqn += 1
                        finpkt.hdr.seqn = self.seqn
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
        faults = self.sendpkts()
        data = ''
        #scan for new packets
        try:
            data, addr = self.s.recvfrom(1024)
        except:
            return
        if (not data):
            print('no data');
            return
        rcvpkt = RTPpkt(None, data, True)
        if (not rcvpkt.examineChksum()):
            return
        if (rcvpkt.hdr.SYN):
            self.accept(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort, rcvpkt.hdr.seqn, rcvpkt.hdr.rwnd)
            return
        if (rcvpkt.hdr.FIN and (not rcvpkt.hdr.ACK) and (not rcvpkt.hdr.POS)):
            self.close(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)
            return
        #checks for connection
        if ((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort) not in self.state):
            return
        if (rcvpkt.hdr.GET):
            ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort, self.seqn)
            ackpkt_hdr.sPort_udp = self.udp_port
            ackpkt_hdr.dPort_udp = rcvpkt.hdr.sPort_udp
            ackpkt_hdr.ACK = True
            ackpkt_hdr.ackn = rcvpkt.hdr.seqn
            ackpkt = RTPpkt(ackpkt_hdr, None, False)
            self.s.sendto(ackpkt.toByteArray(), (rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp))
            self.seqn += 1
            self.sentbfr.pop(rcvpkt.hdr.sPort, None)
            self.pktQ.pop((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort), None)
            self.acks.pop(rcvpkt.hdr.sPort, None)
            self.sendFile(rcvpkt.data.decode(), rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort, False)
            return
        #handles ACK packets received
        elif (rcvpkt.hdr.ACK):
            if (rcvpkt.hdr.TER): #ends file transfer
                self.sentbfr.pop(rcvpkt.hdr.sPort, None)
                self.pktQ.pop((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort), None)
                self.acks.pop(rcvpkt.hdr.sPort, None)
                terack_hdr = RTPhdr(self.ip_addr, self.rtp_port, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort, self.seqn)
                terack_hdr.ACK = True
                terack_hdr.ackn = rcvpkt.hdr.seqn
                terack_hdr.dPort_udp = rcvpkt.hdr.sPort_udp
                terack_hdr.sPort_udp = self.udp_port
                terack = RTPpkt(terack_hdr, None, False)
                self.s.sendto(terack.toByteArray(), (terack.hdr.ip_dest, terack.hdr.dPort_udp))
                self.seqn += 1
                return
            if (rcvpkt.hdr.offset > 0):
                if (rcvpkt.hdr.sPort not in self.acks):
                    self.acks[rcvpkt.hdr.sPort] = [(rcvpkt.hdr.offset, rcvpkt.hdr.FIN, time.time())]
                else:
                    self.acks[rcvpkt.hdr.sPort].append((rcvpkt.hdr.offset, rcvpkt.hdr.FIN, time.time()))
                if (rcvpkt.hdr.sPort in self.sentbfr):
                    rcvpkts = [pkt for pkt in self.sentbfr[rcvpkt.hdr.sPort] if pkt.hdr.offset < rcvpkt.hdr.offset]
                    for pkt in rcvpkts:
                        self.sentbfr[rcvpkt.hdr.sPort].remove(pkt)
                    for pkt in self.pktQ[(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)]:
                        if (pkt.hdr.offset < rcvpkt.hdr.offset):
                            self.pktQ[(rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort)].remove(pkt)
            #congestion control
            if (rcvpkt.hdr.sPort not in faults or (rcvpkt.hdr.sPort in faults and faults[rcvpkt.hdr.sPort] == False)):
                self.cwnd[rcvpkt.hdr.sPort] = min(self.cwnd[rcvpkt.hdr.sPort] + 1, self.destrwnd[rcvpkt.hdr.sPort])
        #handles POST
        elif (rcvpkt.hdr.POS):
            if (rcvpkt.hdr.BEG):
                if (rcvpkt.data.decode() not in self.filebfr):
                    self.filebfr[rcvpkt.data.decode()] = {}
                    self.filename[rcvpkt.hdr.sPort] = rcvpkt.data.decode()
                    self.offsets[rcvpkt.hdr.sPort] = [0, 0]
                    self.firstpkts[rcvpkt.hdr.sPort] = False
                ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort, self.seqn)
                ackpkt_hdr.sPort_udp = self.udp_port
                ackpkt_hdr.dPort_udp = rcvpkt.hdr.sPort_udp
                ackpkt_hdr.ACK = True
                ackpkt_hdr.ackn = rcvpkt.hdr.seqn
                ackpkt_hdr.rwnd = int(self.rwnd / len(self.state)) + 1
                ackpkt = RTPpkt(ackpkt_hdr, None, False)
                self.s.sendto(ackpkt.toByteArray(), (rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp))
                self.seqn += 1
                return
            if (rcvpkt.hdr.sPort not in self.offsets):
                return
            if (rcvpkt.hdr.offset >= self.offsets[rcvpkt.hdr.sPort][0] and rcvpkt.hdr.offset < (self.offsets[rcvpkt.hdr.sPort][0] + (self.rwnd / len(self.offsets) + 1))):
                self.filebfr[self.filename[rcvpkt.hdr.sPort]][rcvpkt.hdr.offset] = (rcvpkt.data, rcvpkt.hdr.FIN)
                if (rcvpkt.hdr.offset == 0):
                    self.firstpkts[rcvpkt.hdr.sPort] = True
            if (0 not in self.filebfr[self.filename[rcvpkt.hdr.sPort]]):
                if (rcvpkt.hdr.sPort not in self.firstpkts):
                    return
                if (self.firstpkts[rcvpkt.hdr.sPort] == False):
                    return
            while (1):
                if (self.offsets[rcvpkt.hdr.sPort][1] not in self.filebfr[self.filename[rcvpkt.hdr.sPort]]):
                    break
                self.offsets[rcvpkt.hdr.sPort][1] += 1
            ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort, self.seqn)
            ackpkt_hdr.sPort_udp = self.udp_port
            ackpkt_hdr.dPort_udp = rcvpkt.hdr.sPort_udp
            ackpkt_hdr.ACK = True
            ackpkt_hdr.offset = self.offsets[rcvpkt.hdr.sPort][1]
            ackpkt_hdr.FIN = self.filebfr[self.filename[rcvpkt.hdr.sPort]][self.offsets[rcvpkt.hdr.sPort][1]][1] if (self.offsets[rcvpkt.hdr.sPort][1] in self.filebfr[self.filename[rcvpkt.hdr.sPort]]) else False
            ackpkt_hdr.rwnd = int(self.rwnd / len(self.state)) + 1
            ackpkt = RTPpkt(ackpkt_hdr, None, False)
            self.s.sendto(ackpkt.toByteArray(), (rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp))
            self.seqn += 1
            time.sleep(.01)
            if (0 in self.filebfr[self.filename[rcvpkt.hdr.sPort]]):
                with open('post_' + self.filename[rcvpkt.hdr.sPort], 'wb') as f:
                    f.write(bytes(self.filebfr[self.filename[rcvpkt.hdr.sPort]][0][0]))
                fin = self.filebfr[self.filename[rcvpkt.hdr.sPort]].pop(0)[1]
                if (fin):
                    terpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
                    terpkt_hdr.sPort_udp = self.udp_port
                    terpkt_hdr.dPort_udp = uPort
                    terpkt_hdr.ACK = True
                    terpkt_hdr.TER = True
                    terpkt = RTPpkt(terpkt_hdr, None, False)
                    self.s.sendto(terpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
                    self.filebfr.pop(self.filename[rcvpkt.hdr.sPort], None)
                    self.filename.pop(rcvpkt.hdr.sPort, None)
                    self.offsets.pop(rcvpkt.hdr.sPort, None)
                    self.checkACK(terpkt)
                    return
                self.offsets[rcvpkt.hdr.sPort][0] = 0    
                return
            for i in range(self.offsets[rcvpkt.hdr.sPort][0] + 1, self.offsets[rcvpkt.hdr.sPort][1]):
                with open('post_' + self.filename[rcvpkt.hdr.sPort], 'ab') as f:
                    f.write(bytes(self.filebfr[self.filename[rcvpkt.hdr.sPort]][i][0]))
                fin = self.filebfr[self.filename[rcvpkt.hdr.sPort]].pop(i)[1]
                if (fin):
                    terpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort, self.seqn)
                    terpkt_hdr.sPort_udp = self.udp_port
                    terpkt_hdr.dPort_udp = rcvpkt.hdr.sPort_udp
                    terpkt_hdr.ACK = True
                    terpkt_hdr.TER = True
                    terpkt = RTPpkt(terpkt_hdr, None, False)
                    self.s.sendto(terpkt.toByteArray(), (rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp))
                    self.seqn += 1
                    self.filebfr.pop(self.filename[rcvpkt.hdr.sPort], None)
                    self.filename.pop(rcvpkt.hdr.sPort, None)
                    self.offsets.pop(rcvpkt.hdr.sPort, None)
                    self.checkACK(terpkt)
                    return
            self.offsets[rcvpkt.hdr.sPort][0] = self.offsets[rcvpkt.hdr.sPort][1] - 1

        #handles single request packets (from dbclient), sends ACK   
        else:
            ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort, self.seqn)
            ackpkt_hdr.sPort_udp = self.udp_port
            ackpkt_hdr.dPort_udp = rcvpkt.hdr.sPort_udp
            ackpkt_hdr.ACK = True
            ackpkt_hdr.ackn = rcvpkt.hdr.seqn
            ackpkt = RTPpkt(ackpkt_hdr, None, False)
            self.s.sendto(ackpkt.toByteArray(), (rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp))
            self.seqn += 1
            return((rcvpkt.data, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort))

        

    def getPost(self, getName, postName, ip_dest, uPort, dPort): #client-side get-post
        #sends GET
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt_hdr.GET = True
        sndpkt = RTPpkt(sndpkt_hdr, getName.encode(), False)
        sndpkt.hdr.seqn = self.seqn
        sndpkt.checkSum()
        self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
        self.seqn += 1
        self.checkACK(sndpkt)
        #sends POST
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt_hdr.BEG = True
        sndpkt_hdr.POS = True
        sndpkt = RTPpkt(sndpkt_hdr, postName.encode(), False)
        sndpkt.hdr.seqn = self.seqn
        sndpkt.checkSum()
        self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
        self.seqn += 1
        ackpkt = self.checkACK(sndpkt)
        #iteratively get and post file
        self.destrwnd[ackpkt.hdr.sPort] = ackpkt.hdr.rwnd
        self.acks[ackpkt.hdr.sPort] = []
        self.sentbfr[ackpkt.hdr.sPort] = []
        self.cwnd[ackpkt.hdr.sPort] = 1
        self.sendFile(postName, ip_dest, uPort, dPort, True)
        pfin = False
        gfin = False
        terackrecv = False
        segments = {}
        offset = 0
        offsetn = 0
        currentTime = time.time()
        currentTime2 = time.time()
        firstpkt = False
        terpkt = ''
        while ((not pfin) or (not gfin)):
            faults = self.sendpkts()
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                continue
            rcvpkt = RTPpkt(None, data, True)
            if (rcvpkt.hdr.dPort != self.rtp_port or not rcvpkt.examineChksum()):
                continue
            if (gfin):
                if (rcvpkt.hdr.ACK and rcvpkt.hdr.ackn == terpkt.hdr.seqn):
                    terackrecv = True
                if (not terackrecv):
                    terpkt.hdr.seqn = self.seqn
                    self.s.sendto(terpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
            if (rcvpkt.hdr.ACK):
                if (rcvpkt.hdr.TER): #ends file transfer
                    self.sentbfr.pop(rcvpkt.hdr.sPort, None)
                    self.pktQ.pop((rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort_udp, rcvpkt.hdr.sPort), None)
                    self.acks.pop(rcvpkt.hdr.sPort, None)
                    terack_hdr = RTPhdr(self.ip_addr, self.rtp_port, rcvpkt.hdr.ip_src, rcvpkt.hdr.sPort, self.seqn)
                    terack_hdr.ACK = True
                    terack_hdr.ackn = rcvpkt.hdr.seqn
                    terack_hdr.dPort_udp = rcvpkt.hdr.sPort_udp
                    terack_hdr.sPort_udp = self.udp_port
                    terack = RTPpkt(terack_hdr, None, False)
                    self.s.sendto(terack.toByteArray(), (terack.hdr.ip_dest, terack.hdr.dPort_udp))
                    self.seqn += 1
                    pfin = True
                    continue
                if (rcvpkt.hdr.offset > 0):
                    if (rcvpkt.hdr.sPort not in self.acks):
                        self.acks[rcvpkt.hdr.sPort] = [(rcvpkt.hdr.offset, rcvpkt.hdr.FIN, time.time())]
                    else:
                        self.acks[rcvpkt.hdr.sPort].append((rcvpkt.hdr.offset, rcvpkt.hdr.FIN, time.time()))
                    if (rcvpkt.hdr.sPort in self.sentbfr):
                        rcvpkts = [pkt for pkt in self.sentbfr[rcvpkt.hdr.sPort] if pkt.hdr.offset < rcvpkt.hdr.offset]
                        for pkt in rcvpkts:
                            self.sentbfr[rcvpkt.hdr.sPort].remove(pkt)
                #congestion control
                if (rcvpkt.hdr.sPort not in faults or (rcvpkt.hdr.sPort in faults and faults[rcvpkt.hdr.sPort] == False)):
                    self.cwnd[rcvpkt.hdr.sPort] = min(self.cwnd[rcvpkt.hdr.sPort] + 1, self.destrwnd[rcvpkt.hdr.sPort])
            else:
                if (rcvpkt.hdr.offset < offset + self.rwnd + 1 and rcvpkt.hdr.offset >= offset):
                    segments[rcvpkt.hdr.offset] = (rcvpkt.data, rcvpkt.hdr.FIN)
                    if (rcvpkt.hdr.offset == 0):
                        firstpkt = True
                if (0 not in segments and not firstpkt):
                    continue
                offsetn = offset + 1
                while (1):
                    if (not offsetn in segments):
                        break
                    offsetn += 1
                if (time.time() > currentTime + .02):
                    ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
                    ackpkt_hdr.sPort_udp = self.udp_port
                    ackpkt_hdr.dPort_udp = uPort
                    ackpkt_hdr.ACK = True
                    ackpkt_hdr.offset = offsetn
                    ackpkt_hdr.FIN = segments[offsetn][1] if (offsetn in segments) else False
                    ackpkt = RTPpkt(ackpkt_hdr, None, False)
                    self.s.sendto(ackpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
                    currentTime = time.time()
                if (0 in segments):
                    with open('get_' + getName, 'wb') as f:
                        f.write(bytes(segments[0][0]))
                    fin = segments.pop(0)[1]
                    if (fin):
                        terpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
                        terpkt_hdr.sPort_udp = self.udp_port
                        terpkt_hdr.dPort_udp = uPort
                        terpkt_hdr.ACK = True
                        terpkt_hdr.TER = True
                        terpkt = RTPpkt(terpkt_hdr, None, False)
                        self.s.sendto(terpkt.toByteArray(), (ip_dest, uPort))
                        self.seqn += 1
                        currentTime2 = time.time()
                        gfin = True
                    offset = 0    
                    continue
                for i in range(offset + 1, offsetn):
                    with open('get_' + getName, 'ab') as f:
                        f.write(bytes(segments[i][0]))
                    fin = segments.pop(i)[1]
                    if (fin):
                        terpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
                        terpkt_hdr.sPort_udp = self.udp_port
                        terpkt_hdr.dPort_udp = uPort
                        terpkt_hdr.ACK = True
                        terpkt_hdr.TER = True
                        terpkt = RTPpkt(terpkt_hdr, None, False)
                        self.s.sendto(terpkt.toByteArray(), (ip_dest, uPort))
                        self.seqn += 1
                        currentTime2 = time.time()
                        gfin = True
                        break
                offset = offsetn - 1
        if (not terack):
            checkACK(terpkt)




#checks for ACK and reorders packet for window size 1, returns when ACK is received
    def checkACK(self, sndpkt):
        currentTime = time.time()
        while (1):
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                if (time.time() > currentTime + 2):
                    sndpkt.hdr.seqn = self.seqn
                    sndpkt.checkSum()
                    self.s.sendto(sndpkt.toByteArray(), (sndpkt.hdr.ip_dest, sndpkt.hdr.dPort_udp))
                    currentTime = time.time()
                    self.seqn += 1
                continue
            ackpkt = RTPpkt(None, data, True)
            if (ackpkt.examineChksum() and ackpkt.hdr.dPort == self.rtp_port and ackpkt.hdr.ACK and ackpkt.hdr.ackn == sndpkt.hdr.seqn):
                return ackpkt
            if (time.time() > currentTime + 2):
                sndpkt.hdr.seqn = self.seqn
                sndpkt.checkSum()
                self.s.sendto(sndpkt.toByteArray(), (sndpkt.hdr.ip_dest, sndpkt.hdr.dPort_udp))
                currentTime = time.time()
                self.seqn += 1


#Client-side get file form server, ACK packets' offset numbers are set to maximum sequentially received offset number + 1
    def getFile(self, filename, ip_dest, uPort, dPort): 
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt_hdr.GET = True
        sndpkt = RTPpkt(sndpkt_hdr, filename.encode(), False)
        self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
        self.seqn += 1
        segments = {}
        offset = 0
        offsetn = 0
        fin = False
        firstpkt = False
        currentTime = time.time()
        while (not fin):
            try:
                data, addr = self.s.recvfrom(1024)
            except:
                if (time.time() > currentTime + 2.5):
                    sndpkt.hdr.seqn = self.seqn
                    sndpkt.checkSum()
                    self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
                    currentTime = time.time()
                continue
            rcvpkt = RTPpkt(None, data, True)
            if (rcvpkt.hdr.dPort != self.rtp_port or not rcvpkt.examineChksum() or rcvpkt.hdr.ACK):
                continue
            if (rcvpkt.hdr.offset < offset + self.rwnd + 1 and rcvpkt.hdr.offset >= offset):
                segments[rcvpkt.hdr.offset] = (rcvpkt.data, rcvpkt.hdr.FIN)
                if (rcvpkt.hdr.offset == 0):
                    firstpkt = True
            if (0 not in segments and not firstpkt):
                continue
            offsetn = offset + 1
            while (1):
                if (not offsetn in segments):
                    break
                offsetn += 1
            if (time.time() > currentTime + .02):
                ackpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
                ackpkt_hdr.sPort_udp = self.udp_port
                ackpkt_hdr.dPort_udp = uPort
                ackpkt_hdr.ACK = True
                ackpkt_hdr.offset = offsetn
                ackpkt_hdr.FIN = segments[offsetn][1] if (offsetn in segments) else False
                ackpkt = RTPpkt(ackpkt_hdr, None, False)
                self.s.sendto(ackpkt.toByteArray(), (ip_dest, uPort))
                self.seqn += 1
                currentTime = time.time()
            if (0 in segments):
                with open('get_' + filename, 'wb') as f:
                    f.write(bytes(segments[0][0]))
                fin = segments.pop(0)[1]
                if (fin):
                    terpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
                    terpkt_hdr.sPort_udp = self.udp_port
                    terpkt_hdr.dPort_udp = uPort
                    terpkt_hdr.ACK = True
                    terpkt_hdr.TER = True
                    terpkt = RTPpkt(terpkt_hdr, None, False)
                    self.s.sendto(terpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
                    self.checkACK(terpkt)
                    break
                offset = 0    
                continue
            for i in range(offset + 1, offsetn):
                with open('get_' + filename, 'ab') as f:
                    f.write(bytes(segments[i][0]))
                fin = segments.pop(i)[1]
                if (fin):
                    terpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
                    terpkt_hdr.sPort_udp = self.udp_port
                    terpkt_hdr.dPort_udp = uPort
                    terpkt_hdr.ACK = True
                    terpkt_hdr.TER = True
                    terpkt = RTPpkt(terpkt_hdr, None, False)
                    self.s.sendto(terpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
                    self.checkACK(terpkt)
                    break
            offset = offsetn - 1

            
#both client and server can use this to send a single message
    def send(self, message, ip_dest, uPort, dPort):
        sndpkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
        sndpkt_hdr.sPort_udp = self.udp_port
        sndpkt_hdr.dPort_udp = uPort
        sndpkt = RTPpkt(sndpkt_hdr, message.encode(), False)
        currentTime = time.time()
        if (not self.server):
            sndpkt.checkSum()
            self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            self.checkACK(sndpkt)
        else:
            sndpkt.checkSum()
            self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
            self.seqn += 1
            self.checkACK(sndpkt)

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
        ackpkt = RTPpkt(ackpkt_hdr, None, False)
        self.s.sendto(ackpkt.toByteArray(), (ip_dest, uPort))
        self.seqn += 1
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
        for pktn in range(count):
            pkt_hdr = RTPhdr(self.ip_addr, self.rtp_port, ip_dest, dPort, self.seqn)
            pkt_hdr.offset = pktn
            pkt_hdr.BEG = (pktn == 0) and (self.server)
            pkt_hdr.FIN = (pktn == count - 1)
            pkt_hdr.sPort_udp = self.udp_port
            pkt_hdr.dPort_udp = uPort
            segment = content[pktn * MAXSIZE : len(content)] if (pktn == count - 1) else content[pktn * MAXSIZE : (pktn + 1) * MAXSIZE]
            pkt_hdr.POS = getPost
            sndpkt = RTPpkt(pkt_hdr, segment, False)
            if (self.server):
                self.queue(sndpkt)
            else:
                if (not getPost):
                    self.s.sendto(sndpkt.toByteArray(), (ip_dest, uPort))
                    self.seqn += 1
                else:
                    self.queue(sndpkt)

class RTPpkt:
    def __init__(self, header, data, is_raw_data):
        #data is in the form of String, raw_data is in the form of byte array 
        if (is_raw_data):
            self.checksum = (data[0] << 8) + data[1] 
            self.length = (data[2] << 8) + data[3] 
            self.hdr = self.parseHeader(data)
            self.data = data[40 : (data[2] << 8) + data[3]]
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
        return (self.hdr.seqn == other.hdr.seqn and self.checksum == other.checksum and self.hdr.offset == other.hdr.offset)
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
        self.checksum = sum(self.toByteArray()[2:]) % 0x10000

#Coding header in packet bytes: bytes 4-7 are ip_src, bytes 8-9 are udp port, bytes 10-11 are rtp port of source. Bytes 12-19 are similarly structured for destination
#Bytes 20-23 hold sequence number, bytes 24-27 hold offset number, byte 28 is flags, bytes 29-32 hold timestamp, bytes 34-36 hold ACK number
#Bytes 37-39 hold receive window. Length of non-payload: 40 Bytes
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
        hdr.TER = raw_data[28] ^64 < raw_data[28]
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
        content.append((int(self.hdr.TER) << 6) + (int(self.hdr.POS) << 5) + (int(self.hdr.GET) << 4) + (int(self.hdr.SYN) << 3) + (int(self.hdr.ACK) << 2) + (int(self.hdr.BEG) << 1) + int(self.hdr.FIN))
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
        return((sum(self.toByteArray()[2:]) % 0x10000) == self.checksum)

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
        self.TER = False
        self.rwnd = 0
        self.timestamp = int(time.time())

    def updateTimestamp(self):
        self.timestamp = int(time.time())