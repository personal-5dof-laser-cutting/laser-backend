import Geometry3D
from core.models.geometry import Geometry
from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule
from core.modules.debug_visualizer.debug_visualizer import (
    DebugVisualizerModule,
    VisualizerFlags,
)
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def test_optimizer():
    Geometry3D.set_sig_figures(4)
    svg = "/home/leonarddf/Downloads/washboard - 6mm.svg"
    dof = SVG5DOF_Importer(6, "illustrator")
    geometry: Geometry = dof.process(open(svg).read())
    given_cuts = geometry.cuts.copy()
    vis = DebugVisualizerModule(6, VisualizerFlags.SHOW_ORDER)
    # vis.process(geometry)
    opt = BucketOptimizerModule()
    optimized = opt.process(geometry)
    assert given_cuts != optimized.cuts
    vis.process(optimized)
