from itertools import product
import numpy as np
from ctypes import ArgumentError
from math import inf

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module
from core.service_container import Container
from core.services.laser_config_service import LaserConfigService
from core.modules.global_optimizer.genetic_gtsp import GTSP, run_gcga


class GlobalOptimizerModule(Module[Geometry, Geometry]):
    def __init__(self, generations: int = 1000) -> None:
        super().__init__()
        self.generations = generations

    def process(
        self,
        data: Geometry,
        laser_config: LaserConfigService = Container.laser_config,
    ) -> Geometry:
        self.laser_config = laser_config
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
        trapezoid_path = self._tour_to_path(tour, cuts, laser_config)
        data.cuts = trapezoid_path

        return data

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
        laser_config = self.laser_config
        matrix[idx1, idx2] = laser_config.get_cost(config1, config2)

    def _tour_to_path(
        self,
        tour: list[int],
        cuts: list[TrapezoidalCut],
        laser_config: LaserConfigService,
    ) -> list[TrapezoidalCut]:
        if len(tour) != len(cuts):
            raise ArgumentError("Every cut has to be included in the tour.")
        cut_list: list[TrapezoidalCut] = []
        for index in tour:
            cut = cuts[index // 2]
            if index % 2 == 0:
                cut_list.append(cut)
            else:
                cut_list.append(cut.flip_direction())
        max_dist = -inf
        idx_max = 0
        for i in range(len(cut_list)):
            dist = laser_config.get_cost(
                cut_list[i].end_configuration(),
                cut_list[(i + 1) % len(cut_list)].start_configuration(),
            )
            if dist > max_dist:
                max_dist = dist
                idx_max = i
        cut_list = cut_list[idx_max + 1 :] + cut_list[: idx_max + 1]
        return cut_list
