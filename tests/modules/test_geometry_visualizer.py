from Geometry3D import Point
import pytest
import os

from core.modules.debug_visualizer import DebugVisualizerModule, VisualizerFlags
from core.models.geometry import Geometry, TrapezoidalCut

IN_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

SQUARE_PARAMS = [
    TrapezoidalCut(Point(0, 0, 0), Point(0, 3, 0), Point(1, 1, -2), Point(1, 2, -2)),
    TrapezoidalCut(Point(0, 3, 0), Point(3, 3, 0), Point(1, 2, -2), Point(2, 2, -2)),
    TrapezoidalCut(Point(3, 3, 0), Point(3, 0, 0), Point(2, 2, -2), Point(2, 1, -2)),
    TrapezoidalCut(Point(3, 0, 0), Point(0, 0, 0), Point(2, 1, -2), Point(1, 1, -2)),
    TrapezoidalCut(Point(5, 0, 0), Point(8, 0, 0), Point(6, 0, -2), Point(7, 0, -2)),
]


@pytest.mark.parametrize("cuts", [SQUARE_PARAMS])
def test_visualizer(cuts: list[TrapezoidalCut]):
    dv = DebugVisualizerModule(2, VisualizerFlags.SHOW_ORDER)
    geo = Geometry()
    for cut in cuts:
        geo.add_cut(cut)

    dv.process(geo)
