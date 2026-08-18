from Geometry3D import Point, Segment

from core.models.geometry import Configuration, TrapezoidalCut
from core.service_container import Container


def test_get_cost():
    lcs = Container.laser_cost

    material_thickness = 5
    c1 = Configuration(0, 0, 0, 0)
    c2 = Configuration(1, 1, 0, 0)

    assert lcs.get_cost(c1, c1, material_thickness) == 0
    assert lcs.get_cost(c1, c2, material_thickness) == lcs.get_cost(
        c2, c1, material_thickness
    )

    a = TrapezoidalCut(
        Point(0, 0, 0),
        Point(0, 3, 0),
        Point(1, 1, -material_thickness),
        Point(1, 2, -material_thickness),
    )
    b = TrapezoidalCut(
        Point(0, 3, 0),
        Point(3, 3, 0),
        Point(1, 2, -material_thickness),
        Point(2, 2, -material_thickness),
    )

    assert a.travel_time_to(b, material_thickness) == Configuration.from_segment(
        Segment(Point(0, 3, 0), Point(1, 2, -material_thickness))
    ).travel_time_to(
        Configuration.from_segment(
            Segment(Point(0, 3, 0), Point(1, 2, -material_thickness))
        ),
        material_thickness,
    )
