import Geometry3D
from core.models.geometry import Geometry
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def test_optimizer():
    # TODO: write a proper test
    Geometry3D.set_sig_figures(4)
    svg = [
        "/home/leonarddf/Uni/IT-Systems_Engineering/HCI-BP/models-to-cut/archive/the-guy-for-real.svg",
        "/home/leonarddf/Uni/IT-Systems_Engineering/HCI-BP/models-to-cut/archive/the-guy-front.svg",
    ][1]
    dof = SVG5DOF_Importer(6, 72)
    geometry: Geometry = dof.process(open(svg).read())
    opt = GreedyOptimizerModule(6)
    previous_costs = geometry.calculate_travel_cost(6)
    optimized = opt.process(geometry)
    optimized_costs = optimized.calculate_travel_cost(6)
    assert previous_costs >= optimized_costs
