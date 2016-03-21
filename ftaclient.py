from RTP import *
from sys import *

def main():
    if len(sys.argv) != 3:
        print "Requires an IP address and port number to send to, as well as the window size."
        return -1
    else:
        arg1 = sys.args[1].split(":")
        ip = int(arg1[0])
        port = int(arg1[1])
        window = int(sys.argv[2])
        rtp = RTP(ip, port, port, False, window)
        rtp.connect(ip, port, port)
        print(format("Connected to server at {0}", ip))
        comm = None
        while comm.split[0].lower() != "disconnect":
            comm = input("Enter a command, or help for available commands: ")
            comm = comm.split(" ")
            if comm[0].lower() == "help":
                print("get F --------- downloads a file F from the server\n")
                print("get-post F G -- downloads F from the server and uploads G\n")
                print("disconnect ---- disconnects from the server and closes the application\n")
            elif comm[0].lower() == "get":
                filename = comm[1]
                rtp.getFile(filename, ip, port, port)
                print(format("Downloaded get_{0} from server", filename))
            elif comm[0].lower() == "get-post":
                getFile = comm[1]
                sendFile = comm[2]
                rtp.getFile(getFile, ip, port, port)
                rtp.sendFile(sendFile, ip, port, port)
                print(format("Downloaded get_{0}, sent post_{1}", getFile, sendFile))
            elif comm[0].lower() == "disconnect":
                rtp.close(ip, port, port)
                print(format("Disconnected from server at {0}.  Goodbye!", ip))
                break
                
                
