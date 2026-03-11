from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module
from Geometry3D import Vector
import math


class LocalOptimizer(Module[Geometry, Geometry]):
    def __init__(self) -> None:
        super().__init__()

    def process(self, data: Geometry) -> Geometry:
        result = Geometry()
        for cut in data.cuts:
            top = cut.top_vector()
            left = cut.start_vector()
            right = cut.end_vector()
            bottom = cut.bottom_vector()

            start_top = cut.start_top
            end_top = cut.end_top
            start_bottom = cut.start_bottom
            end_bottom = cut.end_bottom

            left_flat = Vector(left[0], left[1], 0)
            right_flat = Vector(right[0], right[1], 0)

            if top.angle(left) > math.radians(90):  # type: ignore
                start_top.move(left_flat)
            else:
                start_bottom.move(-left_flat)

            if top.angle(right) > math.radians(90):
                end_bottom.move(-right_flat)
            else:
                end_top.move(right_flat)

            new_cut = TrapezoidalCut(start_top, end_top, start_bottom, end_bottom)
            result.add_cut(new_cut)
        return result
