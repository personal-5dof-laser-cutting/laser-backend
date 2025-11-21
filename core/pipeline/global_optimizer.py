from dependency_injector.wiring import inject, Provide
import networkx as nx
from networkx.algorithms.approximation import christofides
from math import inf

from core.service_container import Container
from core.pipeline.base import Module
from core.services.cost_function_service import CostFunctionService
from core.models.geometry import Geometry, TrapezoidalCut, Configuration


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
        path = self._path_to_trapezoids(path)
        data.cuts = path
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

    def _path_to_trapezoids(self, path: list[TrapezoidalCut | Configuration]):
        path = path[:-1]
        while not isinstance(path[0], TrapezoidalCut):
            path.insert(0, path.pop())
        assert isinstance(path[1], Configuration)
        for i in range(2, len(path) - 1):
            if isinstance(path[i], TrapezoidalCut):
                assert isinstance(path[i - 1], Configuration)
                assert isinstance(path[i + 1], Configuration)

        cut_list = [cut for cut in path if isinstance(cut, TrapezoidalCut)]
        return cut_list
