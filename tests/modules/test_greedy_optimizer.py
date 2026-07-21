import Geometry3D
import pytest
from core.models.geometry import Geometry
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


@pytest.mark.parametrize(
    "svg_string,material_thickness",
    [
        (
            open("tests/modules/svgs/my-guy-wip.svg").read(),
            6,
        ),
        (
            open("tests/modules/svgs/the-guy-new.svg").read(),
            6,
        ),
    ],
)
def test_optimizer(svg_string: str, material_thickness: float):
    # TODO: write a proper test
    Geometry3D.set_sig_figures(4)
    dof = SVG5DOF_Importer(material_thickness, 72)
    geometry: Geometry = dof.process(svg_string)
    an = AutoNester(200, 200)
    geometry = an.process(geometry)
    opt = GreedyOptimizerModule(material_thickness, show_statistics=False)
    previous_costs = geometry.calculate_travel_cost(material_thickness, False)
    optimized = opt.process(geometry)
    optimized_costs = optimized.calculate_travel_cost(material_thickness, False)
    assert not previous_costs < optimized_costs
