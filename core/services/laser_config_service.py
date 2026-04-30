from abc import ABC
from typing import Tuple

import yaml

from core.services.base import BaseService


class LaserConfigService(ABC, BaseService):
    """Service that provides configuration details"""

    def gantry_height_mm(self) -> float: ...

    def gantry_dim_mm(self) -> Tuple[float, float]: ...  # w, h

    def get_config(self) -> dict: ...

    def get_max_rates(self) -> dict[str, int]: ...


class LaserConfigServiceImpl(LaserConfigService):
    def __init__(self) -> None:
        super().__init__()
        with open("config.yaml") as config_file:
            self.config = yaml.safe_load(config_file)

    def gantry_height_mm(self) -> float:
        return 130

    def gantry_dim_mm(self) -> Tuple[float, float]:
        return 400, 400

    def get_config(self) -> dict:
        return self.config

    def get_max_rates(self) -> dict[str, int]:
        return {
            "x": self.config["axes"]["x"]["max_rate_mm_per_min"],
            "y": self.config["axes"]["y"]["max_rate_mm_per_min"],
            "z": self.config["axes"]["z"]["max_rate_mm_per_min"],
            "a": self.config["axes"]["a"]["max_rate_mm_per_min"],
            "b": self.config["axes"]["b"]["max_rate_mm_per_min"],
        }
