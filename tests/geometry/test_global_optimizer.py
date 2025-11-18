import pytest
from Geometry3D import Point
from core.pipeline.global_optimizer import GlobalOptimizerModule
from core.models.geometry import Geometry, TrapezoidalCut, Configuration
from core.services.cost_function_service import CostFunctionService

TEST_PARAMS = [
    [
        TrapezoidalCut(
            Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)
        ),
        TrapezoidalCut(
            Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)
        ),
        TrapezoidalCut(
            Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -5), Point(2, 1, -5)
        ),
        TrapezoidalCut(
            Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -5), Point(1, 1, -5)
        ),
    ]
]


@pytest.mark.parametrize("cuts", TEST_PARAMS)
def test_path_to_trapezoids(
    cuts: list[TrapezoidalCut],
):
    path: list[TrapezoidalCut | Configuration] = []
    for cut in cuts:
        path.append(cut.start_configuration())
        path.append(cut)
        path.append(cut.end_configuration())
    path.append(path[0])

    go = GlobalOptimizerModule()
    trapezoids = go._path_to_trapezoids(path)
    for trapezoid, cut in zip(trapezoids, cuts):
        assert trapezoid == cut

    ls_path = path
    ls_path.append(ls_path.pop(0))
    trapezoids = go._path_to_trapezoids(path)
    for trapezoid, cut in zip(trapezoids, cuts):
        assert trapezoid == cut

    rs_path = path
    rs_path.insert(0, rs_path.pop())
    trapezoids = go._path_to_trapezoids(path)
    for trapezoid, cut in zip(trapezoids, cuts):
        assert trapezoid == cut


@pytest.mark.parametrize("cuts", TEST_PARAMS)
def test_global_optimizer(cuts: list[TrapezoidalCut]):
    geo_rep = Geometry()
    geo_rep.cuts = cuts

    optimizer = GlobalOptimizerModule()
    optimized_geo = optimizer.process(geo_rep)

    original_costs = _calculate_path_cost(geo_rep.cuts)
    optimized_costs = _calculate_path_cost(optimized_geo.cuts)
    assert original_costs > optimized_costs or original_costs == pytest.approx(
        optimized_costs
    )


def _calculate_path_cost(path: list[TrapezoidalCut]):
    total_cost = 0
    cost_function = CostFunctionService()
    for i in range(len(path) - 1):
        total_cost += cost_function.get_cost(
            path[i].end_configuration(), path[i + 1].start_configuration()
        )
    return total_cost
