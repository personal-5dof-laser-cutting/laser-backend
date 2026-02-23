from copy import deepcopy

from Geometry3D import Vector

from core.models.geometry import Geometry
from core.pipeline.base import Module


class NaiveNestingModule(Module[Geometry, Geometry]):
    def __init__(self, center_x: float = 200, center_y: float = 200) -> None:
        super().__init__()

    def process(self, data: Geometry) -> Geometry:
        geo = deepcopy(data)

        min_x: float = 10000
        max_x: float = -10000
        min_y: float = 10000
        max_y: float = -10000
        for cut in geo.cuts:
            min_x = min(
                min_x,
                cut.start_top.x,
                cut.end_top.x,
                cut.start_bottom.x,
                cut.end_bottom.x,
            )
            max_x = max(
                max_x,
                cut.start_top.x,
                cut.end_top.x,
                cut.start_bottom.x,
                cut.end_bottom.x,
            )
            min_y = min(
                min_y,
                cut.start_top.y,
                cut.end_top.y,
                cut.start_bottom.y,
                cut.end_bottom.y,
            )
            max_y = max(
                max_y,
                cut.start_top.y,
                cut.end_top.y,
                cut.start_bottom.y,
                cut.end_bottom.y,
            )
        print(f"Bounds: x={min_x:.3f} y={min_y:.3f}    x={max_x:.3f} y={max_y:.3f}")
        print(f"Size: width={max_x - min_x:.3f}  height={max_y - min_y:.3f}")
        offset_x = (max_x + min_x) / 2.0
        offset_y = (max_y + min_y) / 2.0

        for cut in geo.cuts:
            cut = cut.move(Vector(offset_x, offset_y, 0))

        return data
