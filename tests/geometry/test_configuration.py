from core.models.geometry import Configuration
from Geometry3D import Segment, Point
import pytest
import math


@pytest.mark.parametrize(
    "segment, expected_x, expected_y, expected_alpha, expected_beta",
    [
        (Segment(Point(0, 0, 1), Point(0, 0, 0)), 0, 0, 0, 0),
        (Segment(Point(0, 0, 1), Point(1, 0, 0)), 0, 0, 0, 45),
        (Segment(Point(0, 0, 1), Point(0, 1, 0)), 0, 0, 45, 0),
        (Segment(Point(1.5, 1, 1), Point(0, 0, 0)), 1.5, 1, -45, -56.31),
        (Segment(Point(0, 0, 1), Point(-1, -0.5, 0)), 0, 0, -26.56, -45),
    ],
)
def test_config(
    segment: Segment,
    expected_x: float,
    expected_y: float,
    expected_alpha: float,
    expected_beta: float,
):
    config = Configuration.from_segment(segment)
    assert config.x == pytest.approx(expected_x, 0.01)
    assert config.y == pytest.approx(expected_y, 0.01)
    assert config.alpha_deg == pytest.approx(expected_alpha, 0.01)
    assert config.beta_deg == pytest.approx(expected_beta, 0.01)


def test_deg_rad_conversion():
    config = Configuration(0, 0, 90, 90)

    assert config.alpha_deg == 90.0
    assert config.beta_deg == 90.0
    assert config.alpha_rad == pytest.approx(math.pi / 2, 0.01)
    assert config.beta_rad == pytest.approx(math.pi / 2, 0.01)


def test_over_limits():
    with pytest.raises(ValueError):
        Configuration(0, 0, 91, 0)

    with pytest.raises(ValueError):
        Configuration(0, 0, 0, -91)
