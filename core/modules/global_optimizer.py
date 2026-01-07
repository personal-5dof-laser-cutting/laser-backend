import numpy as np
from ctypes import ArgumentError
from math import inf

from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module
from core.service_container import Container
from core.services.cost_function_service import CostFunctionService
from core.modules.genetic_gtsp import GTSP, run_gcga


class GlobalOptimizerModule(Module[Geometry, Geometry]):
    def process(
        self,
        data: Geometry,
        cost_function: CostFunctionService = Container.cost_function,
    ) -> Geometry:
        cuts: list[TrapezoidalCut] = data.cuts
        weights, groups = self._generate_weights(data.cuts, cost_function)
        gtsp = GTSP(weights, groups)
        best_chrom, _ = run_gcga(
            gtsp,
            pop_size=100,
            generations=1000,
            crossover_prob=0.9,
            mutation_prob=0.15,
            tournament_k=3,
            elitism=2,
            do_head_reopt=True,
        )
        tour = gtsp.decode(best_chrom)
        trapezoid_path = self._tour_to_path(tour, cuts, cost_function)
        # graph: nx.Graph = nx.Graph()
        # self._build_graph(graph, cuts, cost_function)
        # path = christofides(graph)
        # trapezoid_path = self._path_to_trapezoids(path)
        data.cuts = trapezoid_path

        return data

    def _generate_weights(
        self, cuts: list[TrapezoidalCut], cost_function: CostFunctionService
    ) -> tuple[np.ndarray, list[list[int]]]:
        weights = np.zeros((2 * len(cuts), 2 * len(cuts)))
        groups = []
        for i in range(len(cuts)):
            groups.append([2 * i, 2 * i + 1])
            for k in range(0, i):
                start_config = i * 2
                end_config = start_config + 1
                other_start_config = k * 2
                other_end_config = other_start_config + 1

                weights[start_config, other_start_config] = cost_function.get_cost(
                    cuts[i].end_configuration(), cuts[k].start_configuration()
                )
                weights[start_config, other_end_config] = cost_function.get_cost(
                    cuts[i].end_configuration(), cuts[k].end_configuration()
                )
                weights[end_config, other_start_config] = cost_function.get_cost(
                    cuts[i].start_configuration(), cuts[k].start_configuration()
                )
                weights[end_config, other_end_config] = cost_function.get_cost(
                    cuts[i].start_configuration(), cuts[k].end_configuration()
                )
                weights[other_start_config, start_config] = cost_function.get_cost(
                    cuts[k].end_configuration(), cuts[i].start_configuration()
                )
                weights[other_start_config, end_config] = cost_function.get_cost(
                    cuts[k].end_configuration(), cuts[i].end_configuration()
                )
                weights[other_end_config, start_config] = cost_function.get_cost(
                    cuts[k].start_configuration(), cuts[i].start_configuration()
                )
                weights[other_end_config, end_config] = cost_function.get_cost(
                    cuts[k].start_configuration(), cuts[i].end_configuration()
                )

        return (weights, groups)

    def _tour_to_path(
        self,
        tour: list[int],
        cuts: list[TrapezoidalCut],
        cost_function: CostFunctionService,
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
            dist = cost_function.get_cost(
                cut_list[i].end_configuration(),
                cut_list[(i + 1) % len(cut_list)].start_configuration(),
            )
            if dist > max_dist:
                max_dist = dist
                idx_max = i
        cut_list = cut_list[idx_max + 1 :] + cut_list[: idx_max + 1]
        return cut_list
