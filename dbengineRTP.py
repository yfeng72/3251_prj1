import RTP
import sys

def main():
    if len(sys.argv) != 3:
        print ("Requires the port number to listen on, as well as the window size.")
        return
    l = [["903076259", "Anthony", "Peterson", 231, 63, 3.666667], ["903084074", "Richard", "Harris", 236, 66, 3.575758], ["903077650", "Joe", "Miller", 224, 65, 3.446154], ["903083691", "Todd", "Collins", 218, 56, 3.892857], ["903082265", "Laura", "Stewart", 207, 64, 3.234375], ["903075951", "Marie", "Cox", 246, 6, 3.904762], ["903084336", "Stephen", "Baker", 234, 66, 3.545455]]
    t = [[j[i] for j in l] for i in range(len(l[0]))]
    c = ['ID', 'first_name', 'last_name', 'quality_points', 'gpa_hours', 'gpa']
    UDP_IP = '127.0.0.1'
    UDP_PORT = int(sys.argv[1])
    RTP_PORT = int(sys.argv[1])
    rwnd = 1
    BUFFER_SIZE = 1024
    #create RTP object
    r = RTP.RTP('127.0.0.1', UDP_PORT, RTP_PORT, True, rwnd)
    while 1:
        k = 1
        result = r.listen()
        if (not result):
            continue
        print ('Connection address:', result[1:])
        data = result[0]
        print('From Client: ' + result)
        ip_dest = result[1]
        uPort = result[2]
        rPort = result[3]
        if len(data) < 2:
            r.send('Illegal inputs.', ip_dest, uPort, rPort)
            k = 0
        m = data.split(',')
        if len(m) < 2:
            r.send('Illegal inputs.', ip_dest, uPort, rPort)
            k = 0
        if m[0] not in t[0]:
            #non-existing GTID
            r.send('Cannot find GTID.', ip_dest, uPort, rPort)
            k = 0
        if not k:
            continue
        row = t[0].index(m[0])
        msg = ""
        for i in m[1:]:
            if i not in c:
                #bad arguments passed in
                r.send(('Non-existing attribute \"' + i + '\".'), ip_dest, uPort, rPort)
                k = 0
                break
            msg += i + ': ' + str(t[c.index(i)][row]) + ', '
        if not k: 
            continue
        #send data
        print(msg)
        r.send(msg[:-2], ip_dest, uPort, rPort)
        print ("Received data:", data)

main()