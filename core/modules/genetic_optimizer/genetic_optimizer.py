from itertools import combinations, product
import numpy as np
from ctypes import ArgumentError

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module
from core.service_container import Container
from core.modules.genetic_optimizer.genetic_gtsp import GTSP, run_gcga
from core.services.laser_cost_service import LaserCostService


class GeneticOptimizerModule(Module[Geometry, Geometry]):
    def __init__(
        self,
        material_height: float,
        generations: int = 1000,
        laser_cost: LaserCostService = Container.laser_cost,
    ) -> None:
        super().__init__()
        self.generations = generations
        self.material_height = material_height
        self.get_cost = lambda x, y: laser_cost.get_cost(
            material_height=self.material_height, conf1=x, conf2=y
        )

    def process(self, data: Geometry) -> Geometry:
        cuts: list[TrapezoidalCut] = data.cuts
        weights, groups = self._generate_weights(data.cuts)
        gtsp = GTSP(weights, groups)
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
        data.cuts = trapezoid_path

        return data

    def _generate_weights(
        self, cuts: list[TrapezoidalCut]
    ) -> tuple[np.ndarray, list[list[int]]]:
        # We use 2 * len(cuts) to accomodate weight for both cut directions
        weights = np.zeros((2 * len(cuts), 2 * len(cuts)))
        groups = [[2 * i, 2 * i + 1] for i in range(len(cuts))]

        def get_config(cut_idx: int, return_start: bool) -> Configuration:
            if return_start:
                return cuts[cut_idx].start_configuration()
            return cuts[cut_idx].end_configuration()

        def add_weight(cut1: int, cut2: int, flip1: bool, flip2: bool):
            weights[2 * cut1 + flip1, 2 * cut2 + flip2] = get_config(
                cut1, flip1
            ).travel_time_to(get_config(cut2, not flip2), self.material_height)

        for i, k in combinations(range(len(cuts)), 2):
            for flip1, flip2 in product([False, True], repeat=2):
                add_weight(i, k, flip1, flip2)
                add_weight(k, i, flip1, flip2)
        return (weights, groups)

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
