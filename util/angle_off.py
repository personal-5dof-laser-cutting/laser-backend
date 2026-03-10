import math
from core.corgi_interface import CorgiInterface
from gcode_lib.gcode_interface import GCodeInterface
import sys
import threading
import numpy as np
from mock import Mock

from util.calibrate_laser_power import sort_cuts

MAX_POWER = 1000
interface: CorgiInterface
material_height: float


def home():
    interface.send_line("$h")


def move(x: float, y: float, a: float = 0, b: float = 0):
    interface.send_line(f"G0 X{x:z.3f} Y{y:z.3f} Z{material_height} A{a} B{b}")
    # print(f"Move {x} {y} {a} {b}")


def laser_on(laser_power: float):
    interface.send_line("M8")  # air assist on
    interface.send_line(f"M4 S{laser_power:z.3f}")
    # print(f"Laser on {laser_power}")


def laser_off():
    interface.send_line("M4 S0")
    interface.send_line("M8.1")  # air assist off
    # print("Laser off")


def set_feedrate(feedrate: float):
    interface.send_line(f"F{feedrate:z.2f}")


def cut(x: float, y: float, a: float = 0, b: float = 0):
    interface.send_line(f"G1 X{x} Y{y} Z{material_height} A{a} B{b}")
    # print(f"Cut {x} {y} {a} {b}")


def super_range(min: int, max: int, steps: int):
    return (np.array(range(0, steps + 2)) / (steps + 1) * (max - min) + min).tolist()


class Cut:
    def __init__(
        self,
        start_x,
        start_y,
        start_a,
        start_b,
        end_x,
        end_y,
        end_a,
        end_b,
        laser_power,
    ) -> None:
        self.start_x: float = start_x
        self.start_y: float = start_y
        self.start_a: float = start_a
        self.start_b: float = start_b
        self.end_x: float = end_x
        self.end_y: float = end_y
        self.end_a: float = end_a
        self.end_b: float = end_b
        self.laser_power: float = laser_power

    def do(self):
        move(self.start_x, self.start_y, self.start_a, self.start_b)
        laser_on(self.laser_power)
        cut(self.end_x, self.end_y, self.end_a, self.end_b)
        laser_off()


if __name__ == "__main__":
    address = sys.argv[1]
    material_height = float(sys.argv[2])

    interface = CorgiInterface(address)
    threading.Thread(target=interface.main_loop, daemon=True).start()
    # interface = Mock()

    if input("Needs homing? y/n") == "y":
        home()

    set_feedrate(600)
    power = 19
    light_power = 18

    x_o = 100
    y_o = 100

    if input(f"Go to x={x_o} y={y_o}? y/n") == "y":
        laser_off()
        move(x_o, y_o)

    input("Start?")
    cuts = []
    x = x_o
    y = y_o

    cross_size = 1

    for angle in super_range(-45, 45, 11):
        print(angle)
        cuts.append(
            Cut(x - cross_size, y, 0, angle, x + cross_size, y, 0, angle, power)
        )
        cuts.append(
            Cut(x, y - cross_size, 0, angle, x, y + cross_size, 0, angle, power)
        )

        cuts.append(Cut(x + 1, y - 3, 0, 0, x + 1, y + 3, 0, 0, light_power))
        cuts.append(Cut(x, y - 3, 0, 0, x, y + 3, 0, 0, light_power))
        cuts.append(Cut(x - 1, y - 3, 0, 0, x - 1, y + 3, 0, 0, light_power))
        x += 10

    x -= 10

    cuts.append(Cut(x, y + 3, 0, 0, x_o, y_o + 3, 0, 0, light_power))
    cuts.append(Cut(x, y + 2, 0, 0, x_o, y_o + 2, 0, 0, light_power))
    cuts.append(Cut(x, y + 1, 0, 0, x_o, y_o + 1, 0, 0, light_power))
    cuts.append(Cut(x, y, 0, 0, x_o, y_o, 0, 0, power))
    cuts.append(Cut(x, y - 1, 0, 0, x_o, y_o - 1, 0, 0, light_power))
    cuts.append(Cut(x, y - 2, 0, 0, x_o, y_o - 2, 0, 0, light_power))
    cuts.append(Cut(x, y - 3, 0, 0, x_o, y_o - 3, 0, 0, light_power))

    sort_cuts(cuts)

    for c in cuts:
        c.do()

    input("Done?")
