from api.models.base import FrontendInput
from core.modules.gcode_exporter.gcode_export import GCodeExporter
from core.modules.global_optimizer.global_optimizer import GlobalOptimizerModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer
from core.pipeline.base import Module, Pipeline


def full_pipeline(frontendInput: FrontendInput, generations: int = 1000) -> Pipeline:
    modules: list[Module] = [
        SVG5DOF_Importer(
            frontendInput.material_thickness,
            scaling=frontendInput.scaling,
            x_offset=frontendInput.x_offset,
            y_offset=frontendInput.y_offset,
        )
    ]
    if frontendInput.optimize:
        modules.append(GlobalOptimizerModule(generations=generations))
    modules.extend(
        [
            GCodeExporter(
                frontendInput.material_thickness,
                laser_off=frontendInput.laser_off,
                cut_speed=frontendInput.cut_speed,
                pretty_formatting=False,
            )
        ]
    )
    return Pipeline(modules)


def gcode_pipeline(
    material_thickness: float,
    optimize: bool,
    laser_off: bool = False,
    cut_speed_mm_per_s: float = 20,
) -> Pipeline:
    modules = [
        SVG5DOF_Importer(material_thickness),
        GCodeExporter(
            material_thickness, laser_off=laser_off, cut_speed=cut_speed_mm_per_s
        ),
    ]
    if optimize:
        print("Optimizing")
    return Pipeline(modules)
