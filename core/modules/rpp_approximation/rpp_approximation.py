from itertools import combinations, product
from typing import Literal

import networkx as nx
from pydantic import BaseModel

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.modules.base_optimizer import BaseOptimizer
from core.service_container import Container


class CutEdgeData(BaseModel):
    is_cut_move: Literal[True] = True
    original_edge_index: int


class RPPApproximationModule(BaseOptimizer):
    def __init__(self, material_height: float) -> None:
        super().__init__(material_height)

    def get_current_cost(self, as_cycle: bool) -> float:
        return self.geometry.calculate_travel_cost(self.material_height, as_cycle)

    def _optimize(self):
        self.original_cuts: list[TrapezoidalCut] = self.geometry.cuts
        self._build_cache()
        graph: nx.Graph[Configuration] = self._build_graph()
        self._connect_graph_minimally(graph)
        multi_graph: nx.MultiGraph = self._add_mwpm_edges(graph)
        self.geometry = self._graph_to_geometry(multi_graph)

    def _build_cache(self):
        cuts: list[TrapezoidalCut] = self.geometry.cuts
        configurations: set[Configuration] = {
            config for cut in cuts for config in cut.configurations()
        }
        Container.kinematics_service.generate_cache(
            configurations, self.material_height
        )

    def _build_graph(self) -> nx.Graph[Configuration]:
        graph: nx.Graph[Configuration] = nx.Graph()
        for index, cut in enumerate(self.geometry.cuts):
            start_conf, end_conf = cut.configurations()
            graph.add_edge(
                start_conf, end_conf, is_cut_move=True, original_edge_index=index
            )
        return graph

    def _connect_graph_minimally(self, graph: nx.Graph[Configuration]):
        component_graph: nx.Graph[int] | None = self._get_component_graph(graph)
        if component_graph is None:
            return
        for _, _, data in nx.minimum_spanning_edges(
            component_graph, weight="weight", data=True
        ):
            actual_from = data["actual_from"]
            actual_to = data["actual_to"]
            weight = data["weight"]
            graph.add_edge(actual_from, actual_to, weight=weight, is_cut_move=False)

    def _get_component_graph(
        self, graph: nx.Graph[Configuration]
    ) -> nx.Graph[int] | None:
        if nx.is_connected(graph):
            return None
        component_graph: nx.Graph[int] = nx.Graph()
        self.components: list[set[Configuration]] = [
            component for component in nx.connected_components(graph)
        ]
        for component_idx_1, component_idx_2 in combinations(
            range(len(self.components)), 2
        ):
            distance, from_conf, to_conf = self._get_component_distance(
                self.components[component_idx_1], self.components[component_idx_2]
            )
            component_graph.add_edge(
                component_idx_1,
                component_idx_2,
                weight=distance,
                actual_from=from_conf,
                actual_to=to_conf,
            )

        return component_graph

    def _get_component_distance(
        self, component_1: set[Configuration], component_2: set[Configuration]
    ) -> tuple[float, Configuration, Configuration]:
        min_distance = float("inf")
        from_conf: Configuration = Configuration(0, 0, 0, 0)
        to_conf: Configuration = Configuration(0, 0, 0, 0)
        for conf_a, conf_b in product(component_1, component_2):
            distance = conf_a.travel_time_to(conf_b, self.material_height)
            if distance < min_distance:
                min_distance = distance
                from_conf = conf_a
                to_conf = conf_b
        return min_distance, from_conf, to_conf

    def _add_mwpm_edges(
        self, graph: nx.Graph[Configuration]
    ) -> nx.MultiGraph[Configuration]:
        matching_graph: nx.Graph[Configuration] = nx.Graph()
        odd_nodes = self._get_odd_degree_nodes(graph)
        for u, v in combinations(odd_nodes, 2):
            matching_graph.add_edge(
                u, v, weight=u.travel_time_to(v, self.material_height)
            )
        matching = nx.min_weight_matching(matching_graph, weight="weight")
        multi_graph: nx.MultiGraph[Configuration] = nx.MultiGraph(graph)
        for u, v in matching:
            weight = matching_graph.get_edge_data(u, v)["weight"]
            multi_graph.add_edge(
                u,
                v,
                weight=weight,
                is_cut_move=False,
            )
        return multi_graph

    def _get_odd_degree_nodes(
        self, graph: nx.Graph[Configuration]
    ) -> list[Configuration]:
        return [conf for conf, degree in graph.degree() if degree % 2 == 1]

    def _graph_to_geometry(self, graph: nx.MultiGraph) -> Geometry:
        geometry = Geometry()
        for u, v, key in nx.eulerian_circuit(graph, keys=True):
            data = graph.get_edge_data(u, v)[key]
            if data.get("is_cut_move"):
                edge = CutEdgeData.model_validate(data)
                geometry.add_cut(self.original_cuts[edge.original_edge_index])
        geometry.shift_path_optimally(self.material_height)
        return geometry
