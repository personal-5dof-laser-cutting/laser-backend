import math
from core.models.geometry import Geometry, TrapezoidalCut
from core.modules.base_optimizer import BaseOptimizer
from core.service_container import Container


class BucketOptimizerModule(BaseOptimizer):
    def __init__(self, material_height: float, epsilon: float = 0.01) -> None:
        super().__init__(material_height)
        self.epsilon: float = epsilon

    def get_current_cost(self, as_cycle: bool) -> float:
        return self.geometry.calculate_travel_cost(self.material_height, as_cycle)

    def _optimize(self):
        optimized_geo = Geometry()
        sorted_cuts = sorted(self.geometry.cuts, key=self._get_sort_tuple)
        optimized_geo.add_cuts(sorted_cuts)
        self.geometry = optimized_geo

    def _get_sort_tuple(self, cut: TrapezoidalCut) -> tuple[int, int, int, int]:
        start_config = cut.start_configuration
        mpos1, mpos2 = Container.kinematics_service.get_positions(
            start_config, self.material_height
        )
        table_angle, laser_head_angle = mpos1.a, mpos1.b
        # We choose only configuration options with positive table angle for better bucketing
        if table_angle < 0 and not math.isclose(table_angle, 0):
            table_angle, laser_head_angle = mpos2.a, mpos2.b
        table_angle_bucket = self.get_bucket_index(table_angle)
        laser_head_angle_bucket = self.get_bucket_index(laser_head_angle)
        x_pos_bucket = self.get_bucket_index(start_config.x)
        y_pos_bucket = self.get_bucket_index(start_config.y)
        return (laser_head_angle_bucket, table_angle_bucket, x_pos_bucket, y_pos_bucket)

    def get_bucket_index(self, value: float) -> int:
        return round(value / self.epsilon)
