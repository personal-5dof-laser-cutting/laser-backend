from core.corgi_interface import CorgiInterface
import sys
import threading


if __name__ == "__main__":
    gcode_file = open(sys.argv[1], "r").readlines()
    address = sys.argv[2]

    interface = CorgiInterface(address)
    threading.Thread(target=interface.main_loop, daemon=True).start()

    print("Sending GCode")
    interface.send_lines(gcode_file)
    print("Done")
