from abc import ABC, abstractmethod

from core.services.base import BaseService


class LaserService(ABC, BaseService):
    """Service that handles serial communication with the machine"""

    @abstractmethod
    def is_laser_connected(self) -> bool: ...


class LaserServiceImpl(LaserService):
    def is_laser_connected(self) -> bool:
        raise NotImplementedError()  # placeholder
