from itertools import combinations, pairwise, product
from math import ceil
from typing import Literal, TypeGuard

import rustworkx as rx
import networkx as nx
from pydantic import BaseModel

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.modules.base_optimizer import BaseOptimizer


class CutEdge(BaseModel):
    is_cut_move: Literal[True] = True
    original_cut_index: int


class ComponentEdge(BaseModel):
    weight: float
    actual_from_idx: int
    actual_to_idx: int


class MSTEdge(BaseModel):
    is_cut_move: Literal[False] = False


class HelperEdge(BaseModel):
    is_cut_move: Literal[False] = False
    weight: float


def is_cut_move(edge: Edge) -> TypeGuard[CutEdge]:
    return edge.is_cut_move


Edge = CutEdge | MSTEdge | HelperEdge


class RPPApproximationModule(BaseOptimizer):
    def __init__(self, material_height: float) -> None:
        super().__init__(material_height)

    def get_current_cost(self, as_cycle: bool) -> float:
        return self.geometry.calculate_travel_cost(self.material_height, as_cycle)

    def _optimize(self):
        self.original_cuts: list[TrapezoidalCut] = self.geometry.cuts
        trapezoid_graph: rx.PyGraph[Configuration, Edge] = self._build_graph()
        walk: list[tuple[int, int, int]] = self._rpp_solver(trapezoid_graph)
        self.geometry = self._walk_to_geometry(trapezoid_graph, walk)

    def _build_graph(self) -> rx.PyGraph[Configuration, Edge]:
        graph: rx.PyGraph[Configuration, Edge] = rx.PyGraph(multigraph=True)
        conf_to_idx: dict[Configuration, int] = {}
        edges: list[tuple[int, int, Edge]] = []

        for index, cut in enumerate(self.geometry.cuts):
            start_conf, end_conf = cut.configurations()
            if start_conf not in conf_to_idx:
                conf_to_idx[start_conf] = graph.add_node(start_conf)
            if end_conf not in conf_to_idx:
                conf_to_idx[end_conf] = graph.add_node(end_conf)
            u, v = conf_to_idx[start_conf], conf_to_idx[end_conf]
            if not graph.has_edge(u, v):
                edges.append(
                    (u, v, CutEdge(is_cut_move=True, original_cut_index=index))
                )

        graph.add_edges_from(edges)
        return graph

    def _rpp_solver(
        self, graph: rx.PyGraph[Configuration, Edge]
    ) -> list[tuple[int, int, int]]:
        assert graph.multigraph
        if not rx.is_connected(graph):
            self._connect_graph_minimally(graph)
        self._make_graph_eulerian(graph)
        walk: list[tuple[int, int, int]] = self._eulerian_circuit(graph)
        return walk

    def _connect_graph_minimally(self, graph: rx.PyGraph[Configuration, Edge]):
        component_graph: rx.PyGraph[int, ComponentEdge] = self._get_component_graph(
            graph
        )
        for _, _, data in rx.minimum_spanning_edges(
            component_graph, weight_fn=lambda x: x.weight
        ):
            edge = ComponentEdge.model_validate(data)
            actual_from_idx = edge.actual_from_idx
            actual_to_idx = edge.actual_to_idx
            graph.add_edge(
                actual_from_idx,
                actual_to_idx,
                MSTEdge(is_cut_move=False),
            )

    def _get_component_graph(
        self, graph: rx.PyGraph[Configuration, Edge]
    ) -> rx.PyGraph[int, ComponentEdge]:
        component_graph: rx.PyGraph[int, ComponentEdge] = rx.PyGraph()
        components_by_node_indices: list[set[int]] = rx.connected_components(graph)
        component_graph.add_nodes_from(range(len(components_by_node_indices)))
        for component_idx_1, component_idx_2 in combinations(
            component_graph.node_indices(), 2
        ):
            distance, from_conf_idx, to_conf_idx = self._get_component_distance(
                graph,
                components_by_node_indices[component_idx_1],
                components_by_node_indices[component_idx_2],
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
        graph: rx.PyGraph[Configuration, Edge],
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

    def _make_graph_eulerian(self, graph: rx.PyGraph[Configuration, Edge]):
        assert graph.multigraph
        odd_node_indices: list[int] = self._get_odd_degree_node_indices(graph)
        assert len(odd_node_indices) % 2 == 0
        if len(odd_node_indices) == 0:
            return

        odd_indices_graph: rx.PyGraph[int, HelperEdge] = rx.PyGraph()
        odd_idx_to_odd_graph_idx = {
            idx: odd_indices_graph.add_node(idx) for idx in odd_node_indices
        }
        weights: list[float] = []
        for u_idx, v_idx in combinations(odd_node_indices, 2):
            distance = graph[u_idx].travel_time_to(graph[v_idx], self.material_height)
            weights.append(distance)
            odd_indices_graph.add_edge(
                odd_idx_to_odd_graph_idx[u_idx],
                odd_idx_to_odd_graph_idx[v_idx],
                HelperEdge(weight=distance),
            )
        weights.sort()
        max_weight = weights[-1]
        min_diff = min(w2 - w1 for w1, w2 in pairwise(weights) if w2 - w1 != 0)
        scale = ceil(1 / min_diff)
        min_matching_edges = rx.max_weight_matching(
            odd_indices_graph,
            max_cardinality=True,
            weight_fn=lambda u: int((max_weight - u.weight) * scale),
        )
        for u_odd_graph_idx, v_odd_graph_idx in min_matching_edges:
            u_graph_idx: int = odd_indices_graph[u_odd_graph_idx]
            v_graph_idx: int = odd_indices_graph[v_odd_graph_idx]
            distance = odd_indices_graph.get_edge_data(
                u_odd_graph_idx, v_odd_graph_idx
            ).weight
            graph.add_edge(
                u_graph_idx, v_graph_idx, HelperEdge(weight=distance, is_cut_move=False)
            )

        assert len(self._get_odd_degree_node_indices(graph)) == 0

    def _get_odd_degree_node_indices(
        self, graph: rx.PyGraph[Configuration, Edge]
    ) -> list[int]:
        return [
            node_index
            for node_index in graph.node_indices()
            if graph.degree(node_index) % 2 == 1
        ]

    def _eulerian_circuit(
        self, graph: rx.PyGraph[Configuration, Edge]
    ) -> list[tuple[int, int, int]]:
        nx_graph = nx.MultiGraph()
        nx_graph.add_edges_from(graph.edge_list())
        circuit: list[tuple[int, int, int]] = []
        for u_idx, v_idx, key in nx.eulerian_circuit(nx_graph, keys=True):
            circuit.append((u_idx, v_idx, key))
        return circuit

    def _walk_to_geometry(
        self, graph: rx.PyGraph[Configuration, Edge], walk: list[tuple[int, int, int]]
    ) -> Geometry:
        geometry = Geometry()
        for u_idx, v_idx, key in walk:
            edge = graph.get_all_edge_data(u_idx, v_idx)[key]
            if is_cut_move(edge):
                original_cut: TrapezoidalCut = self.geometry.cuts[
                    edge.original_cut_index
                ]
                if original_cut.start_configuration == graph[u_idx]:
                    geometry.add_cut(original_cut)
                else:
                    geometry.add_cut(original_cut.flipped_direction())

        return geometry
