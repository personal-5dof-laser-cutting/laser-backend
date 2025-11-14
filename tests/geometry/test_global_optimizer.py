import pytest
from Geometry3D import Point
from core.pipeline.global_optimizer import GlobalOptimizerModule
from core.models.geometry import Geometry, TrapezoidalCut, Configuration
from core.service_container import Container


@pytest.mark.parametrize(
    "cuts, material_height, expected_order",
    [
        (
            [
                TrapezoidalCut(
                    Point(0, 0, 5), Point(0, 3, 5), Point(1, 1, 0), Point(1, 2, 0)
                ),
                TrapezoidalCut(
                    Point(0, 3, 5), Point(3, 3, 5), Point(1, 2, 0), Point(2, 2, 0)
                ),
                TrapezoidalCut(
                    Point(3, 3, 5), Point(3, 0, 5), Point(2, 2, 0), Point(2, 1, 0)
                ),
                TrapezoidalCut(
                    Point(3, 0, 5), Point(0, 0, 5), Point(2, 1, 0), Point(1, 1, 0)
                ),
            ],
            5,
            [],
        )
    ],
)
def test_path_to_trapezoids(
    cuts: list[TrapezoidalCut],
    material_height: float,
    expected_order: list[TrapezoidalCut],
):
    path: list[TrapezoidalCut | Configuration] = []
    for cut in cuts:
        path.append(cut.start_configuration())
        path.append(cut)
        path.append(cut.end_configuration())
    path.append(path[0])

    go = GlobalOptimizerModule()
    trapezoids = go._path_to_trapezoids(path, material_height)
    for trapezoid, cut in zip(trapezoids, cuts):
        assert trapezoid == cut

    ls_path = path
    ls_path.append(ls_path.pop(0))
    trapezoids = go._path_to_trapezoids(path, material_height)
    for trapezoid, cut in zip(trapezoids, cuts):
        assert trapezoid == cut

    rs_path = path
    rs_path.insert(0, rs_path.pop())
    trapezoids = go._path_to_trapezoids(path, material_height)
    for trapezoid, cut in zip(trapezoids, cuts):
        assert trapezoid == cut


def test_optimizer():
    Container()
    go = GlobalOptimizerModule()
    geo = Geometry(5)
    geo.add_cut(
        TrapezoidalCut(
            Point(-2, -2, 5), Point(2, -2, 5), Point(-1, -1, 0), Point(1, -1, 0)
        )
    )
    geo.add_cut(
        TrapezoidalCut(Point(2, -2, 5), Point(2, 2, 5), Point(1, -1, 0), Point(1, 1, 0))
    )
    geo.add_cut(
        TrapezoidalCut(Point(2, 2, 5), Point(-2, 2, 5), Point(1, 1, 0), Point(-1, 1, 0))
    )
    geo.add_cut(
        TrapezoidalCut(
            Point(-2, 2, 5), Point(-2, -2, 5), Point(-1, 1, 0), Point(-1, -1, 0)
        )
    )
    go.process(geo)
