from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer
from core.modules.gcode_exporter.gcode_export import GCodeExporter
from api.models.base import ScalingType
import sys
from Geometry3D import set_sig_figures

if __name__ == "__main__":
    set_sig_figures(4)
    if len(sys.argv) != 7:
        print(
            "Usage: material_thickness scaling cut_speed material_constant svg_file output_file"
        )
        sys.exit(1)
    material_thickness: float = float(sys.argv[1])
    scaling: str = sys.argv[2]
    cut_speed: float = float(sys.argv[3])
    material_constant: float = float(sys.argv[4])
    svg_path: str = sys.argv[5]
    gcode_output: str = sys.argv[6]

    if scaling not in ScalingType:
        raise Exception("Invalid scaling")
    importer = SVG5DOF_Importer(material_thickness=material_thickness, scaling=scaling)  # type: ignore
    geo = importer.process(open(svg_path, "r").read())

    # vis = GeometryVisualizerModule()
    # vis.process(geo)
    exporter = GCodeExporter(
        material_thickness,
        gcode_comments=False,
        pretty_formatting=False,
        cut_speed=cut_speed,
        laser_off=False,
        material_constant=material_constant,
    )
    gcode = exporter.process(geo)
    with open(gcode_output, "w") as f:
        f.write(gcode)
