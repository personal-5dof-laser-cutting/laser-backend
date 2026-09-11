import time

from api.models.base import WebsocketMessage
from core.corgi_interface import CorgiInterface
import sys

from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.gcode_exporter.gcode_export import GCodeExporter
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


if __name__ == "__main__":
    svg_file = open(sys.argv[1], "r").read()

    material_thickness: float = float(sys.argv[2])
    dpi: float = float(sys.argv[3])
    feedrate: float = float(sys.argv[4])
    cutspeed = feedrate / 60

    importer = SVG5DOF_Importer(material_thickness, dpi)
    generator = GCodeExporter(
        material_thickness, cut_speed=cutspeed, gcode_comments=False
    )
    an = AutoNester(200, 200)

    geo = importer.process(svg_file)
    geo = an.process(geo)
    print(f"Cut cost: {geo.calculate_cut_cost(material_thickness, feedrate) * 60:.3f}s")
    print(
        f"Travel cost: {geo.calculate_travel_cost(material_thickness, False) * 60:.3f}s"
    )

    gcode = generator.process(geo)
    # print(gcode)
    interface = CorgiInterface()

    print("Sending GCode")
    print("\n".join(gcode.split("\n")[:7] + gcode.split("\n")[-2:]))
    interface._prime_commands(gcode.split("\n")[:7] + gcode.split("\n")[-2:])
    timestamps: list[int] = []
    total_active = 0.0
    total_inactive = 0.0
    while True:
        msg: WebsocketMessage = interface.outgoing_messages.get()
        print(msg)
        now = time.time_ns()
        if msg.type != "debug":
            continue
        if msg.content == "done":
            print("Done!")
            break
        print(f"{msg.content=}")
        status, timestamp = msg.content.split(" ")
        is_active = bool(status)
        timestamps.append(int(timestamp))
        # print("Is active: {status}")
        if len(timestamps) > 1:
            if is_active:
                total_inactive += timestamps[-1] - timestamps[-2]
            else:
                total_active += timestamps[-1] - timestamps[-2]
            print(
                f"{'in' * (not is_active)}active for {(timestamps[-1] - timestamps[-2]) / 1000:.3f} s"
            )
            # print(f"Duration: {timestamps[-1] - timestamps[-2]} ms")
        # print(msg.content)

    print(f"Actual laser cost: {total_active / 1000:.3f}s")
    print(f"Actual travel cost: {total_inactive / 1000:.3f}s")
    corgi_interface = CorgiInterface()
    corgi_interface.connect()

    print("Done")
