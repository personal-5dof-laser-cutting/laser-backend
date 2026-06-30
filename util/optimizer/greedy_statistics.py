import logging

import pstats
import sys
import cProfile
from time import time
import Geometry3D

from core.models.geometry import Geometry
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.debug_visualizer.debug_visualizer import DebugVisualizerModule
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer

logging.basicConfig(
    level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s", force=True
)

logger = logging.getLogger("stats" if __name__ == "__main__" else __name__)


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

    cuts_cost = geometry.calculate_cut_cost(material_height, 600)
    previous_costs = geometry.calculate_travel_cost(material_height, False)
    logger.info(
        f"Starting cost: {cuts_cost + previous_costs:.4}, travel moves: {previous_costs:.4} ({previous_costs / (cuts_cost + previous_costs):.2%})"
    )
    start_time = time()
    optimized = opt.process(geometry)
    end_time = time()
    logger.info(f"Optimized in {end_time - start_time} seconds")
    if show_debug_view:
        dbg.process(optimized)

    optimized_costs = optimized.calculate_travel_cost(material_height, False)
    logger.info(
        f"Optimized cost: {cuts_cost + optimized_costs:.4}, travel moves: {optimized_costs:.4} ({optimized_costs / (cuts_cost + optimized_costs):.2%})"
    )


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: svg_path material_height show_debug_view show_live_stats")
        sys.exit(1)
    svg_path: str = sys.argv[1]
    material_height: float = float(sys.argv[2])
    show_debug_view: bool = sys.argv[3] == "1"
    show_live_stats: bool = sys.argv[4] == "1"
    measure_performance: bool = sys.argv[5] == "1"
    if measure_performance:
        with cProfile.Profile() as pr:
            run_optimizer(svg_path, material_height, show_debug_view, show_live_stats)
            stats = pstats.Stats(pr).sort_stats("cumulative")
            stats.print_stats(".*_cache")
    else:
        run_optimizer(svg_path, material_height, show_debug_view, show_live_stats)
