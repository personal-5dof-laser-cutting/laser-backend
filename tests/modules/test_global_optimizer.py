from math import inf
import pytest
import networkx as nx
from Geometry3D import Point, Segment
from core.modules.global_optimizer import GlobalOptimizerModule
from core.models.geometry import Geometry, TrapezoidalCut, Configuration
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


@pytest.mark.parametrize(
    "cuts",
    [
        [
            TrapezoidalCut(
                Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)
            ),
            TrapezoidalCut(
                Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)
            ),
        ],
        [
            TrapezoidalCut(
                Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)
            ),
            TrapezoidalCut(
                Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)
            ),
            TrapezoidalCut(
                Point(3, 3, 0), Point(0, 0, 0), Point(2, 2, -5), Point(1, 1, -5)
            ),
        ],
    ],
)
def test_build_graph(cuts: list[TrapezoidalCut]):
    generated_graph = nx.Graph()
    control_graph = nx.Graph()
    cost_function = CostFunctionServiceImpl()
    optimizer = GlobalOptimizerModule()
    optimizer._build_graph(generated_graph, cuts, cost_function, True)

    expected_nodes = []
    for cut in cuts:
        expected_nodes += [cut] + cut.configurations()
    control_graph.add_nodes_from(expected_nodes)
    assert control_graph.nodes == generated_graph.nodes

    for u in expected_nodes:
        for v in expected_nodes:
            if u != v:
                control_graph.add_edge(u, v)

    assert control_graph.edges == generated_graph.edges


def test_triangle_constallation():
    cuts = [
        TrapezoidalCut(
            Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)
        ),
        TrapezoidalCut(
            Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)
        ),
        TrapezoidalCut(
            Point(3, 3, 0), Point(0, 0, 0), Point(2, 2, -5), Point(1, 1, -5)
        ),
    ]
    optimizer = GlobalOptimizerModule()
    graph = nx.Graph()
    optimizer._build_graph(graph, cuts, CostFunctionServiceImpl(), True)
    assert (
        graph.get_edge_data(cuts[0].start_configuration(), cuts[0].end_configuration())[
            "weight"
        ]
        == inf
    )
    assert (
        graph.get_edge_data(cuts[1].start_configuration(), cuts[1].end_configuration())[
            "weight"
        ]
        == inf
    )
    assert (
        graph.get_edge_data(cuts[2].start_configuration(), cuts[2].end_configuration())[
            "weight"
        ]
        == inf
    )
    pass


@pytest.mark.parametrize(
    "path, cuts",
    [
        (
            [
                Configuration.from_segment(Segment(Point(0, 0, 0), Point(1, 1, -5))),
                TrapezoidalCut(
                    Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)
                ),
                Configuration.from_segment(Segment(Point(0, 3, 0), Point(1, 2, -5))),
                Configuration.from_segment(Segment(Point(0, 3, 0), Point(1, 2, -5))),
                TrapezoidalCut(
                    Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)
                ),
                Configuration.from_segment(Segment(Point(3, 3, 0), Point(2, 2, -5))),
                Configuration.from_segment(Segment(Point(3, 3, 0), Point(2, 2, -5))),
                TrapezoidalCut(
                    Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -5), Point(2, 1, -5)
                ),
                Configuration.from_segment(Segment(Point(3, 0, 0), Point(2, 1, -5))),
                Configuration.from_segment(Segment(Point(3, 0, 0), Point(2, 1, -5))),
                TrapezoidalCut(
                    Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -5), Point(1, 1, -5)
                ),
                Configuration.from_segment(Segment(Point(0, 0, 0), Point(1, 1, -5))),
            ],
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
            ],
        ),
        (
            [
                Configuration.from_segment(Segment(Point(0, 0, 0), Point(1, 1, -5))),
                TrapezoidalCut(
                    Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)
                ),
                Configuration.from_segment(Segment(Point(0, 3, 0), Point(1, 2, -5))),
                TrapezoidalCut(
                    Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)
                ),
                Configuration.from_segment(Segment(Point(3, 3, 0), Point(2, 2, -5))),
                TrapezoidalCut(
                    Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -5), Point(2, 1, -5)
                ),
                Configuration.from_segment(Segment(Point(3, 0, 0), Point(2, 1, -5))),
                TrapezoidalCut(
                    Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -5), Point(1, 1, -5)
                ),
                Configuration.from_segment(Segment(Point(0, 0, 0), Point(1, 1, -5))),
            ],
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
            ],
        ),
    ],
)
def test_path_to_trapezoids(
    path: list[TrapezoidalCut | Configuration], cuts: list[TrapezoidalCut]
):
    go = GlobalOptimizerModule()
    ls_path = path.copy()
    rs_path = path.copy()
    trapezoids = go._path_to_trapezoids(path)
    assert set(trapezoids) == set(cuts)

    if len(path) == 0:
        return

    ls_path.pop()
    ls_path.append(ls_path.pop(0))
    ls_path.append(ls_path[0])
    trapezoids = go._path_to_trapezoids(ls_path)
    assert set(trapezoids) == set(cuts)

    rs_path.pop()
    rs_path.insert(0, rs_path.pop())
    rs_path.append(rs_path[0])
    trapezoids = go._path_to_trapezoids(rs_path)
    assert set(trapezoids) == set(cuts)


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
