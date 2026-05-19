from api.models.base import FrontendInput
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule
from core.pipeline.pipeline import full_pipeline


def test_full_pipeline():
    input = FrontendInput(
        material="wood",
        material_thickness=10,
        cut_speed=5,
        laser_off=True,
        optimize=False,
        svg=open("tests/svg5dof/svgs/circle_2.svg").read(),
        dpi=96,
    )

    pipeline = full_pipeline(input)
    assert GreedyOptimizerModule not in [type(module) for module in pipeline.modules]
    _ = pipeline.run(input.svg)

    input.optimize = True
    pipeline = full_pipeline(input)
    print(pipeline.modules)
    assert GreedyOptimizerModule in [type(module) for module in pipeline.modules]
    _ = pipeline.run(input.svg)
