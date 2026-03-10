from typing import Tuple

from Geometry3D import Point, Vector, Line, Plane

from core.models.geometry import Geometry
from core.service_container import Container
from core.services.laser_config_service import LaserConfigService


def _project_to_mpos_plane(
    top: Point, bottom: Point, laser_config: LaserConfigService = Container.laser_config
) -> Point:
    topv = Vector(top.x, top.y, top.z)
    bottomv = Vector(bottom.x, bottom.y, bottom.z)
    dir = (topv - bottomv).normalized()
    line = Line(bottom, dir)
    plane = Plane(
        Point(0, 0, laser_config.gantry_height_mm()), Vector(1, 0, 0), Vector(0, 1, 0)
    )
    return plane.intersection(line)


def geo_bbox(
    geo: Geometry,
) -> Tuple[float, float, float, float]:  # xmin, xmax, ymin, ymax
    xmax = float("-inf")
    xmin = float("inf")
    ymax = float("-inf")
    ymin = float("inf")

    for cut in geo.cuts:
        p1 = _project_to_mpos_plane(cut.start_top, cut.start_bottom)
        p2 = _project_to_mpos_plane(cut.end_top, cut.end_bottom)
        xmax = max(xmax, p1.x, p2.x)
        xmin = min(xmin, p1.x, p2.x)
        ymax = max(ymax, p1.y, p2.y)
        ymin = min(ymin, p1.y, p2.y)

    return xmin, xmax, ymin, ymax
