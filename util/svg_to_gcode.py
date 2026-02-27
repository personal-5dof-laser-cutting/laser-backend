from typing import cast, get_args

from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule
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

    optimizer = BucketOptimizerModule()
    optimized_geo = optimizer.process(geo)
    # vis = GeometryVisualizerModule()
    # vis.process(geo)
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
