import pytest
from Geometry3D import Point
from core.modules.global_optimizer.global_optimizer import GlobalOptimizerModule
from core.modules.global_optimizer.genetic_gtsp import GTSP, run_gcga
from core.models.geometry import Geometry, TrapezoidalCut
from core.service_container import Container
from core.services.cost_function_service import (
    CostFunctionService,
    CostFunctionServiceImpl,
)

SQUARE_PARAMS = [
    TrapezoidalCut(Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)),
    TrapezoidalCut(Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)),
    TrapezoidalCut(Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -5), Point(2, 1, -5)),
    TrapezoidalCut(Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -5), Point(1, 1, -5)),
]


@pytest.mark.parametrize("cuts", [SQUARE_PARAMS[:-1]])
def test_tour_to_path(cuts: list[TrapezoidalCut]):
    optimizer = GlobalOptimizerModule()
    weights, groups = optimizer._generate_weights(cuts, Container.cost_function)
    gtsp = GTSP(weights, groups)
    best_chrom, _ = run_gcga(
        gtsp,
        pop_size=100,
        generations=1000,
        crossover_prob=0.9,
        mutation_prob=0.15,
        tournament_k=3,
        elitism=2,
        do_head_reopt=True,
    )
    tour = gtsp.decode(best_chrom)
    trapezoid_path = optimizer._tour_to_path(tour, cuts, Container.cost_function)
    for i in range(len(cuts)):
        assert trapezoid_path[i] == cuts[i]


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
    cost_function: CostFunctionService = Container.cost_function,
):
    total_cost = 0
    cost_function = CostFunctionServiceImpl()
    for i in range(len(path) - 1):
        total_cost += cost_function.get_cost(
            path[i].end_configuration(), path[i + 1].start_configuration()
        )
    return total_cost
