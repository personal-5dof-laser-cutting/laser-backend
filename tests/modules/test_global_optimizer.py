import pytest
from Geometry3D import Point
from core.modules.global_optimizer.global_optimizer import GlobalOptimizerModule
from core.models.geometry import Geometry, TrapezoidalCut
from core.service_container import Container
from core.services.laser_config_service import (
    LaserConfigService,
    LaserConfigServiceImpl,
)

SQUARE_PARAMS = [
    TrapezoidalCut(Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)),
    TrapezoidalCut(Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)),
    TrapezoidalCut(Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -5), Point(2, 1, -5)),
    TrapezoidalCut(Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -5), Point(1, 1, -5)),
]


@pytest.mark.parametrize("cuts, tour", [(SQUARE_PARAMS, [0, 2, 4, 6])])
def test_tour_to_path(cuts: list[TrapezoidalCut], tour: list[int]):
    optimizer = GlobalOptimizerModule()
    trapezoid_path = optimizer._tour_to_path(tour, cuts, Container.laser_config)
    for i in range(len(cuts)):
        # tour_to_path tries to eliminate the most costly travel move. Since they're all 0 it eliminates the first travel move by left-shifting the array
        assert trapezoid_path[i] == cuts[(i + 1) % len(cuts)]


@pytest.mark.parametrize("cuts", [SQUARE_PARAMS])
def test_global_optimizer(cuts: list[TrapezoidalCut]):
    geo_rep = Geometry()
    geo_rep.cuts = cuts

    optimizer = GlobalOptimizerModule()
    original_costs = _calculate_path_cost(geo_rep.cuts)
    optimized_geo = optimizer.process(geo_rep)

    optimized_costs = _calculate_path_cost(optimized_geo.cuts)
    assert original_costs > optimized_costs or original_costs == pytest.approx(
        optimized_costs
    )
    print(f"Original cost was {original_costs}")
    print(f"Optimized cost is {optimized_costs}")


def _calculate_path_cost(
    path: list[TrapezoidalCut],
    cost_function: LaserConfigService = Container.laser_config,
):
    total_cost = 0
    cost_function = LaserConfigServiceImpl()
    for i in range(len(path) - 1):
        total_cost += cost_function.get_cost(
            path[i].end_configuration(), path[i + 1].start_configuration()
        )
    return total_cost
