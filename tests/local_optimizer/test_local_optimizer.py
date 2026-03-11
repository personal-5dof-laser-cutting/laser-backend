from Geometry3D import Point
import pytest
from core.models.geometry import Geometry, TrapezoidalCut
from core.modules.local_optimizer.local_optimizer import LocalOptimizer


def test_local_optimizer():
    cut1 = TrapezoidalCut(
        Point(-1, 0, 0), Point(0, 0, 0), Point(0, 0, -1), Point(1, 0, -1)
    )
    geo = Geometry()
    geo.add_cut(cut1)

    optimizer = LocalOptimizer()

    result = optimizer.process(geo).cuts[0]
    print(result)
