from core.models.geometry import TrapezoidalCut
from Geometry3D import Point, Segment, Vector
import pytest


def test_from_points():
    su = Point(0, 0, 1)
    eu = Point(1, 0, 1)
    sl = Point(0, 0, 0)
    el = Point(1, 0, 0)
    t = TrapezoidalCut(su, eu, sl, el)

    assert t.start_top == su
    assert t.end_top == eu
    assert t.start_bottom == sl
    assert t.end_bottom == el
    assert t.bottom_segment() == Segment(sl, el)
    assert t.top_segment() == Segment(su, eu)
    assert t.start_segment() == Segment(su, sl)
    assert t.end_segment() == Segment(eu, el)


def test_invalid_cut():
    with pytest.raises(ValueError):
        TrapezoidalCut(Point(0, 0, 1), Point(1, 0, 1), Point(0, 0, 1), Point(1, 0, 2))


def test_cut_depth():
    t = TrapezoidalCut(Point(0, 0, 1), Point(1, 0, 1), Point(0, 0, 0), Point(1, 0, 0))
    assert t.cut_depth == 1

    t = TrapezoidalCut(
        Point(0, 0, 0.5), Point(1, 0, 0.5), Point(-1, 0, 0), Point(1, 0, 0)
    )
    assert t.cut_depth == 0.5


def test_move():
    t1 = TrapezoidalCut(Point(0, 0, 1), Point(1, 0, 1), Point(0, 0, 0), Point(1, 0, 0))
    t2 = TrapezoidalCut(Point(1, 0, 1), Point(2, 0, 1), Point(1, 0, 0), Point(2, 0, 0))

    t1.move(Vector(1, 0, 0))
    assert t1.polygon() == t2.polygon()
