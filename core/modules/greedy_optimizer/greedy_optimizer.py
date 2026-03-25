from math import inf

from core.pipeline.base import Module
from core.models.geometry import Configuration, Geometry
from core.service_container import Container
from core.services.laser_config_service import LaserConfigService


class GreedyOptimizerModule(Module[Geometry, Geometry]):
    def __init__(self, start_location: Configuration = Configuration(0, 0, 0, 0)):
        super().__init__
        self.start_location = start_location
        self.laser_config: LaserConfigService = Container.laser_config

    def process(self, data: Geometry) -> Geometry:
        next_cost = inf
        next_cut = -1
        flipped = False
        current_conf = self.start_location
        for i in range(0, len(data.cuts)):
            for neighbour in range(i, len(data.cuts)):
                cut = data.cuts[neighbour]
                cost = self.laser_config.get_cost(
                    current_conf, cut.start_configuration()
                )
                if cost < next_cost:
                    next_cost = cost
                    next_cut = neighbour
                    flipped = False
                cost = self.laser_config.get_cost(current_conf, cut.end_configuration())
                if cost < next_cost:
                    next_cost = cost
                    next_cut = neighbour
                    flipped = True

            if flipped:
                data.cuts[next_cut] = data.cuts[next_cut].flip_direction()
            data.cuts[i], data.cuts[next_cut] = (
                data.cuts[next_cut],
                data.cuts[i],
            )

            current_conf = data.cuts[i].end_configuration()
            next_cost = inf

        return data
