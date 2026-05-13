from itertools import combinations
from math import inf, isclose

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
        max_iterations: int = 10,
    ):
        super().__init__()
        self.kinematics = kinematics
        self.material_height = material_height
        self.start_location = start_location
        self.max_iterations = max_iterations

    def process(self, data: Geometry) -> Geometry:
        self.geometry = data
        self._build_cache()
        self._best_first()
        self._two_opt()
        self._tour_to_shortest_path()
        return data

    def _build_cache(self):
        cuts: list[TrapezoidalCut] = self.geometry.cuts
        configurations: list[Configuration] = [
            config for cut in cuts for config in cut.configurations()
        ]
        self.kinematics.generate_cache(configurations, self.material_height)

    def _best_first(self):
        cuts = self.geometry.cuts

        start_idx, flip_cut = self._find_closest_cut(self.start_location, 0)
        if flip_cut:
            cuts[start_idx] = cuts[start_idx].flipped_direction()
        cuts[0], cuts[start_idx] = cuts[start_idx], cuts[0]

        for i in range(1, len(cuts) - 1):
            next_cut, flip_cut = self._find_closest_cut(
                cuts[i - 1].end_configuration(), i
            )

            if flip_cut:
                cuts[next_cut] = cuts[next_cut].flipped_direction()

            cuts[i], cuts[next_cut] = (
                cuts[next_cut],
                cuts[i],
            )

    def _find_closest_cut(
        self, start_conf: Configuration, start_idx: int
    ) -> tuple[int, bool]:
        cuts = self.geometry.cuts
        if start_idx >= len(cuts):
            return (0, False)
        closest_cut: int = start_idx
        flip_cut: bool = True
        closest_cost: float = inf
        for i in range(start_idx, len(cuts)):
            current_cost = start_conf.travel_time_to(
                cuts[i].start_configuration(), self.material_height
            )
            if current_cost < closest_cost:
                closest_cost = current_cost
                closest_cut = i
                flip_cut = False

            current_flipped_cost = start_conf.travel_time_to(
                cuts[i].end_configuration(), self.material_height
            )
            if current_flipped_cost < closest_cost:
                closest_cost = current_flipped_cost
                closest_cut = i
                flip_cut = True
        return closest_cut, flip_cut

    def _two_opt(self):
        cuts = self.geometry.cuts
        found_improvement: bool = True
        iterations: int = 0
        previous_cost: float = self.geometry.calculate_travel_cost(
            self.material_height, True
        )
        improvement: float = 0.0
        while found_improvement and iterations < self.max_iterations:
            found_improvement = False
            for cut1, cut2 in combinations(range(len(cuts)), 2):
                flip_1, flip_2, flip_delta = self._calculate_flip_improvement(
                    cut1, cut2
                )
                two_opt_delta = self._edge_swap_delta(cut1, cut2)

                if two_opt_delta >= 0 and flip_delta >= 0:
                    continue

                found_improvement = True
                improvement += self._apply_best_improvement(
                    cut1, cut2, two_opt_delta, flip_delta, flip_1, flip_2
                )

            iterations += 1
            if (abs(improvement) / previous_cost) < 0.1:
                break
            previous_cost += improvement
            improvement = 0

    def _calculate_flip_improvement(
        self, cut1: int, cut2: int
    ) -> tuple[bool, bool, float]:
        cut1_flip_delta = self._cut_flip_delta(cut1)
        cut2_flip_delta = self._cut_flip_delta(cut2)

        flip_1: bool = cut1_flip_delta < 0
        flip_2: bool = cut2_flip_delta < 0

        flip_delta: float = 0.0
        if flip_1:
            flip_delta += cut1_flip_delta
        if flip_2:
            flip_delta += cut2_flip_delta

        return flip_1, flip_2, flip_delta

    def _cut_flip_delta(self, cut_idx: int) -> float:
        cuts = self.geometry.cuts
        cut_previous = (cut_idx - 1) % len(cuts)
        cut_next = (cut_idx + 1) % len(cuts)

        old_edges_cost = self.get_cost(
            cuts[cut_previous], cuts[cut_idx]
        ) + self.get_cost(cuts[cut_idx], cuts[cut_next])

        new_edges_cost = self.get_cost(
            cuts[cut_previous], cuts[cut_idx].flipped_direction()
        ) + self.get_cost(cuts[cut_idx].flipped_direction(), cuts[cut_next])

        flip_delta = new_edges_cost - old_edges_cost
        if isclose(flip_delta, 0):
            flip_delta = 0

        return flip_delta

    def _get_cost(self, cut1: TrapezoidalCut, cut2: TrapezoidalCut) -> float:
        return cut1.travel_time_to(cut2, self.material_height)

    def _edge_swap_delta(self, cut1_idx: int, cut2_idx: int) -> float:
        # If the indices are the same or one apart, swapping the edges won't change the tour
        if abs(cut1_idx - cut2_idx) <= 1:
            return 0.0

        cuts = self.geometry.cuts
        cut1_next: int = (cut1_idx + 1) % len(cuts)
        cut2_next: int = (cut2_idx + 1) % len(cuts)

        old_edges_cost = self._get_cost(
            cuts[cut1_idx], cuts[cut1_next]
        ) + self._get_cost(cuts[cut2_idx], cuts[cut2_next])

        new_edges_cost = self._get_cost(
            cuts[cut1_idx], cuts[cut2_idx].flipped_direction()
        ) + self._get_cost(cuts[cut1_next].flipped_direction(), cuts[cut2_next])

        swap_delta = new_edges_cost - old_edges_cost
        if isclose(swap_delta, 0):
            swap_delta = 0
        return swap_delta

    def _apply_best_improvement(
        self,
        cut1: int,
        cut2: int,
        two_opt_delta: float,
        flip_delta: float,
        flip_1: bool,
        flip_2: bool,
    ) -> float:
        cuts = self.geometry.cuts
        if two_opt_delta <= flip_delta:
            self._two_opt_swap(cut1, cut2)
            return two_opt_delta
        else:
            if flip_1:
                cuts[cut1] = cuts[cut1].flipped_direction()
            if flip_2:
                cuts[cut2] = cuts[cut2].flipped_direction()
            return flip_delta

    def _two_opt_swap(self, cut1_idx: int, cut2_idx: int):
        # If the indices are the same or one apart, swapping the edges won't change the tour
        if abs(cut1_idx - cut2_idx) <= 1:
            return

        # Set cut1_idx to the smaller index so we don't have to write the swap operation twice
        if cut1_idx > cut2_idx:
            cut1_idx, cut2_idx = cut2_idx, cut1_idx

        cuts = self.geometry.cuts
        i = cut1_idx + 1
        j = cut2_idx
        while i < j:
            cuts[i], cuts[j] = cuts[j].flipped_direction(), cuts[i].flipped_direction()
            i += 1
            j -= 1

    def _tour_to_shortest_path(self):
        longest_incoming_edge_idx = self._find_longest_edge()
        self._left_rotate(longest_incoming_edge_idx)

    def _find_longest_edge(self) -> int:
        cuts = self.geometry.cuts
        number_cuts = len(cuts)
        longest_edge_idx: int = 0
        longest_edge: float = self._get_cost(cuts[-1], cuts[0])
        for i in range(1, number_cuts):
            current_cost = self._get_cost(cuts[i - 1], cuts[i])
            if current_cost < longest_edge:
                longest_edge_idx = i
                longest_edge = current_cost
        return longest_edge_idx

    def _left_rotate(self, i: int):
        cuts = self.geometry.cuts
        cuts = cuts[i:] + cuts[:i]
