from Geometry3D import Point
import pytest

from core.pipeline.geometry_visualizer import GeometryVisualizerModule
from core.models.geometry import Geometry, TrapezoidalCut

SQUARE_PARAMS = [
    TrapezoidalCut(Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -2), Point(1, 2, -2)),
    TrapezoidalCut(Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -2), Point(2, 2, -2)),
    TrapezoidalCut(Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -2), Point(2, 1, -2)),
    TrapezoidalCut(Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -2), Point(1, 1, -2)),
]


@pytest.mark.parametrize("cuts", [SQUARE_PARAMS])
def test_visualizer(cuts: list[TrapezoidalCut]):
    gv = GeometryVisualizerModule()
    geo = Geometry()
    for cut in cuts:
        geo.add_cut(cut)

    gv.process(geo)
