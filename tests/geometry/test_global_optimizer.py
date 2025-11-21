import pytest
import networkx as nx
from Geometry3D import Point
from core.pipeline.global_optimizer import GlobalOptimizerModule
from core.models.geometry import Geometry, TrapezoidalCut, Configuration
from core.service_container import Container
from core.services.cost_function_service import (
    CostFunctionService,
    CostFunctionServiceImpl,
)
from dependency_injector.wiring import inject, Provide

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


@pytest.mark.parametrize(
    "cut1, cut2",
    [
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)
            ),
            TrapezoidalCut(
                Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)
            ),
        )
    ],
)
def test_build_graph(cut1: TrapezoidalCut, cut2: TrapezoidalCut):
    generated_graph = nx.Graph()
    control_graph = nx.Graph()
    cost_function = CostFunctionServiceImpl()
    optimizer = GlobalOptimizerModule()
    optimizer._build_graph(generated_graph, [cut1, cut2], cost_function)

    expected_nodes = [
        cut1,
        cut1.start_configuration(),
        cut1.end_configuration(),
        cut2,
        cut2.start_configuration(),
        cut2.end_configuration(),
    ]
    control_graph.add_nodes_from(expected_nodes)
    assert control_graph.nodes == generated_graph.nodes

    for u in expected_nodes:
        for v in expected_nodes:
            if u != v:
                control_graph.add_edge(u, v)

    assert control_graph.edges == generated_graph.edges


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
    assert set(trapezoids) == set(cuts)

    ls_path = path
    ls_path.append(ls_path.pop(0))
    trapezoids = go._path_to_trapezoids(path)
    assert set(trapezoids) == set(cuts)

    rs_path = path
    rs_path.insert(0, rs_path.pop())
    trapezoids = go._path_to_trapezoids(path)
    assert set(trapezoids) == set(cuts)


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
    print(f"Original cost was {original_costs}")
    print(f"Optimized cost is {optimized_costs}")


@inject
def _calculate_path_cost(
    path: list[TrapezoidalCut],
    cost_function: CostFunctionService = Provide[Container.cost_function],
):
    total_cost = 0
    cost_function = CostFunctionServiceImpl()
    for i in range(len(path) - 1):
        total_cost += cost_function.get_cost(
            path[i].end_configuration(), path[i + 1].start_configuration()
        )
    return total_cost
