from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module

import matplotlib.pyplot as plt
from Geometry3D import Point, Vector
from enum import IntFlag

import math


class VisualizerFlags(IntFlag):
    SHOW_AREA = 0b01
    SHOW_ORDER = 0b10


class DebugVisualizerModule(Module[Geometry, Geometry]):
    max_x = 0
    max_y = 0
    shadeArea = False
    showOrder = False
    direction_map = ["←", "↑", "→", "↓"]

    def __init__(
        self, material_height: float, flags: VisualizerFlags | None = None
    ) -> None:
        super().__init__()
        self.material_height = material_height
        if flags:
            self.shadeArea = bool(flags & VisualizerFlags.SHOW_AREA)
            self.showOrder = bool(flags & VisualizerFlags.SHOW_ORDER)

        self.lightest_grey_value = 0.8
        self.arrow_width = 0.1

    def process(self, data: Geometry) -> Geometry:
        geometry = data
        self.fig, self.ax = plt.subplots()
        for i, cut in enumerate(geometry.cuts):
            self._draw_cut(cut, i)
            if i != len(geometry.cuts) - 1:
                if (
                    geometry.cuts[i + 1].start_configuration()
                    != cut.end_configuration()
                ):
                    self._draw_travel_move(
                        cut.end_configuration(),
                        geometry.cuts[i + 1].start_configuration(),
                    )
        self.ax.set_xlim(-1, self.max_x + 5)
        self.ax.set_ylim(-1, self.max_y + 5)
        self.ax.set_aspect("equal")

        plt.show()
        return geometry

    def _draw_cut(self, cut: TrapezoidalCut, cut_number: int):
        start_top = cut.top_segment().start_point
        end_top = cut.top_segment().end_point

        start_bottom = cut.bottom_segment().start_point
        end_bottom = cut.bottom_segment().end_point

        self._draw_line(start_top, end_top, "black")
        if not cut.is_straight_cut():
            self._draw_line(
                start_bottom, end_bottom, self._get_grey_color(-start_bottom.z)
            )
            self._draw_connecting_lines(cut)

        if self.showOrder:
            cut_direction: Vector = Vector(cut.start_top, cut.end_top)
            angle = cut_direction.angle(Vector.y_unit_vector())
            direction = (
                int(angle * (-1 if cut_direction[0] < 0 else 1) * 2 / math.pi) + 1
            )
            text_point = Point(
                (start_top.x + end_top.x + start_bottom.x + end_bottom.x) / 4,
                (start_top.y + end_top.y + start_bottom.y + end_bottom.y) / 4,
                0,
            )
            self.ax.text(
                text_point.x,
                text_point.y,
                str(cut_number + 1) + self.direction_map[direction],
            )

        self.max_x = max(
            [self.max_x, start_top.x, end_top.x, start_bottom.x, end_bottom.x]
        )
        self.max_y = max(
            [self.max_y, start_top.y, end_top.y, start_bottom.y, end_bottom.y]
        )

    def _draw_travel_move(self, from_config: Configuration, to_config: Configuration):
        self.ax.arrow(
            from_config.x,
            from_config.y,
            to_config.x - from_config.x,
            to_config.y - from_config.y,
            length_includes_head=True,
            color="#0004",
            linestyle="dotted",
            width=self.arrow_width * 3 / 4,
        )

    def _draw_connecting_lines(self, cut: TrapezoidalCut):
        color = "#bbe"
        linestyle = "dashdot"
        self._draw_line(cut.start_top, cut.start_bottom, color, linestyle)
        self._draw_line(
            Point((cut.start_top.pv() + cut.end_top.pv()) * 0.5),
            Point((cut.start_bottom.pv() + cut.end_bottom.pv()) * 0.5),
            color,
            linestyle,
        )
        self._draw_line(cut.end_top, cut.end_bottom, color, linestyle)

    def _draw_line(
        self, start: Point, end: Point, color: str, linestyle: str = "solid"
    ):
        self.ax.plot(
            (start.x, end.x), (start.y, end.y), color=color, linestyle=linestyle
        )

    def _get_grey_color(self, cut_depth: float) -> str:
        assert cut_depth > 0
        assert cut_depth < self.material_height or math.isclose(
            cut_depth, self.material_height
        )
        percentage = cut_depth / self.material_height
        grey = self.lightest_grey_value * percentage
        return str(grey)
