import sys
import time

import Geometry3D
from matplotlib import animation, pyplot as plt

from core.models.geometry import Geometry, TrapezoidalCut
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.base_optimizer import BaseOptimizer
from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule
from core.modules.genetic_optimizer.genetic_optimizer import GeneticOptimizerModule
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.modules.rpp_approximation.rpp_approximation import RPPApproximationModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def build_timeline(
    cuts: list[TrapezoidalCut],
    material_height: float,
    feedrate: float,
    offset_seconds: float = 0,
):
    n = len(cuts)
    print(n)
    t = offset_seconds
    waypoints = [(t, 0.0)]

    for i, cut in enumerate(cuts):
        pct_after = (i + 1) / n * 100
        t += cut.get_internal_cost(feedrate=feedrate, material_height=material_height)
        waypoints.append((t, pct_after))
        if i < n - 1:
            t += (
                cuts[i].travel_time_to(cuts[i + 1], material_height=material_height)
                + 0.1
            )
            waypoints.append((t, pct_after))

    return waypoints


def interpolate_progress(waypoints: list[tuple[float, float]], t_now: float):
    if t_now <= waypoints[0][0]:
        return waypoints[0][1]
    if t_now >= waypoints[-1][0]:
        return waypoints[-1][1]

    for i in range(len(waypoints)):
        t0, p0 = waypoints[i - 1]
        t1, p1 = waypoints[i]
        if t0 <= t_now <= t1:
            if t1 == t0:
                return p1
            frac = (t_now - t0) / (t1 - t0)
            return p0 + frac * (p1 - p0)
    return waypoints[-1][1]


START_TIME = None
xs, org_ys, opt_ys = [], [], []


def simulate_cuttime(
    optimizer: BaseOptimizer, svg_path: str, material_height: float, feedrate: float
):
    svg_string = open(svg_path).read()
    Geometry3D.set_sig_figures(4)

    dof = SVG5DOF_Importer(material_height, 72)
    geometry: Geometry = dof.process(svg_string)
    an = AutoNester(200, 200)
    geometry = an.process(geometry)

    original_timeline = build_timeline(geometry.cuts, material_height, feedrate)
    optimizer_start = time.time()
    optimized_geo = optimizer.process(geometry)
    optimization_duration = time.time() - optimizer_start
    optimized_timeline = build_timeline(
        optimized_geo.cuts,
        material_height,
        feedrate,
        offset_seconds=optimization_duration,
    )
    total_time = max(original_timeline[-1][0], optimized_timeline[-1][0])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, total_time * 1.05)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Progress (%)")
    ax.set_title("Real-time Cutting Progress")
    ax.axhline(
        100, color="green", linestyle="--", linewidth=0.5, alpha=0.5, label="100%"
    )
    ax.grid(True, linestyle=":", alpha=0.4)

    (original_line,) = ax.plot([], [], lw=2, color="royalblue", label="Unoptimized")
    (original_marker,) = ax.plot([], [], "o", color="tomato", markersize=8, zorder=5)
    time_text = ax.text(
        0.02, 0.92, "", transform=ax.transAxes, fontsize=10, color="gray"
    )
    (optimized_line,) = ax.plot([], [], lw=2, color="green", label="Optimized")
    (optimized_marker,) = ax.plot([], [], "o", color="yellow", markersize=8, zorder=5)

    def init():
        original_line.set_data([], [])
        original_marker.set_data([], [])
        optimized_line.set_data([], [])
        optimized_marker.set_data([], [])
        time_text.set_text("")
        return (
            original_line,
            original_marker,
            time_text,
            optimized_line,
            optimized_marker,
        )

    def update(_frame):
        global START_TIME, xs, org_ys, opt_ys

        if START_TIME is None:
            START_TIME = time.time()

        t_now = min(time.time() - START_TIME, total_time)
        org_pct = interpolate_progress(original_timeline, t_now)
        opt_pct = interpolate_progress(optimized_timeline, t_now)
        xs.append(t_now)
        org_ys.append(org_pct)
        original_line.set_data(xs, org_ys)
        original_marker.set_data([t_now], [org_pct])
        opt_ys.append(opt_pct)
        optimized_line.set_data(xs, opt_ys)
        optimized_marker.set_data([t_now], [opt_pct])

        time_text.set_text(
            f"t = {t_now:.2f} s | Unoptimized: {org_pct:.1f}%, Optimized: {opt_pct:.1}%"
        )

        return (
            original_line,
            original_marker,
            time_text,
            optimized_line,
            optimized_marker,
        )

    _ = animation.FuncAnimation(
        fig, update, init_func=init, interval=50, blit=True, cache_frame_data=False
    )
    plt.tight_layout()
    ax.legend(loc="upper left")
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Usage: svg_path material_height feedrate show_debug_view show_live_stats"
        )
        sys.exit(1)
    svg_path: str = sys.argv[1]
    material_height: float = float(sys.argv[2])
    feedrate: float = float(sys.argv[3])
    optimizer_classes = [
        GreedyOptimizerModule,
        GeneticOptimizerModule,
        BucketOptimizerModule,
        RPPApproximationModule,
    ]
    print("Available optimizers:")
    for i, cls in enumerate(optimizer_classes):
        print(f"{i + 1:4}: {cls.__name__}")
    chosen = int(input("Select one optimizer: ")) - 1
    optimizer = optimizer_classes[chosen]

    simulate_cuttime(optimizer(material_height), svg_path, material_height, feedrate)
