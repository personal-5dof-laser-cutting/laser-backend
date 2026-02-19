import math
from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module


class BucketOptimizerModule(Module[Geometry, Geometry]):
    def __init__(self, epsilon: float = 0.01) -> None:
        self.epsilon = epsilon
        super().__init__()

    def process(self, data: Geometry) -> Geometry:
        optimized_geo = Geometry()
        sorted_cuts = sorted(data.cuts, key=self._get_sort_tuple)
        optimized_geo.add_cuts(sorted_cuts)
        return optimized_geo

    def _get_sort_tuple(self, cut: TrapezoidalCut) -> tuple[int, int, int, int]:
        table_angle, laser_head_angle = cut.cutter_angles(unit="radian")
        # We choose only configuration options with positive table angle for better bucketing
        if table_angle < 0 and not math.isclose(table_angle, 0):
            table_angle += math.pi
            laser_head_angle *= -1
        table_angle_bucket = self.get_bucket_index(table_angle)
        laser_head_angle_bucket = self.get_bucket_index(laser_head_angle)
        start_config = cut.start_configuration()
        x_pos_bucket = self.get_bucket_index(start_config.x)
        y_pos_bucket = self.get_bucket_index(start_config.y)
        return (table_angle_bucket, laser_head_angle_bucket, x_pos_bucket, y_pos_bucket)

    def get_bucket_index(self, value: float) -> int:
        return round(value / self.epsilon)
