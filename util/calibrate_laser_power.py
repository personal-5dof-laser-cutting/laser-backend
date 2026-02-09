import math
from core.corgi_interface import CorgiInterface
from gcode_lib.gcode_interface import GCodeInterface
import sys
import threading
from mock import Mock

MAX_POWER = 1000
interface: CorgiInterface
material_height: float


def home():
    interface.send_line("$h")


def move(x: float, y: float):
    interface.send_line(f"G0 X{x:z.3f} Y{y:z.3f} Z{material_height} A0 B0")


def laser_on(laser_power: float):
    interface.send_line("M8")  # air assist on
    interface.send_line(f"M4 S{laser_power:z.3f}")


def laser_off():
    interface.send_line("M4 S0")
    interface.send_line("M8.1")  # air assist off


def set_feedrate(feedrate: float):
    interface.send_line(f"F{feedrate:z.2f}")


def cut(x: float, y: float):
    interface.send_line(f"G1 X{x} Y{y} Z{material_height} A0 B0")


def cut_square(x, y, width=7, height=7):
    move(x, y)
    cut(x + width, y)
    cut(x + width, y + height)
    cut(x, y + height)
    cut(x, y)


def grid():
    for xi, i in enumerate(range(0, 257, 16)):
        for yi, j in enumerate(range(0, 101, 10)):
            if j == 0 or i == 0:
                continue
            power = i
            speed = (j / 100.0) * 20
            x = xi * 6 + 100
            y = yi * 6 + 100
            print(f"Power {power}, speed {speed} mm/s x={x} y={y}")
            set_feedrate(speed * 60)
            laser_on(power)
            cut_square(x, y, 5, 5)
            laser_off()


if __name__ == "__main__":
    address = sys.argv[1]
    material_height = float(sys.argv[2])

    interface = CorgiInterface(GCodeInterface(address))
    threading.Thread(target=interface.main_loop, daemon=True).start()
    # interface = Mock()

    if input("Needs homing? y/n") == "y":
        home()

    if input("Go to x=100 y= 100? y/n") == "y":
        laser_off()
        move(100, 100)

    input("Start? Any key!")

    # grid()

    # sys.exit(0)

    print("Table Calibration Script")
    speed_mm_per_s = 6
    set_feedrate(speed_mm_per_s * 60)  # 10 mm/s
    lower = 0.0
    upper = 255.0
    x = 100
    y = 100
    while lower < upper:
        mid: float = round((lower + upper) / 2.0)
        print(
            f"Cutting square at x={x} y={y} with power {mid} and speed {speed_mm_per_s} mm/s"
        )
        laser_on(mid)
        cut_square(x, y, 8, 8)
        x += 9
        laser_off()
        while (cut_through := input("Did it cut through? y/n: ")) not in ["y", "n"]:
            print("Invalid: please answer with y/n")

        cut_through = cut_through == "y"
        print(f"Material constant {upper / speed_mm_per_s / material_height}")

        if cut_through:
            upper = mid - 1
        else:
            lower = mid + 1
        print(f"New possible power range: {lower} to {upper}\n\n")

    print(f"Material constant {upper / speed_mm_per_s / material_height}")
    print("Done")
