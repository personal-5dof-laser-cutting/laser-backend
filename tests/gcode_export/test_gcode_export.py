from core.modules.gcode_exporter.gcode_export import GCodeExporter
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def test_gcode_export():
    exporter = GCodeExporter()
    importer = SVG5DOF_Importer()
    geo = importer.process((open("tests/svg5dof/svgs/circle_3.svg").read(), 5.0))
    gcode = exporter.process((geo, 5.0))
    with open("output.gcode", "w+") as f:
        f.write(gcode)
