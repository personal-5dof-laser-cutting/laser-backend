from core.models.geometry import Configuration
from Geometry3D import Segment, Point
import pytest
import math


def test_straight_config():
    seg = Segment(Point(0, 0, 1), Point(0, 0, 0))
    config = Configuration.from_segment(seg)

    assert config.x == 0
    assert config.y == 0
    assert config.alpha_deg == 0.0
    assert config.beta_deg == 0.0


def test_angled_config_x():
    seg = Segment(Point(0, 0, 1), Point(1, 0, 0))
    config = Configuration.from_segment(seg)

    assert config.x == 0
    assert config.y == 0
    assert config.alpha_deg == 0
    assert config.beta_deg == pytest.approx(45, 0.01)


def test_angled_config_y():
    seg = Segment(Point(0, 0, 1), Point(0, 1, 0))
    config = Configuration.from_segment(seg)

    assert config.x == 0
    assert config.y == 0
    assert config.alpha_deg == pytest.approx(45, 0.01)
    assert config.beta_deg == 0


def test_angled_config1():
    seg = Segment(Point(1.5, 1, 1), Point(0, 0, 0))
    config = Configuration.from_segment(seg)

    assert config.x == 1.5
    assert config.y == 1
    assert config.alpha_deg == pytest.approx(math.degrees(math.atan(-1)), 0.01)
    assert config.beta_deg == pytest.approx(math.degrees(math.atan(-1.5)), 0.01)


def test_angled_config2():
    seg = Segment(Point(0, 0, 1), Point(-1, -0.5, 0))
    config = Configuration.from_segment(seg)

    assert config.x == 0
    assert config.y == 0
    assert config.beta_deg == pytest.approx(-45.0, 0.01)
    assert config.alpha_deg == pytest.approx(-math.degrees(math.atan(0.5)), 0.01)


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
