from numpy import rad2deg
from core.models.geometry import Configuration, Geometry
from core.pipeline.base import Module


class BucketOptimizerModule(Module[Geometry, Geometry]):
    def process(self, data: Geometry) -> Geometry:
        optimized_geo = Geometry()
        sorted_cuts = sorted(
            data.cuts, key=lambda cut: self._get_sort_tuple(cut.start_configuration())
        )
        optimized_geo.add_cuts(sorted_cuts)
        return optimized_geo

    def _get_sort_tuple(
        self, config: Configuration
    ) -> tuple[float, float, float, float]:
        alpha = round(rad2deg(config.alpha) / 0.5) * 0.5
        beta = round(rad2deg(config.beta) / 0.5) * 0.5
        x_pos = round(rad2deg(config.x) / 0.5) * 0.5
        y_pos = round(rad2deg(config.y) / 0.5) * 0.5
        return (alpha, beta, x_pos, y_pos)
