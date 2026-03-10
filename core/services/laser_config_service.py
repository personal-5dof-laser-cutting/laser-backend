from abc import ABC
from typing import Tuple

from core.services.base import BaseService
from core.models.geometry import Configuration


class LaserConfigService(ABC, BaseService):
    """Service that calculates the cost between two configurations"""

    def get_cost(self, conf1: Configuration, conf2: Configuration) -> float: ...

    def gantry_height_mm(self) -> float: ...

    def gantry_dim_mm(self) -> Tuple[float, float]: ...  # w, h


class LaserConfigServiceImpl(LaserConfigService):
    def get_cost(self, conf1: Configuration, conf2: Configuration) -> float:
        return ((conf1.x - conf2.x) ** 2 + (conf1.y - conf2.y) ** 2) ** (1 / 2) + (
            (conf1.alpha - conf2.alpha) ** 2 + (conf1.beta - conf2.beta) ** 2
        ) ** (1 / 2)

    def gantry_height_mm(self) -> float:
        return 130

    def gantry_dim_mm(self) -> Tuple[float, float]:
        return 400, 400
