from ssl import cert_time_to_seconds

from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module
from Geometry3D import Vector
import math


class AutoNester(Module[Geometry, Geometry]):
    def __init__(self, table_center_x: float, table_center_y: float) -> None:
        self.table_center_x: float = table_center_x
        self.table_center_y: float = table_center_y
        super().__init__()

    def process(self, data: Geometry) -> Geometry:
        if len(data.cuts) == 0:
            return data

        min_x: float = 1000000
        max_x: float = -1000000
        min_y: float = 1000000
        max_y: float = -1000000

        for c in data.cuts:
            min_x = min(
                min_x, c.start_top.x, c.start_bottom.x, c.end_top.x, c.end_bottom.x
            )
            max_x = max(
                max_x, c.start_top.x, c.start_bottom.x, c.end_top.x, c.end_bottom.x
            )

            min_y = min(
                min_y, c.start_top.y, c.start_bottom.y, c.end_top.y, c.end_bottom.y
            )
            max_y = max(
                max_y, c.start_top.y, c.start_bottom.y, c.end_top.y, c.end_bottom.y
            )

        center_x: float = (min_x + max_x) / 2
        center_y: float = (min_y + max_y) / 2

        move_vector: Vector = Vector(-center_x, -center_y, 0) + Vector(
            self.table_center_x, self.table_center_y, 0
        )

        for i in range(len(data.cuts)):
            data.cuts[i] = data.cuts[i].move(move_vector)

        return data
