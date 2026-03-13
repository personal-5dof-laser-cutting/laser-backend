from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module
from Geometry3D import Vector
import math


class LocalOptimizer(Module[Geometry, Geometry]):
    def __init__(self) -> None:
        super().__init__()

    def _calculate_move_vector(
        self, angle: float, side_length: float, dv: Vector
    ) -> Vector:
        #                   ->
        #                   dv
        #          angle ________
        #               /|
        # side_length  / |
        #             /__|_______
        #
        #             --->
        #           return value
        #
        return dv.normalized() * math.sin(angle) * side_length

    def process(self, data: Geometry) -> Geometry:
        result = Geometry()
        for cut in data.cuts:
            top = cut.top_vector()
            left = cut.start_vector()
            right = cut.end_vector()

            start_top = cut.start_top
            end_top = cut.end_top
            start_bottom = cut.start_bottom
            end_bottom = cut.end_bottom

            if (angle := top.angle(left)) > math.radians(90):  # /
                start_top.move(
                    -self._calculate_move_vector(
                        angle - math.radians(90), left.length(), top
                    )
                )
            else:  # \
                start_bottom.move(
                    -self._calculate_move_vector(angle, left.length(), top)
                )

            if (angle := top.angle(right)) > math.radians(90):  # \
                end_bottom.move(
                    -self._calculate_move_vector(
                        angle - math.radians(90), right.length(), top
                    )
                )
            else:  # /
                end_top.move(
                    -self._calculate_move_vector(angle, right.length(), top)
                )  # /

            new_cut = TrapezoidalCut(start_top, end_top, start_bottom, end_bottom)
            result.add_cut(new_cut)
        return result
