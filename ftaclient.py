import RTP
import sys
import socket
import random

def main():
    if len(sys.argv) != 3:
        print("Requires an IP address and port number to send to, as well as the window size.")
        return -1
    else:
        arg1 = sys.argv[1].split(":")
        host_ip = socket.gethostbyname(socket.gethostname())
        host_port = int(arg1[1]) + 1
        dest_ip = arg1[0]
        port = int(arg1[1])
        window = int(sys.argv[2])
        r = RTP.RTP(host_ip, random.randint(0, 65535), random.randint(0, 65535), False, window)
        r.connect(dest_ip, port, port)
        print("Connected to server at " + str(dest_ip) + ':' + str(port))
        comm = None
        while (not comm or (comm and comm[0].lower() != "disconnect")):
            comm = input("Enter a command, or help for available commands: ")
            comm = comm.split(" ")
            if comm[0].lower() == "help":
                print("get F --------- downloads a file F from the server\n")
                print("get-post F G -- downloads F from the server and uploads G\n")
                print("disconnect ---- disconnects from the server and closes the application\n")
            elif comm[0].lower() == "get":
                filename = comm[1]
                r.getFile(filename, dest_ip, port, port)
                print("Downloaded get_{0} from server".format(filename))
            elif comm[0].lower() == "get-post":
                getFile = comm[1]
                sendFile = comm[2]
                r.getPost(getFile, sendFile, dest_ip, port, port)
                print("Downloaded get_{0}, sent post_{1}".format(getFile, sendFile))
            elif comm[0].lower() == "disconnect":
                r.close(dest_ip, port, port)
                print("Disconnected from server at {0}.  Goodbye!".format(dest_ip))
                break

main()
      