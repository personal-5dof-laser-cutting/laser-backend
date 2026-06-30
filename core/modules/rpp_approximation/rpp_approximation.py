from itertools import combinations, product

import networkx as nx

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module
from core.service_container import Container
from core.services.kinematics_service import KinematicsService


class RPPApproximationModule(Module[Geometry, Geometry]):
    def __init__(self, material_height: float) -> None:
        super().__init__()
        self.material_height: float = material_height
        self.kinematics: KinematicsService = Container.kinematics_service

    def process(self, data: Geometry) -> Geometry:
        self.geometry: Geometry = data
        self._build_cache()
        graph: nx.Graph = self._build_graph()
        self._connect_graph_minimally(graph)
        multi_graph: nx.MultiGraph = self._add_mwpm_edges(graph)
        return self._graph_to_geometry(multi_graph)

    def _build_cache(self):
        cuts: list[TrapezoidalCut] = self.geometry.cuts
        configurations: set[Configuration] = {
            config for cut in cuts for config in cut.configurations()
        }
        self.kinematics.generate_cache(list(configurations), self.material_height)

    def _build_graph(self) -> nx.Graph:
        graph: nx.Graph = nx.Graph()
        for cut in self.geometry.cuts:
            start_conf, end_conf = cut.configurations()
            graph.add_edge(
                start_conf,
                end_conf,
                weight=start_conf.travel_time_to(end_conf, self.material_height),
                depth=cut.cut_depth,
                is_cut_move=True,
            )
        return graph

    def _connect_graph_minimally(self, graph: nx.Graph):
        component_graph: nx.Graph | None = self._get_component_graph(graph)
        if component_graph is None:
            return
        for _, _, data in nx.minimum_spanning_edges(
            component_graph, weight="weight", data=True
        ):
            actual_from = data["actual_from"]
            actual_to = data["actual_to"]
            graph.add_edge(
                actual_from, actual_to, weight=data["weight"], is_cut_move=False
            )

    def _get_component_graph(self, graph: nx.Graph) -> nx.Graph | None:
        if nx.is_connected(graph):
            return None
        component_graph = nx.Graph()
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

    def _add_mwpm_edges(self, graph: nx.Graph) -> nx.MultiGraph:
        matching_graph: nx.Graph = nx.Graph()
        odd_nodes = self._get_odd_degree_nodes(graph)
        for u, v in combinations(odd_nodes, 2):
            matching_graph.add_edge(
                u, v, weight=u.travel_time_to(v, self.material_height)
            )
        matching = nx.min_weight_matching(matching_graph, weight="weight")
        multi_graph = nx.MultiGraph(graph)
        for u, v in matching:
            multi_graph.add_edge(
                u,
                v,
                weight=u.travel_time_to(v, self.material_height),
                is_cut_move=False,
            )
        return multi_graph
        # pos = {node: (node.x*2, node.y*2) for node in self.graph.nodes()}
        # nx.draw(self.graph, pos)
        # pos = {node: (node.x*2, node.y*2) for node in debug_graph.nodes()}
        # nx.draw(debug_graph, pos, node_color="#3dd90054", edge_color="red")
        # plt.show()

    def _get_odd_degree_nodes(self, graph: nx.Graph) -> list[Configuration]:
        return [conf for conf, degree in graph.degree() if degree % 2 == 1]

    def _graph_to_geometry(self, graph: nx.MultiGraph) -> Geometry:
        # print("draww")
        # nx.draw(self.graph)
        # plt.show()
        # sleep(60)
        geometry = Geometry()
        for u, v in nx.eulerian_circuit(graph):
            data = graph.get_edge_data(u, v)
            if data and data[0]["is_cut_move"]:
                geometry.add_cut_from_configurations(u, v, data[0]["depth"])
        geometry.shift_path_optimally(self.material_height)
        return geometry
