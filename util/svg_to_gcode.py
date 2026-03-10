import math
from typing import cast, get_args

from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule
from core.modules.debug_visualizer.debug_visualizer import DebugVisualizerModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer
from core.modules.gcode_exporter.gcode_export import GCodeExporter
from api.models.base import ScalingType
import sys
from Geometry3D import set_sig_figures

if __name__ == "__main__":
    set_sig_figures(4)
    if len(sys.argv) not in [8, 10]:
        print(
            "Usage: material_thickness scaling cut_speed material_constant prop_up svg_file output_file [x_offset y_offset]"
        )
        sys.exit(1)
    if sys.argv[2] not in get_args(ScalingType):
        raise Exception("Invalid scaling")

    material_thickness: float = float(sys.argv[1])
    scaling: ScalingType = cast(ScalingType, sys.argv[2])
    cut_speed: float = float(sys.argv[3])
    material_constant: float = float(sys.argv[4])
    prop_up: float = float(sys.argv[5])
    svg_path: str = sys.argv[6]
    gcode_output: str = sys.argv[7]
    x_offset: int = int(sys.argv[8]) if len(sys.argv) == 10 else 0
    y_offset: int = int(sys.argv[9]) if len(sys.argv) == 10 else 0

    importer = SVG5DOF_Importer(
        material_thickness=material_thickness,
        scaling=scaling,
        x_offset=x_offset,
        y_offset=y_offset,
    )
    geo = importer.process(open(svg_path, "r").read())

    max_angle: float = max([c.effective_angle_abs for c in geo.cuts])
    print(f"Max angle: {math.degrees(max_angle)}")

    min_x: float = 1000
    max_x: float = -1000
    min_y: float = 1000
    max_y: float = -1000

    for c in geo.cuts:
        min_x = min(c.start_bottom.x, c.start_top.x, c.end_bottom.x, c.end_top.x)
        max_x = max(c.start_bottom.x, c.start_top.x, c.end_bottom.x, c.end_top.x)
        min_y = min(c.start_bottom.y, c.start_top.y, c.end_bottom.y, c.end_top.y)
        max_y = max(c.start_bottom.y, c.start_top.y, c.end_bottom.y, c.end_top.y)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    print(f"Center: {center_x} {center_y}")

    optimizer = BucketOptimizerModule()
    optimized_geo = optimizer.process(geo)
    vis = DebugVisualizerModule(material_thickness)
    geo = vis.process(geo)
    exporter = GCodeExporter(
        material_thickness,
        gcode_comments=False,
        pretty_formatting=False,
        cut_speed=cut_speed,
        laser_off=False,
        material_constant=material_constant,
        prop_up=prop_up,
    )
    gcode = exporter.process(optimized_geo)
    with open(gcode_output, "w") as f:
        f.write(gcode)
