from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule
from core.modules.debug_visualizer.debug_visualizer import DebugVisualizerModule
from core.modules.local_optimizer.local_optimizer import LocalOptimizer
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer
from core.modules.gcode_exporter.gcode_export import GCodeExporter
import sys
from Geometry3D import set_sig_figures

if __name__ == "__main__":
    set_sig_figures(2)
    if len(sys.argv) != 10:
        print(
            "Usage: material_thickness dpi cut_speed material_constant prop_up local_optimizer global_optimizer svg_file output_file"
        )
        print(
            "DPI values:\n- 72 (adobe Illustrator)\n- 96 (Inkscape, others)\n\nmaterial_constant = -1 for max power"
        )
        sys.exit(1)

    material_thickness: float = float(sys.argv[1])
    dpi: float = float(sys.argv[2])
    cut_speed: float = float(sys.argv[3])
    material_constant: float = float(sys.argv[4])
    prop_up: float = float(sys.argv[5])
    local_optimizer_on = sys.argv[6].strip() == "1"
    global_optimizer_on = sys.argv[7].strip() == "1"
    svg_path: str = sys.argv[8]
    gcode_output: str = sys.argv[9]

    importer = SVG5DOF_Importer(
        material_thickness=material_thickness,
        dpi=dpi,
    )
    geo = importer.process(open(svg_path, "r").read())

    if local_optimizer_on:
        local_optimizer = LocalOptimizer()
        geo = local_optimizer.process(geo)

    nester = AutoNester(200, 200)
    geo = nester.process(geo)

    if global_optimizer_on:
        optimizer = BucketOptimizerModule()
        geo = optimizer.process(geo)

    vis = DebugVisualizerModule(material_thickness)
    result_geo = vis.process(geo)
    exporter = GCodeExporter(
        material_thickness,
        gcode_comments=False,
        pretty_formatting=False,
        cut_speed=cut_speed,
        laser_off=False,
        material_constant=material_constant,
        prop_up=prop_up,
        force_max_laser_power=material_constant == -1,
    )

    gcode = exporter.process(result_geo)
    with open(gcode_output, "w") as f:
        f.write(gcode)
