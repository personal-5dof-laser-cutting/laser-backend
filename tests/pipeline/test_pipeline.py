import uvicorn

from api.models.base import FrontendInput
from core.modules.global_optimizer.global_optimizer import GlobalOptimizerModule
from core.pipeline.pipeline import full_pipeline


def start_backend():
    from main import app

    uvicorn.run(app, host="127.0.0.1", port=8000)


def test_full_pipeline():
    input = FrontendInput(
        material="wood",
        material_thickness=10,
        cut_speed=5,
        laser_off=True,
        optimize=False,
        svg=open("tests/svg5dof/svgs/circle_2.svg").read(),
        scaling="mm",
    )

    pipeline = full_pipeline(input)
    assert GlobalOptimizerModule not in [type(module) for module in pipeline.modules]
    g_code_unoptimized = pipeline.run(input.svg)

    input.optimize = True
    pipeline = full_pipeline(input, generations=10)
    print(pipeline.modules)
    assert GlobalOptimizerModule in [type(module) for module in pipeline.modules]
    g_code_optimized = pipeline.run(input.svg)
    assert g_code_unoptimized != g_code_optimized
