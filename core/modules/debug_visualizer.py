from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module

import matplotlib.pyplot as plt
from typing import Tuple
from enum import IntFlag


class Flags(IntFlag):
    SHOW_AREA = 0b01
    SHOW_ORDER = 0b10


class DebugVisualizerModule(Module[Tuple[Geometry, Flags], Geometry]):
    max_x = 0
    max_y = 0

    def process(self, data: Tuple[Geometry, Flags]) -> Geometry:
        geometry, flags = data
        shadeArea = bool(flags & Flags.SHOW_AREA)
        showOrder = bool(flags & Flags.SHOW_ORDER)
        self.fig, self.ax = plt.subplots()
        for cut in geometry.cuts:
            self._draw_cut(cut, shadeArea, showOrder)
        self.ax.set_xlim(-1, self.max_x + 5)
        self.ax.set_ylim(-1, self.max_y + 5)
        self.ax.set_aspect("equal")

        plt.show()
        return geometry

    def _draw_cut(self, cut: TrapezoidalCut, shadeArea: bool, showOrder: bool):
        start_top = cut.top_segment().start_point
        end_top = cut.top_segment().end_point

        start_bottom = cut.bottom_segment().start_point
        end_bottom = cut.bottom_segment().end_point

        if showOrder:
            self.ax.arrow(
                start_top.x,
                start_top.y,
                end_top.x - start_top.x,
                end_top.y - start_top.y,
                length_includes_head=True,
                color="red",
                head_width=0.3,
                head_length=0.3,
            )
            self.ax.arrow(
                start_bottom.x,
                start_bottom.y,
                end_bottom.x - start_bottom.x,
                end_bottom.y - start_bottom.y,
                length_includes_head=True,
                color="blue",
            )
        else:
            self.ax.plot(
                (start_top.x, end_top.x), (start_top.y, end_top.y), color="red"
            )
            self.ax.plot(
                (start_bottom.x, end_bottom.x),
                (start_bottom.y, end_bottom.y),
                color="blue",
            )

        self.ax.plot(
            (start_top.x, start_bottom.x), (start_top.y, start_bottom.y), color="purple"
        )
        self.ax.plot(
            (end_top.x, end_bottom.x), (end_top.y, end_bottom.y), color="purple"
        )

        self.max_x = max(
            [self.max_x, start_top.x, end_top.x, start_bottom.x, end_bottom.x]
        )
        self.max_y = max(
            [self.max_y, start_top.y, end_top.y, start_bottom.y, end_bottom.y]
        )

    def _draw_travel_move(self):
        pass
