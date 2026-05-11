import pytest
from Geometry3D import Point
from core.modules.genetic_optimizer.genetic_optimizer import GeneticOptimizerModule
from core.models.geometry import Geometry, TrapezoidalCut

SQUARE_PARAMS = [
    TrapezoidalCut(Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)),
    TrapezoidalCut(Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)),
    TrapezoidalCut(Point(3, 6, 0), Point(3, 0, 0), Point(2, 2, -5), Point(2, 1, -5)),
    TrapezoidalCut(Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -5), Point(1, 1, -5)),
]


@pytest.mark.parametrize("cuts, tour", [(SQUARE_PARAMS, [0, 2, 4, 6])])
def test_tour_to_path(cuts: list[TrapezoidalCut], tour: list[int]):
    optimizer = GeneticOptimizerModule(5)
    trapezoid_path = optimizer._tour_to_path(
        tour,
        cuts,
    )
    for i in range(len(cuts)):
        # tour_to_path tries to eliminate the most costly travel move. Since all but from idx 1 to idx 2 are 0 it eliminates the second travel move by left-shifting the array twice
        assert trapezoid_path[i] == cuts[(i + 2) % len(cuts)]


@pytest.mark.parametrize("cuts", [SQUARE_PARAMS])
def test_genetic_optimizer(cuts: list[TrapezoidalCut]):
    geo_rep = Geometry()
    geo_rep.cuts = cuts

    material_height = 5
    optimizer = GeneticOptimizerModule(material_height)
    original_costs = geo_rep.calculate_travel_cost(material_height)

    optimized_geo = optimizer.process(geo_rep)
    optimized_costs = optimized_geo.calculate_travel_cost(material_height)

    assert original_costs > optimized_costs or original_costs == pytest.approx(
        optimized_costs
    )
