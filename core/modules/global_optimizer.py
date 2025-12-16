from ctypes import ArgumentError
from math import inf

import networkx as nx
import numpy as np

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
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
        trapezoid_path = self._tour_to_path(tour, cuts)
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

    def _tour_to_path(self, tour: list[int], cuts: list[TrapezoidalCut]):
        if len(tour) != len(cuts):
            raise ArgumentError("Every cut has to be included in the tour.")
        cut_list = []
        for index in tour:
            cut = cuts[index // 2]
            if index % 2 != 0:
                cut_list.append(cut)
            else:
                cut_list.append(cut.flip_direction())
        return cut_list

    def _snap_cuts(
        self,
        base_configs: list[Configuration] | Configuration,
        potential_configs: list[Configuration] | Configuration,
        other_cut: TrapezoidalCut,
    ):
        if isinstance(base_configs, Configuration):
            base_configs = [base_configs]
        if isinstance(potential_configs, Configuration):
            potential_configs = [potential_configs]
        for base_config in base_configs:
            for potential_config in potential_configs:
                if base_config == potential_config:
                    potential_config = base_config
                    if potential_config == other_cut.start_configuration():
                        other_cut = TrapezoidalCut.from_configurations(
                            base_config,
                            other_cut.end_configuration(),
                            other_cut.cut_depth,
                        )
                    elif potential_config == other_cut.end_configuration():
                        other_cut = TrapezoidalCut.from_configurations(
                            other_cut.start_configuration(),
                            base_config,
                            other_cut.cut_depth,
                        )
                    else:
                        raise ArgumentError(
                            "The potential configurations must be part of the TrapezoidalCut"
                        )

    def _min_dist(
        self,
        from_cuts: list[Configuration],
        to_cuts: list[Configuration],
        cost_function: CostFunctionService,
    ):
        min_dist = inf
        for from_config in from_cuts:
            for to_config in to_cuts:
                if from_config != to_config:
                    current_dist = cost_function.get_cost(from_config, to_config)
                    if current_dist < min_dist:
                        min_dist = current_dist
        return min_dist

    def _build_graph(
        self,
        graph: nx.Graph,
        cuts: list[TrapezoidalCut],
        cost_function: CostFunctionService,
    ):
        for i in range(len(cuts)):
            cut1 = cuts[i]
            graph.add_edge(
                cut1.start_configuration(),
                cut1.end_configuration(),
                weight=cost_function.get_cost(
                    cut1.start_configuration(), cut1.end_configuration()
                ),
            )
            graph.add_edge(cut1.start_configuration(), cut1, weight=0)
            graph.add_edge(cut1.end_configuration(), cut1, weight=0)
            for k in range(i + 1, len(cuts)):
                cut2 = cuts[k]
                if cut1 is cut2:
                    cut2 = cut1
                    continue
                graph.add_edge(
                    cut1,
                    cut2,
                    weight=self._min_dist(
                        cut1.configurations(), cut2.configurations(), cost_function
                    ),
                )

                for cut_config in cut1.configurations():
                    if cut_config in cut2.configurations():
                        self._snap_cuts(cut_config, cut2.configurations(), cut2)
                        continue
                    graph.add_edge(
                        cut_config,
                        cut2,
                        weight=self._min_dist(
                            [cut_config], cut2.configurations(), cost_function
                        ),
                    )

                    for neighbour_config in cut2.configurations():
                        if neighbour_config in cut1.configurations():
                            self._snap_cuts(
                                cut1.configurations(), neighbour_config, cut2
                            )
                            continue
                        graph.add_edge(cut1, neighbour_config)
                        if not graph.has_edge(cut_config, neighbour_config):
                            dist = cost_function.get_cost(cut_config, neighbour_config)
                            graph.add_edge(cut_config, neighbour_config, weight=dist)

    def _path_to_trapezoids(
        self, path: list[TrapezoidalCut | Configuration]
    ) -> list[TrapezoidalCut]:
        if len(path) == 0:
            return []
        if len(path) == 1:
            if not isinstance(path[1], TrapezoidalCut):
                raise TypeError(
                    "A path consisting of only one element has to be a TrapezoidalCut"
                )
            return [path[1]]
        if path[0] != path[-1]:
            raise ValueError("A path has to be a Hamilton Cycle")
        path.pop()
        if not isinstance(path[1], TrapezoidalCut):
            if isinstance(path[2], TrapezoidalCut):
                path.append(path.pop(0))  # left shift
            elif isinstance(path[0], TrapezoidalCut):
                path.insert(0, path.pop())  # right shift
            else:
                raise TypeError(
                    "A path can't have more than two Configuration objects in a row"
                )
        if not isinstance(path[0], Configuration):
            raise TypeError("A path has to start at a Configuration")
        cut_list = []
        for i in range(1, len(path)):
            current = path[i]
            if isinstance(current, TrapezoidalCut):
                start_config = path[i - 1]
                end_config = path[(i + 1) % len(path)]
                if not isinstance(start_config, Configuration) or not isinstance(
                    end_config, Configuration
                ):
                    raise TypeError(
                        "A TrapezoidalCut has to be surrounded by Configuration objects"
                    )
                if {start_config, end_config} != {
                    current.start_configuration(),
                    current.end_configuration(),
                }:
                    raise ValueError(
                        "A TrapezoidalCut has to be surrounded by its start and end configuration "
                    )
                cut_list.append(
                    TrapezoidalCut.from_configurations(
                        start_config, end_config, current.cut_depth
                    )
                )

        return cut_list
