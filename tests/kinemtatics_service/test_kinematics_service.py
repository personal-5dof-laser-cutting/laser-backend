from core.models.geometry import Configuration, MotorPosition
from core.service_container import Container


def test_get_positions():
    ks = Container.kinematics_service

    c1, f1 = ks.get_positions(Configuration(0, 0, 0, 0), 5)
    c2, f2 = ks.get_positions(Configuration(1, 1, 0, 0), 5)

    assert c1.delta(c1) == MotorPosition(0, 0, 0, 0, 0)
    assert c1.delta(c2) == f1.delta(f2)
    assert c1.delta(f2) == f1.delta(c2)
