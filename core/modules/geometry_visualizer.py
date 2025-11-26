from vpython import scene, quad, curve, vertex, color, arrow, vector, text, cross

from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module
import math


class GeometryVisualizerModule(Module[Geometry, Geometry]):
    def process(self, data: Geometry) -> Geometry:
        scene.title = "Debug view"
        scene.range = 10
        scene.background = color.gray(0.8)
        scene.width = 1200
        scene.height = 800

        arrow_width = 0.1
        top_color = color.yellow
        bottom_color = color.red

        for i, cut in enumerate(data.cuts):
            cut_vectors = [
                vector(point.x, point.z, point.y)
                for point in [
                    cut.start_bottom,
                    cut.end_bottom,
                    cut.end_top,
                    cut.start_top,
                ]
            ]

            cut_vectors = {
                k: v
                for k, v in zip(
                    ["start_bottom", "end_bottom", "end_top", "start_top"], cut_vectors
                )
            }

            normal_vector = cross(
                cut_vectors["end_top"] - cut_vectors["start_top"],
                cut_vectors["start_bottom"] - cut_vectors["start_top"],
            )
            if (
                math.isclose(normal_vector.x, 0)
                + math.isclose(normal_vector.y, 0)
                + math.isclose(normal_vector.z, 0)
            ) > 1:
                quad(
                    vs=[
                        vertex(pos=vec, color=color.orange)
                        for vec in cut_vectors.values()
                    ],
                    opacity=1,
                    retain=1,
                )
            else:
                quad(
                    v0=vertex(pos=cut_vectors["start_bottom"], color=bottom_color),
                    v1=vertex(pos=cut_vectors["end_bottom"], color=bottom_color),
                    v2=vertex(pos=cut_vectors["end_top"], color=top_color),
                    v3=vertex(pos=cut_vectors["start_top"], color=top_color),
                    opacity=1,
                    retain=1,
                )

            self._add_cut_rank(cut_vectors, i + 1, arrow_width / 2)
            self._add_cut_direction(cut_vectors, arrow_width)

            if (
                i > 0
                and data.cuts[i - 1].end_configuration()
                != data.cuts[i].start_configuration()
            ):
                self._add_travel_move(data.cuts[i - 1], data.cuts[i], arrow_width)

            outline_points = list(cut_vectors.values())
            outline_points.append(outline_points[0])
            curve(pos=outline_points, color=color.black, radius=0.03)

        print("hihi")
        return data

    def _write_text(
        self,
        pos: vector,
        content: str,
        up: vector,
        text_height: float,
        text_color: vector = color.black,
    ):
        text(
            text=content,
            pos=pos,
            up=up,
            height=text_height,
            color=text_color,
            align="center",
            billboard=False,
        )

    def _add_cut_rank(
        self, cut_vector: dict[str, vector], rank: int, height_offset: float
    ):
        top_text_height = (cut_vector["end_top"] - cut_vector["start_top"]).mag * 0.3
        top_pos = (cut_vector["start_top"] + cut_vector["end_top"]) / 2
        top_pos.y = height_offset
        top_pos.z += top_text_height / 2
        top_up_vector = vector(0, 0, -1)

        bottom_text_height = (
            cut_vector["end_bottom"] - cut_vector["start_bottom"]
        ).mag * 0.3
        bottom_pos = (cut_vector["start_bottom"] + cut_vector["end_bottom"]) / 2
        bottom_pos.y = cut_vector["start_bottom"].y - height_offset
        bottom_pos.z -= bottom_text_height / 2
        bottom_up_vector = vector(0, 0, 1)
        self._write_text(top_pos, str(rank), top_up_vector, top_text_height)
        self._write_text(bottom_pos, str(rank), bottom_up_vector, bottom_text_height)

    def _add_cut_direction(self, cut_vectors: dict[str, vector], arrow_width: float):
        arrow(
            pos=cut_vectors["start_top"],
            axis=(cut_vectors["end_top"] - cut_vectors["start_top"]),
            shaftwidth=arrow_width,
            headlength=2 * arrow_width,
            color=color.red,
        )
        arrow(
            pos=cut_vectors["start_bottom"],
            axis=(cut_vectors["end_bottom"] - cut_vectors["start_bottom"]),
            shaftwidth=arrow_width,
            color=color.red,
        )

    def _add_travel_move(
        self, from_cut: TrapezoidalCut, to_cut: TrapezoidalCut, arrow_width: float
    ):
        from_vector_top = vector(
            from_cut.end_top.x, from_cut.end_top.z, from_cut.end_top.y
        )
        from_vector_bottom = vector(
            from_cut.end_bottom.x, from_cut.end_bottom.z, from_cut.end_bottom.y
        )

        to_vector_top = vector(to_cut.end_top.x, to_cut.end_top.z, to_cut.end_top.y)
        to_vector_bottom = vector(
            to_cut.end_bottom.x, to_cut.end_bottom.z, to_cut.end_bottom.y
        )

        arrow(
            pos=from_vector_top,
            axis=(to_vector_top - from_vector_top),
            shaftwidth=arrow_width,
            color=color.gray(0.5),
        )
        arrow(
            pos=from_vector_bottom,
            axis=(to_vector_bottom - from_vector_bottom),
            shaftwidth=arrow_width,
            color=color.gray(0.5),
        )
