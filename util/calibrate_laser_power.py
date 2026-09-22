import math
from core.corgi_interface import CorgiInterface
import sys
import numpy as np

MAX_POWER = 1000
material_thickness: float


def home():
    corgi_interface.send_command("$h")


def move(x: float, y: float, a: float = 0, b: float = 0):
    corgi_interface.send_command(
        f"G0 X{x:z.3f} Y{y:z.3f} Z{material_thickness} A{a} B{b}"
    )
    # print(f"Move {x} {y} {a} {b}")


def laser_on(laser_power: float):
    corgi_interface.send_command("M8")  # air assist on
    corgi_interface.send_command(f"M4 S{laser_power:z.3f}")
    # print(f"Laser on {laser_power}")


def laser_off():
    corgi_interface.send_command("M4 S0")
    corgi_interface.send_command("M8.1")  # air assist off
    # print("Laser off")


def set_feedrate(feedrate: float):
    corgi_interface.send_command(f"F{feedrate:z.2f}")


def cut(x: float, y: float, a: float = 0, b: float = 0):
    corgi_interface.send_command(f"G1 X{x} Y{y} Z{material_thickness} A{a} B{b}")
    # print(f"Cut {x} {y} {a} {b}")


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


def cut_half_groove(
    x: float,
    y: float,
    angle_deg: float,
    width: float,
    length: float,
    laser_power: float,
    margin: float = 0,
) -> list[Cut]:
    offset: float = math.sin(math.radians(angle_deg)) * length

    # |  /
    # | / depth
    # |/
    # |  angle
    # |
    return [
        Cut(
            x + offset,
            y - margin,
            0,
            -angle_deg,
            x + offset,
            y + width + margin,
            0,
            -angle_deg,
            laser_power,
        ),  # angled cut
        Cut(x, y, 0, 0, x, y + width, 0, 0, 255),  # parallel to angled cut
        Cut(x, y + width, 0, 0, x + offset + margin, y + width, 0, 0, 255),
        Cut(x, y, 0, 0, x + offset + margin, y, 0, 0, 255),
    ]


def power_1dgrid(x, y, range: list[float], angle_deg, depth):
    cuts = []
    for power in range:
        print(power)
        cuts.extend(cut_half_groove(x, y, angle_deg, 5, depth, power))
        y += 10
    return cuts


def sort_cuts(cuts: list[Cut]):
    cuts.sort(key=lambda a: (a.start_a, a.start_b, a.start_y, a.start_x))


def cut_v_groove(x: float, y: float, angle_deg: float, width: float, length: float):
    offset: float = math.sin(math.radians(angle_deg)) * length

    move(x - offset, y, 0, angle_deg)
    cut(x - offset, y + width, 0, angle_deg)

    move(x + offset, y + width, 0, -angle_deg)
    cut(x + offset, y, 0, -angle_deg)

    move(x - offset, y + width)
    cut(x + offset, y + width)

    move(x - offset, y)
    cut(x + offset, y)


def super_range(min: int, max: int, steps: int):
    return (np.array(range(0, steps + 2)) / (steps + 1) * (max - min) + min).tolist()


if __name__ == "__main__":
    address = sys.argv[1]
    material_thickness = float(sys.argv[2])

    corgi_interface = CorgiInterface()
    corgi_interface.connect()

    if input("Needs homing? y/n") == "y":
        home()

    set_feedrate(240)

    x = 100
    y = 100

    if input(f"Go to x={x} y={y}? y/n") == "y":
        laser_off()
        move(x, y)

    cuts = power_1dgrid(100, 100, super_range(10, 180, 10), angle_deg=18, depth=5)
    sort_cuts(cuts)
    for c in cuts:
        c.do()
