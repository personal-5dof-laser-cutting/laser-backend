from core.models.geometry import TrapezoidalCut, Geometry
from Geometry3D import Point
from core.modules.gcode_exporter.gcode_export import GCodeExporter
from core.modules.geometry_visualizer.geometry_visualizer import (
    GeometryVisualizerModule,
)


def test_segmentation():
    # this only checks if no errors occur while segmenting a cut
    cut = TrapezoidalCut(
        Point(0, 0, 0), Point(10, 0, 0), Point(5, 0, -1), Point(10.5, 0, -1)
    )

    exporter = GCodeExporter(1, laser_off=False, force_max_laser_power=False)
    cuts = exporter._discretize_cut(cut)
    geo = Geometry()
    geo.add_cuts(cuts)

    test_geo = Geometry()
    test_geo.add_cut(cut)
