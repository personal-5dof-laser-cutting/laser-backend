import math
from core.models.geometry import TrapezoidalCut, Point
import pytest


@pytest.mark.parametrize(
    "cut, expected_table, expected_head",
    [
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(1, 1, 0), Point(0, 0, -1), Point(1, 1, -1)
            ),
            0,
            0,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(1, 0, 0), Point(0, 1, -1), Point(1, 1, -1)
            ),
            90,
            -45,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(1, 1, 0), Point(0, 1, -1), Point(1, 2, -1)
            ),
            45,
            -45,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(0, 1, 0), Point(-1, 0, -1), Point(-1, 1, -1)
            ),
            0,
            -45,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(-1, 1, 0), Point(-1, 0, -1), Point(-2, 1, -1)
            ),
            -45,
            -45,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(-1, 0, 0), Point(0, -1, -1), Point(-1, -1, -1)
            ),
            90,
            45,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(-1, -1, 0), Point(0, -1, -1), Point(-1, -2, -1)
            ),
            45,
            45,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(0, -1, 0), Point(1, 0, -1), Point(1, -1, -1)
            ),
            0,
            45,
        ),
        (
            TrapezoidalCut(
                Point(0, 0, 0), Point(1, -1, 0), Point(1, 0, -1), Point(2, -1, -1)
            ),
            -45,
            45,
        ),
    ],
)
def test_angle(cut: TrapezoidalCut, expected_table: float, expected_head: float):
    table, laser_head = cut.cutter_angles(unit="degree")
    assert math.isclose(table, expected_table)
    assert math.isclose(laser_head, expected_head)
