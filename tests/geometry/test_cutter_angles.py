from core.models.geometry import Configuration
import pytest
import math


@pytest.mark.parametrize(
    "conf, expected_table, expected_head",
    [
        (Configuration(0, 0, 0, math.radians(45)), 0, 45),
        (
            Configuration(0, 0, math.radians(45), math.radians(45)),
            -45,
            math.degrees(math.acos(1 / math.sqrt(3))),
        ),
        (Configuration(0, 0, math.radians(45), 0), 90, -45),
        (
            Configuration(0, 0, math.radians(45), math.radians(-45)),
            45,
            -math.degrees(math.acos(1 / math.sqrt(3))),
        ),
        (Configuration(0, 0, 0, math.radians(-45)), 0, -45),
        (
            Configuration(0, 0, math.radians(-45), math.radians(-45)),
            -45,
            -math.degrees(math.acos(1 / math.sqrt(3))),
        ),
        (Configuration(0, 0, math.radians(-45), 0), 90, 45),
        (
            Configuration(0, 0, math.radians(-45), math.radians(45)),
            45,
            math.degrees(math.acos(1 / math.sqrt(3))),
        ),
    ],
)
def test_angles(conf: Configuration, expected_table: float, expected_head: float):
    table, laser_head = conf.get_cutter_angles(unit="degree")
    assert table == pytest.approx(expected_table, 0.01)
    assert laser_head == pytest.approx(expected_head, 0.01)
