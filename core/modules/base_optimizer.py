from abc import ABC, abstractmethod
import logging
from typing import final


from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module
from core.service_container import Container

log = logging.getLogger("Optimizer")


class BaseOptimizer(Module[Geometry, Geometry], ABC):
    material_height: float
    start_configuration: Configuration
    geometry: Geometry

    current_travel_cost: float = 0

    def __init__(
        self, material_height: float, start_location: Configuration | None = None
    ):
        super().__init__()
        self.material_height = material_height
        self.start_configuration = start_location or Configuration(0, 0, 0, 0)

    @abstractmethod
    def _optimize(self): ...

    @abstractmethod
    def get_current_cost(self, as_cycle: bool) -> float: ...

    @final
    def process(self, data: Geometry) -> Geometry:
        self.geometry = data
        self._build_cache
        self._optimize()
        return self.geometry

    def _build_cache(self):
        cuts: list[TrapezoidalCut] = self.geometry.cuts
        configurations: list[Configuration] = [
            config for cut in cuts for config in cut.configurations()
        ]
        Container.kinematics_service.generate_cache(
            configurations, self.material_height
        )
