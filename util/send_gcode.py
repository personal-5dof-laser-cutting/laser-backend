from core.corgi_interface import corgi_interface
import sys
import threading


if __name__ == "__main__":
    gcode_file = open(sys.argv[1], "r").readlines()
    address = sys.argv[2]

    threading.Thread(target=corgi_interface.main_loop, daemon=True).start()

    print("Sending GCode")
    corgi_interface.send_lines(gcode_file)
    print("Done")
