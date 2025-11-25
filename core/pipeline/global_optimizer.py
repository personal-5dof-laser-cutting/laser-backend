from math import inf

import networkx as nx
from dependency_injector.wiring import Provide, inject
from networkx.algorithms.approximation import christofides

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module
from core.service_container import Container
from core.services.cost_function_service import CostFunctionService


class GlobalOptimizerModule(Module[Geometry, Geometry]):
    @inject
    def process(
        self,
        data: Geometry,
        cost_function: CostFunctionService = Provide[Container.cost_function],
    ) -> Geometry:
        graph: nx.Graph = nx.Graph()
        cuts: list[TrapezoidalCut] = data.cuts
        self._build_graph(graph, cuts, cost_function)

        path = christofides(graph)
        trapezoid_path = self._path_to_trapezoids(path)
        data.cuts = trapezoid_path

        return data

    def _build_graph(
        self,
        graph: nx.Graph,
        cuts: list[TrapezoidalCut],
        cost_function: CostFunctionService,
    ):
        for cut1 in cuts:
            graph.add_edge(
                cut1.start_configuration(), cut1.end_configuration(), weight=inf
            )
            graph.add_edge(cut1.start_configuration(), cut1, weight=0)
            graph.add_edge(cut1.end_configuration(), cut1, weight=0)
            for cut2 in cuts:
                if cut1 is cut2:
                    continue
                graph.add_edge(cut1, cut2, weight=inf)

                for cut_config in [
                    cut1.start_configuration(),
                    cut1.end_configuration(),
                ]:
                    if cut_config in [
                        cut2.start_configuration(),
                        cut2.end_configuration(),
                    ]:
                        continue
                    graph.add_edge(cut_config, cut2, weight=inf)

                    for neighbour_config in [
                        cut2.start_configuration(),
                        cut2.end_configuration(),
                    ]:
                        if neighbour_config in [
                            cut1.start_configuration(),
                            cut2.start_configuration(),
                        ]:
                            continue
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
