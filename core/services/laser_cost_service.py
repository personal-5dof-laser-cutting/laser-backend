from abc import ABC, abstractmethod
from functools import cache

from core.models.geometry import Configuration, MotorPosition
from core.services.base import BaseService
from core.services.kinematics_service import KinematicsService


class LaserCostService(ABC, BaseService):
    """Service that calculates the cost between two configurations"""

    @abstractmethod
    @cache
    def get_cost(
        self, conf1: Configuration, conf2: Configuration, material_height: float
    ) -> float: ...

    @abstractmethod
    def chebyshev_distance(
        self, mpos1: MotorPosition, mpos2: MotorPosition
    ) -> float: ...


class LaserCostServiceImpl(LaserCostService):
    def __init__(
        self, max_rates: dict[str, int], kinematics: KinematicsService
    ) -> None:
        super().__init__()
        self.max_rates = max_rates
        self.kinematics = kinematics

    @cache
    def get_cost(
        self, conf1: Configuration, conf2: Configuration, material_height: float
    ) -> float:
        # We ignore conf1_pos2 because they are symmetric around the table center
        conf1_pos1, _ = self.kinematics.get_positions(conf1, material_height)
        conf2_pos1, conf2_pos2 = self.kinematics.get_positions(conf2, material_height)
        min_time = min(
            self.chebyshev_distance(conf1_pos1, conf2_pos1),
            self.chebyshev_distance(conf1_pos1, conf2_pos2),
        )

        return min_time

    def chebyshev_distance(self, mpos1: MotorPosition, mpos2: MotorPosition) -> float:
        delta = mpos1.delta(mpos2)
        chebyshevd_dist = max(
            [
                distance / self.max_rates[axis]
                for axis, distance in delta.axes_dict().items()
            ]
        )
        return chebyshevd_dist
