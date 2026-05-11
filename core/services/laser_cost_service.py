from abc import ABC
from math import inf

from core.models.geometry import Configuration
from core.services.base import BaseService
from core.services.kinematics_service import KinematicsService


class LaserCostService(ABC, BaseService):
    """Service that calculates the cost between two configurations"""

    def get_cost(
        self, conf1: Configuration, conf2: Configuration, material_height: float
    ) -> float: ...


class LaserCostServiceImpl(LaserCostService):
    def __init__(
        self, max_rates: dict[str, int], kinematics: KinematicsService
    ) -> None:
        super().__init__()
        self.max_rates = max_rates
        self.kinematics = kinematics

    def get_cost(
        self, conf1: Configuration, conf2: Configuration, material_height: float
    ) -> float:
        conf1_pos1, conf1_pos2 = self.kinematics.get_positions(conf1, material_height)
        conf2_pos1, conf2_pos2 = self.kinematics.get_positions(conf2, material_height)
        deltas = [conf1_pos1.delta(conf2_pos1), conf1_pos1.delta(conf2_pos2)]
        min_time = inf

        for delta in deltas:
            chebyshev_dist = max(
                *[
                    distance / self.max_rates[axis]
                    for axis, distance in delta.axes_dict().items()
                ]
            )
            min_time = min(min_time, chebyshev_dist)
        return min_time
