from api.models.base import FrontendInput
from core.modules.genetic_optimizer.genetic_optimizer import GeneticOptimizerModule
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
    assert GeneticOptimizerModule not in [type(module) for module in pipeline.modules]
    g_code_unoptimized = pipeline.run(input.svg)

    input.optimize = True
    pipeline = full_pipeline(input, generations=10)
    print(pipeline.modules)
    assert GeneticOptimizerModule in [type(module) for module in pipeline.modules]
    g_code_optimized = pipeline.run(input.svg)
    assert g_code_unoptimized != g_code_optimized
