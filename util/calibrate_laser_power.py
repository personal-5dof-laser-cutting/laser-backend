import math
from core.corgi_interface import CorgiInterface
from gcode_lib.gcode_interface import GCodeInterface
import sys
import threading

MAX_POWER = 1000
interface: CorgiInterface
material_height: float


def home():
    interface.send_line("$h")


def move(x: float, y: float, a: float = 0, b: float = 0):
    interface.send_line(f"G0 X{x:z.3f} Y{y:z.3f} Z{material_height} A{a} B{b}")


def laser_on(laser_power: float):
    interface.send_line("M8")  # air assist on
    interface.send_line(f"M4 S{laser_power:z.3f}")


def laser_off():
    interface.send_line("M4 S0")
    interface.send_line("M8.1")  # air assist off


def set_feedrate(feedrate: float):
    interface.send_line(f"F{feedrate:z.2f}")


def cut(x: float, y: float, a: float = 0, b: float = 0):
    interface.send_line(f"G1 X{x} Y{y} Z{material_height} A{a} B{b}")


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


def line():
    for xi, i in enumerate(range(0, 257, 16)):
        if i == 0:
            continue
        power = i
        speed = 5
        x = xi * 6 + 100
        y = 100
        print(f"Power {power}, speed {speed} mm/s x={x} y={y}")
        set_feedrate(speed * 60)
        laser_on(power)
        cut_square(x, y, 5, 5)
        laser_off()


def cut_v_groove(x: float, y: float, angle_deg: float, width: float, depth: float):
    offset: float = math.tan(math.radians(angle_deg)) * depth

    move(x - offset, y, 0, angle_deg)
    cut(x - offset, y + width, 0, angle_deg)

    move(x + offset, y + width, 0, -angle_deg)
    cut(x + offset, y, 0, -angle_deg)

    move(x - offset, y + width)
    cut(x + offset, y + width)

    move(x - offset, y)
    cut(x + offset, y)


def binary_search():
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


if __name__ == "__main__":
    address = sys.argv[1]
    material_height = float(sys.argv[2])

    interface = CorgiInterface(GCodeInterface(address))
    threading.Thread(target=interface.main_loop, daemon=True).start()
    # interface = Mock()

    if input("Needs homing? y/n") == "y":
        home()

    set_feedrate(240)

    x = 100
    y = 100

    if input(f"Go to x={x} y={y}? y/n") == "y":
        laser_off()
        move(x, y)

    for angle in range(10, 55, 5):
        print("\n#######################")
        print(f"New Angle {angle}°\n")
        lower = 1
        upper = 255
        while lower < upper:
            mid = math.floor((lower + upper) / 2)
            print(f"Cutting with laser power {mid} (0-255)")
            laser_on(mid)
            cut_v_groove(x, y, angle, 10, 3)
            laser_off()
            x += 10
            if input("Did it cut through? y/n: ").strip() == "y":
                upper = mid
            else:
                lower = mid + 1

    input("Start? Any key!")
