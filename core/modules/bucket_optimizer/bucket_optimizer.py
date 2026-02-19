import math
from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module


class BucketOptimizerModule(Module[Geometry, Geometry]):
    def process(self, data: Geometry) -> Geometry:
        optimized_geo = Geometry()
        sorted_cuts = sorted(data.cuts, key=lambda cut: self._get_sort_tuple(cut))
        optimized_geo.add_cuts(sorted_cuts)
        return optimized_geo

    def _get_sort_tuple(self, cut: TrapezoidalCut) -> tuple[float, float, float, float]:
        table_angle, laser_head_angle = cut.cutter_angles(unit="radian")
        # We choose only configuration options with positive table angle for better bucketing
        if table_angle < 0 and not math.isclose(table_angle, 0):
            table_angle += math.pi
            laser_head_angle *= -1
        epsilon = 0.01
        table_angle = self.round_to_epsilon(table_angle, epsilon)
        laser_head_angle = self.round_to_epsilon(laser_head_angle, epsilon)
        x_pos = self.round_to_epsilon(cut.start_configuration().x, epsilon)
        y_pos = self.round_to_epsilon(cut.start_configuration().y, epsilon)
        return (table_angle, laser_head_angle, x_pos, y_pos)

    def round_to_epsilon(self, value: float, epsilon: float) -> float:
        return round(value / epsilon) * epsilon
