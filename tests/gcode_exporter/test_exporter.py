from core.modules.gcode_exporter.gcode_export import GCodeExporter
from core.modules.geometry_visualizer import GeometryVisualizerModule
from core.models.geometry import Geometry, TrapezoidalCut
from Geometry3D import Point, Vector


def test_discretization():
    geometry = Geometry()
    cut = TrapezoidalCut(
        Point(0, 0, 0), Point(1, 0, 0), Point(-1, 0, -1), Point(1.5, 0, -1)
    )
    cut2 = cut.move(Vector(0, 1, 0))

    geometry.add_cut(cut)

    exporter = GCodeExporter(material_height=2)

    visualizer = GeometryVisualizerModule()
    visualizer.process(geometry)

    geometry2 = Geometry()
    geometry2.add_cuts(exporter._discretize_cut(cut2))
    visualizer2 = GeometryVisualizerModule()
    visualizer2.process(geometry2)
