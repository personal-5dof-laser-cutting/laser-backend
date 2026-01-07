from Geometry3D import Point
from matplotlib.patches import PathPatch
from matplotlib.textpath import TextPath
from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module

from mpl_interactions import panhandler, zoom_factory
import matplotlib.pyplot as plt

import math
from enum import IntFlag


class VisualizerFlags(IntFlag):
    SHOW_AREA = 0b01
    SHOW_ORDER = 0b10


class DebugVisualizerModule(Module[Geometry, Geometry]):
    max_x = 0
    max_y = 0

    def __init__(self, flags: VisualizerFlags) -> None:
        super().__init__()

        self.shadeArea = bool(flags & VisualizerFlags.SHOW_AREA)
        self.showOrder = bool(flags & VisualizerFlags.SHOW_ORDER)

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
        zoom_factory(self.ax)
        panhandler(self.fig)

        plt.show()
        return geometry

    def _draw_cut(self, cut: TrapezoidalCut, cut_number: int):
        start_top = cut.top_segment().start_point
        end_top = cut.top_segment().end_point

        start_bottom = cut.bottom_segment().start_point
        end_bottom = cut.bottom_segment().end_point

        is_slanted_cut = not math.isclose(cut.plane().n[2], 0)

        self.ax.plot((start_top.x, end_top.x), (start_top.y, end_top.y), color="red")
        if is_slanted_cut:
            self.ax.plot(
                (start_bottom.x, end_bottom.x),
                (start_bottom.y, end_bottom.y),
                color="blue",
            )
            if self.showOrder:
                arrow_start = Point(
                    (start_top.x + start_bottom.x) / 2,
                    (start_top.y + start_bottom.y) / 2,
                    0,
                )
                arrow_end = Point(
                    (end_top.x + end_bottom.x) / 2, (end_top.y + end_bottom.y) / 2, 0
                )
                arrow_direction = Point(
                    arrow_end.x - arrow_start.x, arrow_end.y - arrow_start.y, 0
                )
                self.ax.arrow(
                    arrow_start.x + arrow_direction.x * 0.05,
                    arrow_start.y + arrow_direction.y * 0.05,
                    arrow_direction.x * 0.9,
                    arrow_direction.y * 0.9,
                    length_includes_head=True,
                    color="black",
                    width=0.1,
                    head_width=1,
                    head_length=1,
                )

                text_size = 2
                text_path = TextPath(
                    (
                        (arrow_start.x + arrow_end.x) / 2 - text_size / 2,
                        (arrow_start.y + arrow_end.y) / 2 - text_size / 2,
                    ),
                    str(cut_number),
                    size=text_size,
                )
                self.ax.add_patch(PathPatch(text_path, color="black"))

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

    def _draw_travel_move(self, from_config: Configuration, to_config: Configuration):
        self.ax.arrow(
            from_config.x,
            from_config.y,
            to_config.x - from_config.x,
            to_config.y - from_config.y,
            length_includes_head=True,
            color="gray",
            width=0.075,
        )
