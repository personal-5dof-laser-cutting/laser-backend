from collections import OrderedDict
from math import ceil
import sys
import time

import Geometry3D
from matplotlib import animation, pyplot as plt

from core.models.geometry import Geometry
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.base_optimizer import BaseOptimizer
from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule
from core.modules.genetic_optimizer.genetic_optimizer import GeneticOptimizerModule
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.modules.rpp_approximation.rpp_approximation import RPPApproximationModule
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def build_timeline(
    geo: Geometry, material_thickness: float, feedrate: float, offset_seconds: float = 0
):
    cuts = geo.cuts
    n = len(cuts)
    t = offset_seconds
    waypoints = [(t, 0.0)]
    cuts_cost = geo.calculate_cut_cost(material_thickness, feedrate) * 60
    accum_cuts_cost = 0.0

    for i, cut in enumerate(cuts):
        cut_cost = (
            cut.get_internal_cost(
                feedrate=feedrate, material_thickness=material_thickness
            )
            * 60
        )
        accum_cuts_cost += cut_cost
        pct_after = accum_cuts_cost / cuts_cost * 100
        t += cut_cost
        waypoints.append((t, pct_after))
        if i < n - 1:
            t += (
                cuts[i].travel_time_to(
                    cuts[i + 1], material_thickness=material_thickness
                )
                * 60
            )
            waypoints.append((t, pct_after))

    return waypoints


def interpolate_progress(waypoints: list[tuple[float, float]], t_now: float):
    if t_now <= waypoints[0][0]:
        return waypoints[0][1]
    if t_now >= waypoints[-1][0]:
        return -waypoints[-1][1]

    for i in range(len(waypoints)):
        t0, p0 = waypoints[i - 1]
        t1, p1 = waypoints[i]
        if t0 <= t_now <= t1:
            if t1 == t0:
                return p1
            frac = (t_now - t0) / (t1 - t0)
            return p0 + frac * (p1 - p0)
    return waypoints[-1][1]


# Distinct colors for each series; extend if you ever need more than 8
_COLORS = ["royalblue", "green", "orange", "red", "purple", "brown", "pink", "gray"]

START_TIME = None


def simulate_cut(
    optimizers: list[BaseOptimizer],
    optimizer_names: list[str],
    svg_path: str,
    material_thickness: float,
    feedrate: float,
    save_animation: bool,
    speed: float,
):
    global START_TIME
    START_TIME = None
    HOMING_DURATION = 0

    svg_string = open(svg_path).read()
    Geometry3D.set_sig_figures(4)

    dof = SVG5DOF_Importer(material_thickness, 72)
    geometry: Geometry = dof.process(svg_string)
    an = AutoNester(200, 200)
    geometry = an.process(geometry)

    # --- build one timeline per optimizer (plus the unoptimized baseline) ---
    timelines: list[tuple[str, list[tuple[float, float]]]] = []
    original_timeline = build_timeline(
        geometry, material_thickness, feedrate, offset_seconds=HOMING_DURATION
    )
    timelines.append(("Unoptimiert", original_timeline))

    for optimizer, name in zip(optimizers, optimizer_names):
        t0 = time.time()
        print(f"Optimizing using {optimizer.__class__.__name__}")
        optimized_geo = optimizer.process(geometry)
        duration = time.time() - t0
        print(f"Took {duration} seconds")
        tl = build_timeline(
            optimized_geo,
            material_thickness,
            feedrate,
            offset_seconds=max(duration, HOMING_DURATION),
        )
        timelines.append((name, tl))

    total_time = max(tl[-1][0] for _, tl in timelines)

    # --- set up plot ---
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, total_time * 1.05)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Rechenzeit + Schnittzeit (Minuten)", fontsize=20)
    ax.set_ylabel("Fortschritt (%)", fontsize=20)
    # ax.set_title("Real-time Cutting Progress")
    ax.axhline(100, color="black", linestyle="--", linewidth=0.5, alpha=0.4)
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.tick_params(labelsize=13)
    time_text = ax.text(
        1.00, 0.95, "", transform=ax.transAxes, fontsize=20, color="gray"
    )

    # One line + marker per series
    series = []
    for idx, (name, tl) in enumerate(timelines):
        color = _COLORS[idx % len(_COLORS)]
        (line,) = ax.plot([], [], lw=2, color=color, label=name)
        (marker,) = ax.plot([], [], "o", color=color, markersize=8, zorder=5)
        series.append(
            {
                "timeline": tl,
                "line": line,
                "marker": marker,
                "xs": [],
                "ys": [],
                "done": False,
            }
        )

    # ax.legend(loc="lower right")

    artists = [item for s in series for item in (s["line"], s["marker"])] + [time_text]
    for idx, s in enumerate(series):
        s["text"] = ax.text(
            1.05,
            0.22 - idx * 0.05,
            "",
            transform=ax.transAxes,
            fontsize=20,
            color=_COLORS[idx % len(_COLORS)],
        )

    def init():
        for s in series:
            s["line"].set_data([], [])
            s["marker"].set_data([], [])
            s["xs"].clear()
            s["ys"].clear()
            s["done"] = False
        time_text.set_text("")
        return artists

    FPS = 20
    FRAME_COUNT = ceil((total_time + 1) / speed * FPS)

    def update(frame):
        global START_TIME
        if START_TIME is None:
            START_TIME = time.time()

        t_now = frame / FPS * speed

        for s in series:
            pct = interpolate_progress(s["timeline"], t_now)
            if pct < 0:
                if s["done"]:
                    continue
                else:
                    s["done"] = True
                    pct = -pct
            s["text"].set_text(f"{s['line'].get_label()}: {pct:.1f}%")
            s["xs"].append(t_now)
            s["ys"].append(pct)
            s["line"].set_data(s["xs"], s["ys"])
            s["marker"].set_data([t_now], [pct])

        return artists

    plt.tight_layout()
    fig.subplots_adjust(right=0.65)
    ani = animation.FuncAnimation(
        fig,
        update,
        frames=FRAME_COUNT,
        init_func=init,
        interval=1000 / FPS,
        blit=False,
        cache_frame_data=False,
        repeat=False,
    )
    if save_animation:
        print(1)
        ani.save("cutting_progress.mp4", writer="ffmpeg", fps=20)
    else:
        print(2)
        plt.show()


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(
            "Usage: python script.py svg_path material_height feedrate save_animation speed"
        )
        sys.exit(1)

    svg_path: str = sys.argv[1]
    material_thickness: float = float(sys.argv[2])
    feedrate: float = float(sys.argv[3])
    save_animation: bool = sys.argv[4] == "1"
    speed: float = float(sys.argv[5])

    optimizers: OrderedDict[str, BaseOptimizer] = OrderedDict(
        {
            "Naive Lösung": BucketOptimizerModule(material_thickness),
            "Greedy": GreedyOptimizerModule(material_thickness),
            "Genetischer Algorithmus": GeneticOptimizerModule(material_thickness),
            "Christofides Algorithmus": RPPApproximationModule(material_thickness),
        }
    )

    print("Available optimizers:")
    for i, optimizer in enumerate(optimizers.keys()):
        print(f"  {i + 1}: {optimizer}")
    print("Enter one or more numbers separated by spaces (e.g. 1 3):")

    raw = input("Select optimizers: ").split()
    chosen_indices = [int(x) - 1 for x in raw]

    if not chosen_indices:
        chosen_indices = list(range(len(optimizers)))
    elif any(i < 0 or i >= len(optimizers) for i in chosen_indices):
        print("Invalid selection.")
        sys.exit(1)
    chosen_optimizers = [list(optimizers.values())[i] for i in chosen_indices]
    chosen_names = [list(optimizers.keys())[i] for i in chosen_indices]

    simulate_cut(
        chosen_optimizers,
        chosen_names,
        svg_path,
        material_thickness,
        feedrate,
        save_animation,
        speed,
    )
