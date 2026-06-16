import multiprocessing as mp
import sys
import time
from tkinter import filedialog
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button

from core.models.geometry import Geometry, TrapezoidalCut
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.base_optimizer import BaseOptimizer
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def run_process(
    optimizer: BaseOptimizer,
    cuts: list[TrapezoidalCut],
    material_height: float,
    idx: int,
    current_costs,
    done_flags,
    result_queue: mp.Queue,
):
    geometry = Geometry()
    geometry.add_cuts(cuts)

    import threading

    stop_polling = threading.Event()

    def poll():
        time.sleep(1)
        while not stop_polling.is_set():
            current_costs[idx] = optimizer.get_current_cost(True)
            time.sleep(0.05)

    poll_thread = threading.Thread(target=poll, daemon=True)
    poll_thread.start()

    result_geometry = optimizer.process(geometry)

    stop_polling.set()
    poll_thread.join()

    final_cost = result_geometry.calculate_travel_cost(material_height, False)
    current_costs[idx] = final_cost
    done_flags[idx] = True
    result_queue.put((idx, result_geometry, final_cost))


def race_plot(
    svg_name: str,
    optimizers: list[BaseOptimizer],
    geometry: Geometry,
    material_height: float,
    interval: float = 1.0,
):
    n = len(optimizers)
    initial_cost = geometry.calculate_travel_cost(material_height, True)

    manager = mp.Manager()
    current_costs = manager.list([initial_cost] * n)
    done_flags = manager.list([False] * n)
    result_queue: mp.Queue = mp.Queue()

    optimized_results: list[Geometry | None] = [None] * n
    final_costs = [-1.0] * n
    timestamps = []
    costs = [[] for _ in range(n)]
    finish_idx = [-1] * n

    processes: list[mp.Process] = []

    fig, ax = plt.subplots()
    lines_solid = [
        ax.plot([], [], label=f"{type(optimizers[i]).__name__}")[0] for i in range(n)
    ]
    lines_dashed = [
        ax.plot([], [], linestyle="--", color=lines_solid[i].get_color())[0]
        for i in range(n)
    ]

    ax.set_title(f"Travel time over computation time for {svg_name}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Travel time (s)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, initial_cost * 1.2)
    ax.set_autoscalex_on(True)
    # ax.set_autoscaley_on(True)
    ax.legend()

    button_ax = fig.add_axes(rect=(0.45, 0.02, 0.1, 0.06))
    play_button = Button(button_ax, "Play", color="lightgreen", hovercolor="green")

    state = {"started": False, "start_time": None, "ani": None}

    def on_play(event):
        if state["started"]:
            return
        state["started"] = True
        state["start_time"] = time.time()

        for i, optimizer in enumerate(optimizers):
            p = mp.Process(
                target=run_process,
                args=(
                    optimizer,
                    geometry.cuts,
                    material_height,
                    i,
                    current_costs,
                    done_flags,
                    result_queue,
                ),
                daemon=True,
            )
            processes.append(p)
            p.start()

        play_button.label.set_text("Running...")
        play_button.color = "lightgray"
        play_button.hovercolor = "lightgray"

        state["ani"] = animation.FuncAnimation(
            fig, update, interval=interval * 1000, cache_frame_data=False
        )
        fig.canvas.draw_idle()

    play_button.on_clicked(on_play)

    def update(frame):
        if not state["started"]:
            return lines_solid + lines_dashed

        timestamps.append(time.time() - state["start_time"])

        while not result_queue.empty():
            idx, result_geometry, final_cost = result_queue.get()
            optimized_results[idx] = result_geometry
            final_costs[idx] = final_cost

        for i in range(n):
            if not done_flags[i]:
                c = current_costs[i]
            else:
                c = final_costs[i] if final_costs[i] != -1.0 else current_costs[i]
            costs[i].append(c)

            if not done_flags[i] or finish_idx[i] == -1:
                finish_idx[i] = len(timestamps)
                lines_solid[i].set_data(timestamps, costs[i])
                lines_dashed[i].set_data([], [])
            else:
                f = finish_idx[i]
                lines_solid[i].set_data(timestamps[: f + 1], costs[i][: f + 1])
                lines_dashed[i].set_data(timestamps[f:], costs[i][f:])

        ax.relim()
        ax.autoscale_view()

        if all(done_flags):
            play_button.label.set_text("Done")
            play_button.color = "lightcoral"
            play_button.hovercolor = "lightcoral"
            fig.canvas.draw_idle()
            state["ani"].event_source.stop()

        return lines_solid + lines_dashed

    plt.show()
    return state


if __name__ == "__main__":
    svg_file = filedialog.askopenfile(
        filetypes=[("SVG4DOF", "*.svg*")], initialdir="tests/modules/svgs"
    )
    if svg_file is None:
        print("Invalid file")
        sys.exit(1)
    print(f"Selected {svg_file.name}")
    svg_string: str = svg_file.read()
    dpi: float = float(input("DPI: ") or "72")
    material_height: float = float(input("Material height: "))
    nest_svg: bool = input("Nest SVG [y/N]: ").lower() == "y"
    importer = SVG5DOF_Importer(material_height, dpi)
    geometry: Geometry = importer.process(svg_string)
    if nest_svg:
        nester = AutoNester(200, 200)
        geometry = nester.process(geometry)

    optimizer_classes = {i: cls for i, cls in enumerate(BaseOptimizer.__subclasses__())}
    print("Available optimizers:")
    for i, cls in optimizer_classes.items():
        print(f"{i + 1:4}: {cls.__name__}")
    chosen = input("Select optimizers (seperated by spaces, e.g. '1 2 3'): ").split()
    optimizers = [optimizer_classes[int(i) - 1](material_height) for i in chosen]

    race_plot(
        svg_file.name,
        optimizers,
        geometry,
        material_height,
        interval=1.0,
    )
