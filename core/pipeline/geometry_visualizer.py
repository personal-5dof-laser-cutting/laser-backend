from vpython import scene, quad, curve, vertex, color, arrow, vector, sphere, text

from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module


class GeometryVisualizerModule(Module[Geometry, Geometry]):
    def process(self, data: Geometry) -> Geometry:
        scene.title = "Debug view"
        scene.range = 10
        scene.background = color.gray(0.8)
        scene.width = 1200
        scene.height = 800

        arrow_width = 0.1

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

            quad(
                vs=[vertex(pos=vec, color=color.orange) for vec in cut_vectors],
                opacity=1,
                retain=1,
            )

            self._add_cut_order(data.cuts, arrow_width / 2)
            self._add_cut_direction(cut_vectors, arrow_width)

            if (
                i > 0
                and data.cuts[i - 1].end_configuration()
                != data.cuts[i].start_configuration()
            ):
                self._add_travel_move(data.cuts[i - 1], data.cuts[i], arrow_width)

            outline_points = cut_vectors
            curve(pos=outline_points, color=color.black, radius=0.03)

            sphere(pos=cut_vectors[0], radius=0.1, color=color.red)
            sphere(pos=cut_vectors[1], radius=0.1, color=color.red)
            sphere(pos=cut_vectors[2], radius=0.1, color=color.red)
            sphere(pos=cut_vectors[3], radius=0.1, color=color.red)

        return data

    def _write_text(
        self,
        cut: TrapezoidalCut,
        text_content: str,
        height_offset: float,
        draw_top: bool = True,
    ):
        if draw_top:
            points = [cut.start_top, cut.end_top]
        else:
            points = [cut.start_bottom, cut.end_bottom]
        text_x = (points[0].x + points[1].x) / 2
        text_z = (
            (points[0].y + points[1].y) / 2
        )  # coordinate system uses y for height, which is why TrapezoidalCut y is text_z

        text_height = 0.5
        if draw_top:
            y_pos = height_offset
            z_pos = text_z + text_height / 2
        else:
            y_pos = points[0].z - height_offset
            z_pos = text_z - text_height / 2
        text_pos = vector(text_x, y_pos, z_pos)
        up_vector = vector(0, 0, -1) if draw_top else vector(0, 0, 1)
        text(
            text=text_content,
            pos=text_pos,
            align="center",
            color=color.black,
            height=text_height,
            up=up_vector,
            billboard=False,
        )

    def _add_cut_order(self, cuts: list[TrapezoidalCut], height_offset: float):
        for i, cut in enumerate(cuts):
            self._write_text(cut, str(i + 1), height_offset)
            self._write_text(cut, str(i + 1), -height_offset, draw_top=False)

    def _add_cut_direction(self, cut_vectors: list[vector], arrow_width: float):
        arrow(
            pos=cut_vectors[3],
            axis=(cut_vectors[2] - cut_vectors[3]),
            shaftwidth=arrow_width,
            color=color.red,
        )
        arrow(
            pos=cut_vectors[1],
            axis=(cut_vectors[0] - cut_vectors[1]),
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
