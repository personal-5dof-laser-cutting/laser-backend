from abc import ABC, abstractmethod
import ctypes

from typing import Iterable, Tuple

import numpy as np
from core.models.geometry import Configuration, MotorPosition
from core.services.base import BaseService


class KinematicsService(ABC, BaseService):
    """Service that can use kinematics functions"""

    @abstractmethod
    def get_positions(
        self, cartesian: Configuration, material_thickness: float
    ) -> Tuple[MotorPosition, MotorPosition]: ...

    @abstractmethod
    def generate_cache(
        self, configurations: Iterable[Configuration], material_thickness: float
    ): ...


class KinematicsServiceImpl(KinematicsService):
    def __init__(self, rotating_kinematics):
        self.rotating_kinematics = rotating_kinematics
        self.lib = ctypes.CDLL("core/services/kinematics.so")

        # Define the function signature
        self.lib.cartesian_to_closest_furthest_c.argtypes = [
            # cartesian input
            ctypes.POINTER(ctypes.c_float),  # cx
            ctypes.POINTER(ctypes.c_float),  # cy
            ctypes.POINTER(ctypes.c_float),  # cz
            ctypes.POINTER(ctypes.c_float),  # ca
            ctypes.POINTER(ctypes.c_float),  # cb
            ctypes.c_int,  # number of cartesian positions
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
        self.lib.cartesian_to_closest_furthest_c.restype = None

        self.center_x = self.rotating_kinematics["center_x"]
        self.center_y = self.rotating_kinematics["center_y"]
        self.z_height = self.rotating_kinematics["z_height"]
        self.rotation_offset = self.rotating_kinematics["rotation_offset"]
        self.focus_offset = self.rotating_kinematics["focus_offset"]
        self.laser_head_z_angle = 0.5
        self.max_z_mm = self.rotating_kinematics["max_z_mm"]

        self.cache: dict[Configuration, Tuple[MotorPosition, MotorPosition]] = {}

    def get_positions(
        self, cartesian: Configuration, material_thickness: float
    ) -> Tuple[MotorPosition, MotorPosition]:
        if cartesian not in self.cache:
            self.generate_cache([cartesian], material_thickness)

        return self.cache[cartesian]

    def generate_cache(
        self, configurations: Iterable[Configuration], material_thickness: float
    ):
        configurations_f = np.array(
            [[c.x, c.y, c.alpha, c.beta] for c in configurations]
        ).astype(np.float32)
        n = len(configurations_f)
        cx = np.ascontiguousarray(configurations_f[:, 0], dtype=np.float32)
        cy = np.ascontiguousarray(configurations_f[:, 1], dtype=np.float32)
        cz = np.ascontiguousarray(np.full(n, material_thickness, dtype=np.float32))
        ca = np.ascontiguousarray(configurations_f[:, 2], dtype=np.float32)
        cb = np.ascontiguousarray(configurations_f[:, 3], dtype=np.float32)

        closest = np.zeros((n, 6), dtype=np.float32)
        furthest = np.zeros((n, 6), dtype=np.float32)

        self.lib.cartesian_to_closest_furthest_c(
            cx.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            cy.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            cz.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ca.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            cb.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.c_int(n),
            closest.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            furthest.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.c_float(self.center_x),
            ctypes.c_float(self.center_y),
            ctypes.c_float(self.z_height),
            ctypes.c_float(self.rotation_offset),
            ctypes.c_float(self.focus_offset),
            ctypes.c_float(self.laser_head_z_angle),
            ctypes.c_float(self.max_z_mm),
        )
        results = [
            (MotorPosition(*c[:-1]), MotorPosition(*f[:-1]))
            for c, f in zip(closest, furthest)
        ]

        for conf, positions in zip(configurations, results):
            self.cache[conf] = positions
