from abc import ABC, abstractmethod
from typing import Tuple

import yaml

from core.services.base import BaseService


class LaserConfigService(ABC, BaseService):
    """Service that provides configuration details"""

    @abstractmethod
    def gantry_height_mm(self) -> float: ...

    @abstractmethod
    def gantry_dim_mm(self) -> Tuple[float, float]: ...  # w, h

    @abstractmethod
    def get_rotating_kinematics(self) -> dict: ...

    @abstractmethod
    def get_max_rates(self) -> dict[str, int]: ...

    @abstractmethod
    def steps_per_mm(self) -> dict[str, int]: ...


class LaserConfigServiceImpl(LaserConfigService):
    def __init__(self) -> None:
        super().__init__()
        with open("config.yaml") as config_file:
            self.config = yaml.safe_load(config_file)

    def gantry_height_mm(self) -> float:
        focus_offset = self.config["Kinematics"]["rotating_table_five_axis"][
            "focus_offset"
        ]
        z_height = self.config["Kinematics"]["rotating_table_five_axis"]["z_height"]
        return focus_offset + z_height

    def gantry_dim_mm(self) -> Tuple[float, float]:
        max_x = self.config["Kinematics"]["rotating_table_five_axis"]["max_x"]
        max_y = self.config["Kinematics"]["rotating_table_five_axis"]["max_y"]
        return max_x, max_y

    def get_rotating_kinematics(self) -> dict:
        return self.config["Kinematics"]["rotating_table_five_axis"]

    def get_max_rates(self) -> dict[str, int]:
        return {
            "x": self.config["axes"]["x"]["max_rate_mm_per_min"],
            "y": self.config["axes"]["y"]["max_rate_mm_per_min"],
            "z": self.config["axes"]["z"]["max_rate_mm_per_min"],
            "a": self.config["axes"]["a"]["max_rate_mm_per_min"],
            "b": self.config["axes"]["b"]["max_rate_mm_per_min"],
        }

    def steps_per_mm(self) -> dict[str, int]:
        return {
            "x": self.config["axes"]["x"]["steps_per_mm"],
            "y": self.config["axes"]["y"]["steps_per_mm"],
            "z": self.config["axes"]["z"]["steps_per_mm"],
            "a": self.config["axes"]["a"]["steps_per_mm"],
            "b": self.config["axes"]["b"]["steps_per_mm"],
        }
