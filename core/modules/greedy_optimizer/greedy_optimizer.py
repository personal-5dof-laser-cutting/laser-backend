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
        self.best_first()
        return data
        cuts = self.geometry.cuts
        next_cost = inf
        next_cut = -1
        flipped = False
        for i in range(0, len(cuts)):
            for neighbour in range(i, len(cuts)):
                cost = self.get_cost(cuts[i - 1], cuts[neighbour])
                if cost < next_cost:
                    next_cost = cost
                    next_cut = neighbour
                    flipped = False
                cost = self.get_cost(cuts[i - 1], cuts[neighbour].flipped_direction())
                if cost < next_cost:
                    next_cost = cost
                    next_cut = neighbour
                    flipped = True

            if flipped:
                cuts[next_cut] = cuts[next_cut].flipped_direction()

            cuts[i], cuts[next_cut] = (
                cuts[next_cut],
                cuts[i],
            )

            next_cost = inf

        return data
