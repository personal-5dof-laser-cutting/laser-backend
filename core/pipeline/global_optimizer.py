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
        for cut in cuts:
            for neighbour in cuts:
                self._generate_edges(graph, cut, neighbour, cost_function)

        path = christofides(graph)
        self._path_to_trapezoids(path)
        data.cuts = path
        return data

    def _generate_edges(
        self,
        graph: nx.Graph,
        cut1: TrapezoidalCut,
        cut2: TrapezoidalCut,
        cost_function: CostFunctionService,
    ):
        if cut1 is cut2:
            graph.add_edge(cut1.start_configuration(), cut1, weight=0)
            graph.add_edge(cut1.end_configuration(), cut1, weight=0)
        else:
            for cut_config in [cut1.start_configuration(), cut1.end_configuration()]:
                for neighbur_config in [
                    cut2.start_configuration(),
                    cut2.end_configuration(),
                ]:
                    dist = cost_function.get_cost(cut_config, neighbur_config)
                    graph.add_edge(cut_config, neighbur_config, weight=dist)
                    graph.add_edge(cut_config, cut2, weight=inf)
                    graph.add_edge(neighbur_config, cut1, weight=inf)

    def _path_to_trapezoids(self, path: list[TrapezoidalCut | Configuration]):
        path = path[:-1]
        assert len(path) % 3 == 0
        if isinstance(path[0], TrapezoidalCut):
            path.insert(
                0, path.pop()
            )  # shift path to the right so it starts with a configuration node
        elif isinstance(path[2], TrapezoidalCut):
            path.append(
                path.pop(0)
            )  # shift path to the left if the path order isn't Config -> Cut -> Config

        for i in range(len(path)):
            if i % 3 == 1:
                assert isinstance(path[i], TrapezoidalCut)
            else:
                assert isinstance(path[i], Configuration)
        assert isinstance(path[0], Configuration)

        cut_list: list[TrapezoidalCut] = []
        for i in range(0, len(path), 3):
            start_config = path[i]
            end_config = path[i + 2]
            cut = path[i + 1]
            assert isinstance(start_config, Configuration)
            assert isinstance(end_config, Configuration)
            assert isinstance(cut, TrapezoidalCut)
            cut_list.append(
                TrapezoidalCut.from_configurations(
                    start_config, end_config, cut.cut_depth
                )
            )
        return cut_list
