from api.models.base import FrontendInput
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.gcode_exporter.gcode_export import GCodeExporter
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer
from core.pipeline.base import Module, Pipeline
from core.service_container import Container


def full_pipeline(frontendInput: FrontendInput) -> Pipeline:
    modules: list[Module] = [
        SVG5DOF_Importer(
            frontendInput.material_thickness,
            dpi=frontendInput.dpi,
            x_offset=frontendInput.x_offset,
            y_offset=frontendInput.y_offset,
            model_scale=frontendInput.model_scale,
        ),
    ]
    if frontendInput.optimize:
        modules.append(GreedyOptimizerModule(frontendInput.material_thickness))
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


def svg_to_geometry_pipeline(
    material_thickness: float,
    dpi: float,
    nest_geometry: bool,
    x_offset: float = 0,
    y_offset: float = 0,
    model_scale: float = 0,
):
    modules: list[Module] = []
    modules.append(
        SVG5DOF_Importer(
            material_thickness=material_thickness,
            dpi=dpi,
            x_offset=x_offset,
            y_offset=y_offset,
            model_scale=model_scale,
        )
    )
    if nest_geometry:
        center_x, center_y = Container.laser_config.table_center()
        modules.append(AutoNester(center_x, center_y))

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
