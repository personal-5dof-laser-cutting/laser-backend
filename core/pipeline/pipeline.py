from fastapi import WebSocket
from core.modules.gcode_exporter.gcode_export import GCodeExporter
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer
from core.pipeline.base import Pipeline


def full_pipline_unoptimized(
    websocket: WebSocket,
    material_thickness: float,
    laser_off: bool = True,
    cut_speed_mm_per_s: float = 20,
) -> Pipeline:
    return Pipeline(
        [
            SVG5DOF_Importer(material_thickness),
            GCodeExporter(
                material_thickness, laser_off=laser_off, cut_speed=cut_speed_mm_per_s
            ),
            # GCodeSender(websocket),
        ]
    )


def gcode_pipeline(
    material_thickness: float,
    optimize: bool,
    laser_off: bool = False,
    cut_speed_mm_per_s: float = 20,
) -> Pipeline:
    modules = [
        SVG5DOF_Importer(material_thickness),
        GCodeExporter(
            material_thickness, dry_run=laser_off, cut_speed=cut_speed_mm_per_s
        ),
    ]
    if optimize:
        print("Optimizing")
    return Pipeline(modules)
