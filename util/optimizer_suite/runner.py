from copy import deepcopy
import random
import time
from typing import Any, Callable, NotRequired, Optional, Tuple, TypedDict

from Geometry3D import set_sig_figures
from pydantic import BaseModel

from core.models.geometry import Configuration, Geometry
from core.modules.base_optimizer import BaseOptimizer

import pandas as pd

from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.pipeline.base import Pipeline
from core.pipeline.pipeline import svg_to_geometry_pipeline


class ProblemSettings(BaseModel):
    material_height: float
    dpi: float
    nest_geometry: bool
    x_offset: float
    y_offset: float
    model_scale: float
    feedrate: float


class OptimizerStats(TypedDict, total=True):
    svg_path: str
    optimizer: str
    run_index: int
    travel_cost: float
    wall_clock_time_s: NotRequired[float]
    process_time_s: NotRequired[float]


def _load_svg(path: str) -> str:
    """Load an SVG file and validate that it is actually an SVG"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content: str = f.read()

        if "<svg" not in content.lower():
            raise ValueError(f"File does not appear to be a valid SVG: {path}")

        return content
    except FileNotFoundError:
        raise FileNotFoundError(f"SVG file not found: {path}")


def _original_stats(
    svg_path: str, geometry: Geometry, material_height: float
) -> OptimizerStats:
    return OptimizerStats(
        svg_path=svg_path,
        optimizer="Original",
        run_index=0,
        travel_cost=geometry.calculate_travel_cost(material_height, False),
    )


def _shuffled_stats(
    on_progress: Callable[[str, str, int], None],
    svg_path: str,
    geometry: Geometry,
    material_height: float,
    iterations: int,
) -> list[OptimizerStats]:
    stats: list[OptimizerStats] = []
    name = "Randomized"
    for i in range(iterations):
        work_geo = deepcopy(geometry)
        random.shuffle(work_geo.cuts)
        count = random.randint(1, len(work_geo.cuts))
        for cut in random.sample(work_geo.cuts, k=count):
            cut.flip_direction()

        stats.append(
            OptimizerStats(
                svg_path=svg_path,
                optimizer=name,
                run_index=i,
                travel_cost=work_geo.calculate_travel_cost(material_height, False),
            )
        )
        on_progress(svg_path, name, i)
    return stats


def _run_optimizer(
    on_progress: Callable[[str, str, int], None],
    optimizer: BaseOptimizer,
    geometry: Geometry,
    material_height: float,
    svg_path: str,
    iterations: int,
) -> list[OptimizerStats]:
    stats: list[OptimizerStats] = []
    name = type(optimizer).__name__
    for i in range(iterations):
        geo_copy = deepcopy(geometry)
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        optimized_geo = optimizer.process(geo_copy)
        wall_end = time.perf_counter()
        cpu_end = time.process_time()

        stats.append(
            OptimizerStats(
                svg_path=svg_path,
                optimizer=name,
                run_index=i,
                travel_cost=optimized_geo.calculate_travel_cost(material_height, False),
                wall_clock_time_s=wall_end - wall_start,
                process_time_s=cpu_end - cpu_start,
            )
        )

        on_progress(svg_path, name, i)

    return stats


def run_suite(
    on_progress: Callable[[str, str, int], None],
    problems: list[Tuple[ProblemSettings, str]],
    optimizers: list[Tuple[type[BaseOptimizer], dict[str, Any]]],
    sample_size: int,
    start_location: Optional[Configuration] = None,
) -> Tuple[pd.DataFrame, list[float]]:
    set_sig_figures(4)

    rows: list[OptimizerStats] = []
    total_costs: list[float] = []
    for settings, svg_path in problems:
        material_height = settings.material_height
        pipeline: Pipeline = svg_to_geometry_pipeline(
            material_thickness=settings.material_height,
            dpi=settings.dpi,
            nest_geometry=settings.nest_geometry,
            x_offset=settings.x_offset,
            y_offset=settings.y_offset,
            model_scale=settings.model_scale,
        )
        content: str = _load_svg(svg_path)
        geometry: Geometry = pipeline.run(content)
        total_costs.append(
            geometry.calculate_total_cost(
                settings.material_height, settings.feedrate, False
            )
        )

        rows.append(_original_stats(svg_path, geometry, material_height))
        on_progress(svg_path, "Original", 0)

        rows.extend(
            _shuffled_stats(
                on_progress, svg_path, geometry, material_height, sample_size
            )
        )
        for optimizer, settings in optimizers:
            # settings.pop("start_location", None)
            rows.extend(
                _run_optimizer(
                    on_progress,
                    optimizer(
                        material_height=material_height,
                        start_location=start_location,
                        **settings,
                    ),
                    geometry,
                    material_height,
                    svg_path,
                    sample_size,
                )
            )

    return (pd.DataFrame(rows), total_costs)


if __name__ == "__main__":

    def progress(svg_path, name, index):
        print(f"Path: {svg_path}, optimizer {name}, iteration {index + 1}")

    setting = ProblemSettings(
        material_height=6,
        dpi=72,
        nest_geometry=True,
        x_offset=0,
        y_offset=0,
        model_scale=1,
        feedrate=600,
    )
    problems = [
        (
            setting,
            "/home/leonarddf/Uni/IT-Systems_Engineering/HCI-BP/demo-models/low poly bust/the-guy-stirn.svg",
        ),
        (
            setting,
            "/home/leonarddf/Uni/IT-Systems_Engineering/HCI-BP/demo-models/low poly bust/the-guy-neck.svg",
        ),
    ]
    optimizers = [
        (GreedyOptimizerModule, {"max_iterations": 10, "show_statistics": False}),
        (BucketOptimizerModule, {"epsilon": 0.01}),
    ]
    sample_size = 3

    print(run_suite(progress, problems, optimizers, sample_size))
