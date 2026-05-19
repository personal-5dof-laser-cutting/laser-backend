from Geometry3D import Point
import pytest

from core.models.geometry import Geometry, TrapezoidalCut


SQUARE_PARAMS = [
    TrapezoidalCut(Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -5), Point(1, 2, -5)),
    TrapezoidalCut(Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -5), Point(2, 2, -5)),
    TrapezoidalCut(Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -5), Point(2, 1, -5)),
    TrapezoidalCut(Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -5), Point(1, 1, -5)),
]


@pytest.mark.parametrize("cuts", [SQUARE_PARAMS])
def test_travel_cost(cuts: list[TrapezoidalCut]):
    geo = Geometry()
    geo.cuts = cuts

    material_height = 5
    assert geo.calculate_travel_cost(material_height, as_tour=False) == 0

    geo.cuts[1] = geo.cuts[1].flipped_direction()

    assert geo.calculate_travel_cost(material_height, as_tour=False) == geo.cuts[
        0
    ].travel_time_to(geo.cuts[1], material_height) + geo.cuts[1].travel_time_to(
        geo.cuts[2], material_height
    )
