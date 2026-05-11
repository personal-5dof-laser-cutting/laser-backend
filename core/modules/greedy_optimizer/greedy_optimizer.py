from itertools import combinations
from math import inf

from core.pipeline.base import Module
from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.service_container import Container
from core.services.kinematics_service import KinematicsService


class GreedyOptimizerModule(Module[Geometry, Geometry]):
    def __init__(
        self,
        material_height: float,
        kinematics: KinematicsService = Container.kinematics_service,
        start_location: Configuration = Configuration(0, 0, 0, 0),
    ):
        super().__init__
        self.kinematics = kinematics
        self.material_height = material_height
        self.start_location = start_location
        self.get_cost = lambda x, y: x.travel_time_to(y, self.material_height)

    def process(self, data: Geometry) -> Geometry:
        self.geometry = data
        self.build_cache()
        self.best_first()
        self.two_opt()
        return data

    def build_cache(self):
        cuts: list[TrapezoidalCut] = self.geometry.cuts
        configurations: list[Configuration] = [
            config for cut in cuts for config in cut.configurations()
        ]
        self.kinematics.generate_cache(configurations, self.material_height)

    def best_first(self):
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

    def two_opt(self):
        cuts = self.geometry.cuts
        found_improvement: bool = True
        previous_cost: float = self.geometry.calculate_travel_cost(self.material_height)
        improvement: float = 0
        iterations = 0
        while found_improvement:
            previous_cost += improvement
            improvement = 0
            found_improvement = False
            for cut1, cut2 in combinations(range(len(cuts)), 2):
                flip_1 = flip_2 = False
                flip_delta: float = 0
                if (cut1_flip_delta := self._cut_flip_delta(cuts, cut1)) < 0:
                    flip_delta += cut1_flip_delta
                    flip_1 = True
                if (cut2_flip_delta := self._cut_flip_delta(cuts, cut2)) < 0:
                    flip_delta += cut2_flip_delta
                    flip_2 = True

                if (two_opt_delta := self._edge_swap_delta(cuts, cut1, cut2)) >= 0:
                    continue

                if not (flip_1 or flip_1):
                    continue

                found_improvement = True

                if two_opt_delta <= flip_delta:
                    self._two_opt_swap(cuts, cut1, cut2)
                    improvement += two_opt_delta
                else:
                    if flip_1:
                        cuts[cut1] = cuts[cut1].flipped_direction()
                    if flip_2:
                        cuts[cut2] = cuts[cut2].flipped_direction()
                    improvement += flip_delta
            iterations += 1
            if (abs(improvement) / previous_cost) < 0.1:
                break
        pass

    def _two_opt_swap(self, cuts: list[TrapezoidalCut], cut1_idx: int, cut2_idx: int):
        if cut1_idx == cut2_idx:
            return

        # Set cut1_idx to the smaller index so we don't have to write the swap operation twice
        if cut1_idx > cut2_idx:
            cut1_idx, cut2_idx = cut2_idx, cut1_idx

        # This case wouldn't change the tour
        if cut2_idx == cut1_idx + 1:
            return

        i = cut1_idx + 1
        j = cut2_idx
        while i < j:
            cuts[i], cuts[j] = cuts[j].flipped_direction(), cuts[i].flipped_direction()
            i += 1
            j -= 1

    def _cut_flip_delta(self, cuts: list[TrapezoidalCut], cut_idx: int) -> float:
        cut = cut_idx
        cut_previous = (cut_idx - 1) % len(cuts)
        cut_next = (cut_idx + 1) % len(cuts)

        old_edges_cost = self.get_cost(cuts[cut_previous], cuts[cut]) + self.get_cost(
            cuts[cut], cuts[cut_next]
        )

        new_edges_cost = self.get_cost(
            cuts[cut_previous], cuts[cut].flipped_direction()
        ) + self.get_cost(cuts[cut].flipped_direction(), cuts[cut_next])

        return new_edges_cost - old_edges_cost

    def _edge_swap_delta(
        self, cuts: list[TrapezoidalCut], cut1_idx: int, cut2_idx: int
    ) -> float:
        cut1_next: int = (cut1_idx + 1) % len(cuts)
        cut2_next: int = (cut2_idx + 1) % len(cuts)

        old_edges_cost = self.get_cost(cuts[cut1_idx], cuts[cut1_next]) + self.get_cost(
            cuts[cut2_idx], cuts[cut2_next]
        )

        new_edges_cost = self.get_cost(
            cuts[cut1_idx], cuts[cut2_idx].flipped_direction()
        ) + self.get_cost(cuts[cut1_next].flipped_direction(), cuts[cut2_next])

        return new_edges_cost - old_edges_cost
