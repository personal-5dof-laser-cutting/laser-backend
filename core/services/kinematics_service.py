from abc import ABC
import ctypes

from typing import Tuple
from core.models.geometry import Configuration, MotorPosition
from core.services.base import BaseService


class KinematicsService(ABC, BaseService):
    """Service that can use kinematics functions"""

    def get_positions(
        self, cartesian: Configuration, material_height: float
    ) -> Tuple[MotorPosition, MotorPosition]: ...


class KinematicsServiceImpl(KinematicsService):
    def __init__(self, config):
        self.config = config
        self.lib = ctypes.CDLL("core/services/kinematics.so")

        # Define the function signature
        self.lib.kinematics_closest_furthest.restype = None
        self.lib.kinematics_closest_furthest.argtypes = [
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,  # cartesian input (cx, cy, cz, ca, cb)
            ctypes.POINTER(ctypes.c_float),  # closest output array
            ctypes.POINTER(ctypes.c_float),  # furthest output array
            # machine config
            ctypes.c_float,  # center_x
            ctypes.c_float,  # center_y
            ctypes.c_float,  # z_height
            ctypes.c_float,  # rotation_offset
            ctypes.c_float,  # focus_offset
            ctypes.c_float,  # laser_head_z_angle
            ctypes.c_float,  # max_z
        ]

        self.center_x = self.config["Kinematics"]["rotating_table_five_axis"][
            "center_x"
        ]
        self.center_y = self.config["Kinematics"]["rotating_table_five_axis"][
            "center_y"
        ]
        self.z_height = self.config["Kinematics"]["rotating_table_five_axis"][
            "z_height"
        ]
        self.rotation_offset = self.config["Kinematics"]["rotating_table_five_axis"][
            "rotation_offset"
        ]
        self.focus_offset = self.config["Kinematics"]["rotating_table_five_axis"][
            "focus_offset"
        ]
        self.laser_head_z_angle = 0.5
        self.max_z_mm = self.config["Kinematics"]["rotating_table_five_axis"][
            "max_z_mm"
        ]

    def get_positions(
        self, cartesian: Configuration, material_height: float
    ) -> Tuple[MotorPosition, MotorPosition]:
        closest = (ctypes.c_float * 5)()
        furthest = (ctypes.c_float * 5)()

        self.lib.kinematics_closest_furthest(
            cartesian.x,
            cartesian.y,
            material_height,
            cartesian.alpha,
            cartesian.beta,
            closest,
            furthest,
            self.center_x,
            self.center_y,
            self.z_height,
            self.rotation_offset,
            self.focus_offset,
            self.laser_head_z_angle,
            self.max_z_mm,
        )

        closest = MotorPosition(*closest, isRadians=False)
        furthest = MotorPosition(*furthest, isRadians=False)

        return (closest, furthest)
