from fastapi import APIRouter

from api.models.base import GCodeOutput, SomeOutput, SvgToGcodeInput
from core.pipeline.pipeline import full_pipline_unoptimized

router = APIRouter()


# sample get endpoint
# will be available under http://127.0.0.1:8000/?inp=foo
@router.get("/", response_model=SomeOutput)
def test_endpoint_1(inp: str) -> SomeOutput:
    return SomeOutput(message=inp)


@router.post("/post", response_model=GCodeOutput)
def svg_to_gcode(inp: SvgToGcodeInput) -> GCodeOutput:
    pipeline = full_pipline_unoptimized(
        inp.material_thickness, inp.laser_off, inp.cut_speed
    )
    return GCodeOutput(gcode=pipeline.run(inp.svg))
