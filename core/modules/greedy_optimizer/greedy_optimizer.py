from math import inf

from core.pipeline.base import Module
from core.models.geometry import Configuration, Geometry
from core.service_container import Container


class GreedyOptimizerModule(Module[Geometry, Geometry]):
    def __init__(
        self,
        material_height: float,
        start_location: Configuration = Configuration(0, 0, 0, 0),
    ):
        super().__init__
        self.material_height = material_height
        self.start_location = start_location
        self.get_cost = Container.laser_cost.get_cost

    def process(self, data: Geometry) -> Geometry:
        next_cost = inf
        next_cut = -1
        flipped = False
        current_conf = self.start_location
        for i in range(0, len(data.cuts)):
            for neighbour in range(i, len(data.cuts)):
                cut = data.cuts[neighbour]
                cost = self.get_cost(
                    current_conf, cut.start_configuration(), self.material_height
                )
                if cost < next_cost:
                    next_cost = cost
                    next_cut = neighbour
                    flipped = False
                cost = self.get_cost(
                    current_conf, cut.end_configuration(), self.material_height
                )
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
