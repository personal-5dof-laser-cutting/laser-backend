from itertools import product
from typing import Optional, override
import numpy as np
from ctypes import ArgumentError

from core.models.geometry import Configuration, TrapezoidalCut
from core.modules.base_optimizer import BaseOptimizer
from core.modules.genetic_optimizer.genetic_gtsp import GTSP, run_gcga


class GeneticOptimizerModule(BaseOptimizer):
    def __init__(
        self,
        material_height: float,
        generations: int = 1000,
        start_location: Optional[Configuration] = None,
    ) -> None:
        super().__init__(material_height, start_location)
        self.generations = generations
        self.material_height = material_height

    @override
    def _optimize(self):
        self._set_current_cost(
            self.geometry.calculate_travel_cost(self.material_height, True)
        )
        cuts: list[TrapezoidalCut] = self.geometry.cuts
        weights, groups = self._generate_weights(cuts)
        gtsp = GTSP(weights, groups, self._set_current_cost)
        best_chrom, _ = run_gcga(
            gtsp,
            pop_size=100,
            generations=self.generations,
            crossover_prob=0.9,
            mutation_prob=0.15,
            tournament_k=3,
            elitism=2,
            do_head_reopt=True,
        )
        tour = gtsp.decode(best_chrom)
        trapezoid_path = self._tour_to_path(tour, cuts)
        self.geometry.cuts = trapezoid_path

    @override
    def get_current_cost(self, as_cycle: bool) -> float:
        return self.current_cost

    def _set_current_cost(self, current_cost: float):
        self.current_cost = current_cost

    def _generate_weights(
        self, cuts: list[TrapezoidalCut]
    ) -> tuple[np.ndarray, list[list[int]]]:
        # We use 2 * len(cuts) to accomodate weight for both cut directions
        weights = np.zeros((2 * len(cuts), 2 * len(cuts)))
        groups = []
        for i in range(len(cuts)):
            groups.append([2 * i, 2 * i + 1])
            cut1_configs = cuts[i].configurations()
            for k in range(i):
                cut2_configs = cuts[k].configurations()

                for conf1_offset, conf2_offset in product([0, 1], repeat=2):
                    cut1_weight_idx = 2 * i + conf1_offset
                    cut2_weight_idx = 2 * k + conf2_offset
                    # We use cutX_configs[1-confX_offset] because if we start a cut at start_config, we need the distance of end_config to the other cut and vice versa
                    self._add_weight(
                        weights,
                        cut1_weight_idx,
                        cut2_weight_idx,
                        cut1_configs[1 - conf1_offset],
                        cut2_configs[conf2_offset],
                    )
                    self._add_weight(
                        weights,
                        cut2_weight_idx,
                        cut1_weight_idx,
                        cut2_configs[1 - conf2_offset],
                        cut1_configs[conf1_offset],
                    )

        return (weights, groups)

    def _add_weight(
        self,
        matrix: np.ndarray,
        idx1: int,
        idx2: int,
        config1: Configuration,
        config2: Configuration,
    ):
        matrix[idx1, idx2] = config1.travel_time_to(config2, self.material_height)

    def _tour_to_path(
        self,
        tour: list[int],
        cuts: list[TrapezoidalCut],
    ) -> list[TrapezoidalCut]:
        if len(tour) != len(cuts):
            raise ArgumentError("Every cut has to be included in the tour.")
        cut_list: list[TrapezoidalCut] = []
        for index in tour:
            cut = cuts[index // 2]
            if index % 2 == 0:
                cut_list.append(cut)
            else:
                cut_list.append(cut.flipped_direction())
        max_dist = cut_list[-1].travel_time_to(cut_list[0], self.material_height)
        idx_max = -1
        for i in range(len(cut_list) - 1):
            dist = cut_list[i].travel_time_to(cut_list[i + 1], self.material_height)
            if dist > max_dist:
                max_dist = dist
                idx_max = i
        cut_list = cut_list[idx_max + 1 :] + cut_list[: idx_max + 1]
        return cut_list
