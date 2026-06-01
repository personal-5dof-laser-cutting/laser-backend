import pstats
import sys
import cProfile
import Geometry3D

from core.models.geometry import Geometry
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.debug_visualizer.debug_visualizer import DebugVisualizerModule
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def run_optimizer(
    svg_path: str, material_height: float, show_debug_view: bool, show_live_stats: bool
):
    svg_string = open(svg_path).read()
    Geometry3D.set_sig_figures(4)

    dof = SVG5DOF_Importer(material_height, 72)
    geometry: Geometry = dof.process(svg_string)
    an = AutoNester(200, 200)
    dbg = DebugVisualizerModule(material_height)
    opt = GreedyOptimizerModule(material_height, show_statistics=show_live_stats)

    geometry = an.process(geometry)
    if show_debug_view:
        dbg.process(geometry)

    previous_costs = geometry.calculate_travel_cost(material_height, False)
    print(f"Starting cost: {previous_costs}")

    optimized = opt.process(geometry)
    if show_debug_view:
        dbg.process(optimized)

    optimized_costs = optimized.calculate_travel_cost(material_height, False)
    print(f"Final cost: {optimized_costs}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: svg_path material_height show_debug_view show_live_stats")
        sys.exit(1)
    svg_path: str = sys.argv[1]
    material_height: float = float(sys.argv[2])
    show_debug_view: bool = sys.argv[3] == "1"
    show_live_stats: bool = sys.argv[4] == "1"
    with cProfile.Profile() as pr:
        run_optimizer(svg_path, material_height, show_debug_view, show_live_stats)
        stats = pstats.Stats(pr).sort_stats("cumulative")
        stats.print_stats(15)
