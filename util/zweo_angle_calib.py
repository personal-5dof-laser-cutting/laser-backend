from core.corgi_interface import corgi_interface
import sys
import threading
import numpy as np


MAX_POWER = 1000
material_thickness: float


def home():
    corgi_interface.send_line("$h")


def move(x: float, y: float, a: float = 0, b: float = 0):
    corgi_interface.send_line(f"G0 X{x:z.3f} Y{y:z.3f} Z{material_thickness} A{a} B{b}")
    # print(f"Move {x} {y} {a} {b}")


def laser_on(laser_power: float):
    corgi_interface.send_line("M8")  # air assist on
    corgi_interface.send_line(f"M4 S{laser_power:z.3f}")
    # print(f"Laser on {laser_power}")


def laser_off():
    corgi_interface.send_line("M4 S0")
    corgi_interface.send_line("M8.1")  # air assist off
    # print("Laser off")


def set_feedrate(feedrate: float):
    corgi_interface.send_line(f"F{feedrate:z.2f}")


def cut(x: float, y: float, a: float = 0, b: float = 0):
    corgi_interface.send_line(f"G1 X{x} Y{y} Z{material_thickness} A{a} B{b}")
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
    material_thickness = float(sys.argv[2])

    threading.Thread(target=corgi_interface.main_loop, daemon=True).start()
    # interface = Mock()

    if input("Needs homing? y/n") == "y":
        home()

    set_feedrate(600)
    x = 200
    y = 200
    if input(f"Go to x={x} y={y}? y/n") == "y":
        laser_off()
        move(x, y)

    input("Start?")
    cuts = []
    diff = 1.5
    power = 15

    delta_0 = 0
    # - 0.18125

    length = 5

    cuts.append(Cut(x - diff, y, 0, -45, x - diff, y + length, 0, -45 + delta_0, power))
    cuts.append(Cut(x, y, 0, 0, x, y + length, 0, 0 + delta_0, power))
    cuts.append(Cut(x + diff, y, 0, 45, x + diff, y + length, 0, 45 + delta_0, power))

    # sort_cuts(cuts)

    for c in cuts:
        c.do()
    input("done?")
