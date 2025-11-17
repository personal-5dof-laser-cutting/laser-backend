from core.models.geometry import TrapezoidalCut
from Geometry3D import Point, Segment, Vector
import pytest


def test_from_points():
    su = Point(0, 0, 0)
    eu = Point(1, 0, 0)
    sl = Point(0, 0, -1)
    el = Point(1, 0, -1)
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
        # this trapezoid does not have two pairs of parallel lines
        TrapezoidalCut(Point(0, 0, 1), Point(1, 0, 1), Point(0, 0, 1), Point(1, 0, 2))


@pytest.mark.parametrize(
    "trapezoidal_cut,expected_cut_depth",
    [
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(1, 0, 0), Point(0, 0, -1), Point(1, 0, -1)
            ),
            1,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(1, 0, 0), Point(-1, 0, -0.5), Point(1, 0, -0.5)
            ),
            0.5,
        ),
    ],
)
def test_cut_depth(trapezoidal_cut: TrapezoidalCut, expected_cut_depth: float):
    assert trapezoidal_cut.cut_depth == pytest.approx(expected_cut_depth, 0.01)


def test_move():
    t1 = TrapezoidalCut(
        Point(0, 0, 0), Point(1, 0, 0), Point(0, 0, -1), Point(1, 0, -1)
    )
    t2 = TrapezoidalCut(
        Point(1, 0, 0), Point(2, 0, 0), Point(1, 0, -1), Point(2, 0, -1)
    )

    t1_moved = t1.move(Vector(1, 0, 0))
    assert t1_moved.polygon() == t2.polygon()
