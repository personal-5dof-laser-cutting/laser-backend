from itertools import combinations
import logging
from math import inf, isclose
from typing import Optional, override

from matplotlib import pyplot as plt

from core.modules.base_optimizer import BaseOptimizer
from core.models.geometry import Configuration, TrapezoidalCut

log = logging.getLogger("Groptimizer")


class GreedyOptimizerModule(BaseOptimizer):
    max_iterations: int
    show_statistics: bool

    def __init__(
        self,
        material_height: float,
        start_location: Optional[Configuration] = None,
        max_iterations: int = 10,
        show_statistics: bool = False,
    ):
        super().__init__(material_height, start_location)
        self.max_iterations = max_iterations
        self.show_statistics = show_statistics

    @override
    def _optimize(self):
        if self.show_statistics:
            self._create_plot()
            self._append_stats("Original")
        self._best_first()
        self._two_opt()
        if self.show_statistics:
            self._append_stats("Cycle to Path", False)
        if self.show_statistics:
            plt.ioff()
            plt.show()

    @override
    def get_current_cost(self, as_cycle: bool) -> float:
        return self.geometry.calculate_travel_cost(self.material_height, as_cycle)

    def _best_first(self):
        cuts = self.geometry.cuts
        for i in range(1, len(cuts) - 1):
            next_cut, flip_cut = self._find_closest_cut(
                cuts[i - 1].end_configuration, i
            )

            if flip_cut:
                cuts[next_cut].flip_direction()

            cuts[i], cuts[next_cut] = (
                cuts[next_cut],
                cuts[i],
            )

        if self.show_statistics:
            self._append_stats("Best First")

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
                cuts[i].start_configuration, self.material_height
            )
            if current_cost < closest_cost:
                closest_cost = current_cost
                closest_cut = i
                flip_cut = False

            current_flipped_cost = start_conf.travel_time_to(
                cuts[i].end_configuration, self.material_height
            )
            if current_flipped_cost < closest_cost:
                closest_cost = current_flipped_cost
                closest_cut = i
                flip_cut = True
            if isclose(closest_cost, 0):
                break
        return closest_cut, flip_cut

    def _two_opt(self):
        cuts = self.geometry.cuts
        found_improvement: bool = True
        iterations: int = 0
        previous_cost: float = self.geometry.calculate_travel_cost(
            self.material_height, True
        )
        improvement: float = 0.0
        cut_indices = list(range(len(cuts)))
        improvable_cut_indices = filter(
            lambda idx: (
                cuts[idx - 1].travel_time_to(cuts[idx], self.material_height) != 0
                or cuts[idx].travel_time_to(
                    cuts[(idx + 1) % len(cuts)], self.material_height
                )
                != 0
            ),
            cut_indices,
        )
        while (
            found_improvement and iterations < self.max_iterations and previous_cost > 0
        ):
            found_improvement = False
            for cut1, cut2 in combinations(improvable_cut_indices, 2):
                if abs(cut1 - cut2) <= 1:
                    continue
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
            if self.show_statistics:
                self._append_stats(f"Two Opt It. {iterations}")
            improvement_ratio = -improvement / previous_cost
            if self.show_statistics:
                log.info(f"Improved by {improvement_ratio:.2%}")
            if improvement_ratio <= 0.05:
                if self.show_statistics:
                    log.info("\tImprovement too low, ending")
                break
            previous_cost += improvement
            improvement = 0

    def _calculate_flip_improvement(
        self, cut1: int, cut2: int
    ) -> tuple[bool, bool, float]:
        flip_delta: float = 0.0

        cut1_flip_delta = self._cut_flip_delta(cut1)
        flip_1: bool = cut1_flip_delta < 0
        if flip_1:
            flip_delta += cut1_flip_delta

        if cut2 == cut1:
            # If they are equal, flip_2 should be False so an algorithm won't flip the cut twice if flip_1 == True
            return flip_1, False, flip_delta

        cut2_flip_delta = self._cut_flip_delta(cut2)
        flip_2: bool = cut2_flip_delta < 0
        if flip_2:
            flip_delta += cut2_flip_delta

        if abs(cut2 - cut1) == 1 and flip_1 and flip_2:
            # Since the cuts are subsequent, adding the flip deltas seperately counts some travel moves twice, some unneccesarily and doesn't count others
            cuts = self.geometry.cuts
            direct_move_cost = self._get_cost(cuts[cut1], cuts[cut2])  # counted twice
            flip_1_direct_move_cost = self._get_cost(
                cuts[cut1], cuts[cut2], flip1=True
            )  # counted unnecessarily
            flip_2_direct_move_cost = self._get_cost(
                cuts[cut1], cuts[cut2], flip2=True
            )  # counted unnecessarily
            flip_both_direct_move_cost = self._get_cost(
                cuts[cut1], cuts[cut2], True, True
            )  # didn't count
            inaccuracy = (
                direct_move_cost
                + flip_both_direct_move_cost
                - flip_1_direct_move_cost
                - flip_2_direct_move_cost
            )

            fixed_delta = flip_delta + inaccuracy
            if fixed_delta < min(cut1_flip_delta, cut2_flip_delta):
                return True, True, fixed_delta
            elif cut1_flip_delta < cut2_flip_delta:
                return True, False, cut1_flip_delta
            else:
                return False, True, cut2_flip_delta

        return flip_1, flip_2, flip_delta

    def _cut_flip_delta(self, cut_idx: int) -> float:
        segment_cost = self._segment_cost(cut_idx, flipped=False)

        flipped_cost = self._segment_cost(cut_idx, flipped=True)

        flip_delta = flipped_cost - segment_cost
        if isclose(flip_delta, 0):
            flip_delta = 0

        return flip_delta

    def _get_cost(
        self,
        cut1: TrapezoidalCut,
        cut2: TrapezoidalCut,
        flip1: bool = False,
        flip2: bool = False,
    ) -> float:
        from_conf = cut1.start_configuration if flip1 else cut1.end_configuration
        to_conf = cut2.end_configuration if flip2 else cut2.start_configuration
        return from_conf.travel_time_to(to_conf, self.material_height)

    def _segment_cost(self, cut_idx: int, flipped: bool = False) -> float:
        cuts = self.geometry.cuts
        cut = cuts[cut_idx]
        cut_previous = cuts[(cut_idx - 1) % len(cuts)]
        cut_next = cuts[(cut_idx + 1) % len(cuts)]

        edges_cost = self._get_cost(cut_previous, cut, flip2=flipped) + self._get_cost(
            cut, cut_next, flip1=flipped
        )

        if isclose(edges_cost, 0):
            edges_cost = 0

        return edges_cost

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
            cuts[cut1_idx], cuts[cut2_idx], flip2=True
        ) + self._get_cost(cuts[cut1_next], cuts[cut2_next], flip1=True)

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
                cuts[cut1].flip_direction()
            if flip_2:
                cuts[cut2].flip_direction()
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
        if i == j:
            cuts[i].flip_direction()

    def _create_plot(self):
        self.fig, self.ax = plt.subplots()
        self._setup_plot()
        plt.ion()
        self.steps: list[str] = []
        self.results: list[float] = []
        self.cut_cost = self.geometry.calculate_cut_cost(self.material_height, 600)

    def _setup_plot(self):
        self.ax.set_xlabel("Step")
        self.ax.set_ylabel("Path cost (minutes)")
        self.ax.set_title("Path Cost Evolution over Time")

    def _append_stats(self, step_name: str, as_cycle: bool = True):
        self.steps.append(step_name)
        current_cost = self.geometry.calculate_travel_cost(
            self.material_height, as_cycle=as_cycle
        )
        self.results.append(current_cost)

        self.ax.clear()
        self.ax.bar(
            self.steps,
            [self.cut_cost + result for result in self.results],
            color="blue",
        )
        self.ax.bar(self.steps, [self.cut_cost] * len(self.steps), color="red")
        self._setup_plot()
        plt.pause(0.1)
