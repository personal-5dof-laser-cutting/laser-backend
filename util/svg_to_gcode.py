from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer
from core.modules.gcode_exporter.gcode_export import GCodeExporter
import sys

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: material_thickness scaling cut_speed svg_file output_file")
        sys.exit(1)
    material_thickness: float = float(sys.argv[1])
    scaling: str = sys.argv[2]
    cut_speed: float = float(sys.argv[3])
    svg_path: str = sys.argv[4]
    gcode_output: str = sys.argv[5]

    if scaling not in ["mm", "illsturator"]:
        raise Exception("Invalid scaling")
    importer = SVG5DOF_Importer(material_thickness=material_thickness, scaling=scaling)  # type: ignore
    geo = importer.process(open(svg_path, "r").read())
    exporter = GCodeExporter(
        material_thickness,
        gcode_comments=False,
        pretty_formatting=False,
        cut_speed=cut_speed,
        laser_off=False,
    )
    gcode = exporter.process(geo)
    with open(gcode_output, "w") as f:
        f.write(gcode)
