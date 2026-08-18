from core.corgi_interface import CorgiInterface
import sys


if __name__ == "__main__":
    gcode_file = open(sys.argv[1], "r").readlines()
    address = sys.argv[2]

    corgi_interface = CorgiInterface()
    corgi_interface.connect()

    print("Sending GCode")
    corgi_interface._prime_commands(gcode_file)
    print("Done")
