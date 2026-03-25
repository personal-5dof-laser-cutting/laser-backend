from abc import ABC
from math import cos, isclose
from typing import Tuple

from numpy import sign
import yaml

from core.services.base import BaseService
from core.models.geometry import Configuration


class LaserConfigService(ABC, BaseService):
    """Service that calculates the cost between two configurations"""

    def get_cost(self, conf1: Configuration, conf2: Configuration) -> float: ...

    def gantry_height_mm(self) -> float: ...

    def gantry_dim_mm(self) -> Tuple[float, float]: ...  # w, h


class LaserConfigServiceImpl(LaserConfigService):
    def __init__(self) -> None:
        super().__init__()
        with open("config.yaml") as config_file:
            config = yaml.safe_load(config_file)
        self.rotation_offset = config["Kinematics"]["rotating_table_five_axis"][
            "rotation_offset"
        ]
        self.focus_offset = config["Kinematics"]["rotating_table_five_axis"][
            "focus_offset"
        ]
        self.max_rate: dict[str, int] = {
            "x": config["axes"]["x"]["max_rate_mm_per_min"],
            "y": config["axes"]["y"]["max_rate_mm_per_min"],
            "z": config["axes"]["z"]["max_rate_mm_per_min"],
            "a": config["axes"]["a"]["max_rate_mm_per_min"],
            "b": config["axes"]["b"]["max_rate_mm_per_min"],
        }
        self.center_x = config["Kinematics"]["rotating_table_five_axis"]["center_x"]
        self.center_y = config["Kinematics"]["rotating_table_five_axis"]["center_y"]
        self.focus_offset = config["Kinematics"]["rotating_table_five_axis"][
            "focus_offset"
        ]
        self.rotation_offset = config["Kinematics"]["rotating_table_five_axis"][
            "rotation_offset"
        ]
        self.max_z_mm = config["Kinematics"]["rotating_table_five_axis"]["max_z_mm"]

    def get_cost(self, conf1: Configuration, conf2: Configuration) -> float:
        distances = conf1.distance_to(
            conf2,
            self.center_x,
            self.center_y,
            self.focus_offset,
            self.rotation_offset,
            self.max_z_mm,
        )
        max_distance = 0
        for axis, distance in distances.items():
            max_distance = max(max_distance, distance * self.max_rate[axis])
        return max_distance

    def gantry_height_mm(self) -> float:
        return 130

    def gantry_dim_mm(self) -> Tuple[float, float]:
        return 400, 400


def _z_extension(angle1: float, angle2: float, zero_z_extension: float) -> float:
    if sign(angle1) == sign(angle2) or isclose(angle1, 0) or isclose(angle2, 0):
        return abs(zero_z_extension / cos(angle1) - zero_z_extension / cos(angle2))
    return _z_extension(angle1, 0, zero_z_extension) + _z_extension(
        0, angle2, zero_z_extension
    )
