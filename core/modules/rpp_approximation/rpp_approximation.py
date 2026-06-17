from itertools import combinations, product
from typing import Literal, Union

import rustworkx as rx
import networkx as nx
from pydantic import BaseModel

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.modules.base_optimizer import BaseOptimizer
from core.service_container import Container


class CutEdge(BaseModel):
    is_cut_move: Literal[True] = True
    original_edge_index: int


class ComponentEdge(BaseModel):
    is_cut_move: Literal[False] = False
    weight: float
    actual_from_idx: int
    actual_to_idx: int


class HelperEdge(BaseModel):
    is_cut_move: Literal[False] = False
    weight: float


Edge = Union[CutEdge, ComponentEdge, HelperEdge]


class RPPApproximationModule(BaseOptimizer):
    def __init__(self, material_height: float) -> None:
        super().__init__(material_height)

    def get_current_cost(self, as_cycle: bool) -> float:
        return self.geometry.calculate_travel_cost(self.material_height, as_cycle)

    def _optimize(self):
        self.original_cuts: list[TrapezoidalCut] = self.geometry.cuts
        self._build_cache()
        self.configurations: list[Configuration] = list(
            {conf for cut in self.geometry.cuts for conf in cut.configurations()}
        )
        self.trapezoid_graph: rx.PyGraph[Configuration, Edge] = self._build_graph()
        self._connect_graph_minimally(self.trapezoid_graph)
        multi_graph: rx.PyGraph[Configuration, Edge] = self._add_mwpm_edges(
            self.trapezoid_graph
        )
        self.geometry = self._graph_to_geometry(multi_graph)

    def _build_cache(self):
        cuts: list[TrapezoidalCut] = self.geometry.cuts
        configurations: set[Configuration] = {
            config for cut in cuts for config in cut.configurations()
        }
        Container.kinematics_service.generate_cache(
            configurations, self.material_height
        )

    def _get_distance(self, u: int, v: int) -> float:
        return self.trapezoid_graph[u].travel_time_to(
            self.trapezoid_graph[v], self.material_height
        )

    def _build_graph(self) -> rx.PyGraph[Configuration, Edge]:
        graph: rx.PyGraph[Configuration, Edge] = rx.PyGraph(multigraph=False)
        conf_to_idx: dict[Configuration, int] = {}

        for index, cut in enumerate(self.geometry.cuts):
            start_conf, end_conf = cut.configurations()
            if start_conf not in conf_to_idx:
                conf_to_idx[start_conf] = graph.add_node(start_conf)
            if end_conf not in conf_to_idx:
                conf_to_idx[end_conf] = graph.add_node(end_conf)
            graph.add_edge(
                conf_to_idx[start_conf],
                conf_to_idx[end_conf],
                CutEdge(is_cut_move=True, original_edge_index=index),
            )
        return graph

    def _connect_graph_minimally(self, graph: rx.PyGraph[Configuration, Edge]):
        component_graph: rx.PyGraph[int, ComponentEdge] | None = (
            self._get_component_graph(graph)
        )
        if component_graph is None:
            return
        for _, _, data in rx.minimum_spanning_edges(
            component_graph, weight_fn=lambda x: x.weight
        ):
            edge = ComponentEdge.model_validate(data)
            actual_from_idx = edge.actual_from_idx
            actual_to_idx = edge.actual_to_idx
            weight = edge.weight
            graph.add_edge(
                actual_from_idx,
                actual_to_idx,
                HelperEdge(weight=weight, is_cut_move=False),
            )

    def _get_component_graph(
        self, graph: rx.PyGraph[Configuration, Edge]
    ) -> rx.PyGraph[int, ComponentEdge] | None:
        if rx.is_connected(graph):
            return None
        component_graph: rx.PyGraph[int, ComponentEdge] = rx.PyGraph()
        components_of_indices: list[set[int]] = rx.connected_components(graph)
        component_graph.add_nodes_from(range(len(components_of_indices)))
        for component_idx_1, component_idx_2 in combinations(
            component_graph.node_indices(), 2
        ):
            distance, from_conf_idx, to_conf_idx = self._get_component_distance(
                graph,
                components_of_indices[component_idx_1],
                components_of_indices[component_idx_2],
            )
            component_graph.add_edge(
                component_idx_1,
                component_idx_2,
                ComponentEdge(
                    weight=distance,
                    actual_from_idx=from_conf_idx,
                    actual_to_idx=to_conf_idx,
                ),
            )

        return component_graph

    def _get_component_distance(
        self,
        graph: rx.PyGraph[Configuration],
        component_1: set[int],
        component_2: set[int],
    ) -> tuple[float, int, int]:
        min_distance = float("inf")
        from_conf_idx: int = 0
        to_conf_idx: int = 0
        for node_u_idx, node_v_idx in product(component_1, component_2):
            distance = graph[node_u_idx].travel_time_to(
                graph[node_v_idx], self.material_height
            )
            if distance < min_distance:
                min_distance = distance
                from_conf_idx = node_u_idx
                to_conf_idx = node_v_idx
        return min_distance, from_conf_idx, to_conf_idx

    def _add_mwpm_edges(
        self, graph: rx.PyGraph[Configuration, Edge]
    ) -> rx.PyGraph[Configuration, Edge]:
        matching_graph: rx.PyGraph[int, HelperEdge] = rx.PyGraph()
        graph_odd_node_indices: list[int] = self._get_odd_degree_node_indices(graph)
        graph_to_matching_graph_index = {
            n: matching_graph.add_node(n) for n in graph_odd_node_indices
        }
        for u_idx, v_idx in combinations(graph_odd_node_indices, 2):
            distance = graph[u_idx].travel_time_to(graph[v_idx], self.material_height)
            matching_graph.add_edge(
                graph_to_matching_graph_index[u_idx],
                graph_to_matching_graph_index[v_idx],
                HelperEdge(weight=distance),
            )
        min_matching_edges = rx.max_weight_matching(
            matching_graph,
            max_cardinality=True,
            weight_fn=lambda u: int(-u.weight * 1_000_000_000_000),
        )
        multi_graph: rx.PyGraph[Configuration, Edge] = rx.PyGraph(multigraph=True)
        multi_graph.add_nodes_from(graph.nodes())
        multi_graph.add_edges_from(graph.weighted_edge_list())
        for u_idx, v_idx in min_matching_edges:
            conf_u_graph_idx: int = matching_graph[u_idx]
            conf_v_graph_idx: int = matching_graph[v_idx]
            distance = graph[conf_u_graph_idx].travel_time_to(
                graph[conf_v_graph_idx], self.material_height
            )
            multi_graph.add_edge(
                conf_u_graph_idx,
                conf_v_graph_idx,
                HelperEdge(weight=distance, is_cut_move=False),
            )
        return multi_graph

    def _get_odd_degree_node_indices(
        self, graph: rx.PyGraph[Configuration, Edge]
    ) -> list[int]:
        return [
            node_index
            for node_index in graph.node_indices()
            if graph.degree(node_index) % 2 == 1
        ]

    def _graph_to_geometry(self, graph: rx.PyGraph[Configuration, Edge]) -> Geometry:
        geometry = Geometry()

        nx_graph: nx.MultiGraph[Configuration] = nx.MultiGraph()
        for u_idx, v_idx, data in graph.weighted_edge_list():
            nx_graph.add_edge(graph[u_idx], graph[v_idx], **data.model_dump())
        for u, v, key in nx.eulerian_circuit(nx_graph, keys=True):
            data = nx_graph.get_edge_data(u, v)[key]
            if data.get("is_cut_move"):
                edge = CutEdge.model_validate(data)
                original_cut = self.original_cuts[edge.original_edge_index]
                if original_cut.start_configuration == u:
                    geometry.add_cut(original_cut)
                else:
                    geometry.add_cut(original_cut.flipped_direction())
        geometry.shift_path_optimally(self.material_height)
        return geometry
