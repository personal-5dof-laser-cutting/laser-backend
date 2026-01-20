import io
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.models.base import GCodeOutput, SomeOutput, SvgToGcodeInput
from core.pipeline.pipeline import full_pipline_unoptimized, gcode_pipeline

router = APIRouter()


# sample get endpoint
# will be available under http://127.0.0.1:8000/?inp=foo
@router.get("/", response_model=SomeOutput)
def test_endpoint_1(inp: str) -> SomeOutput:
    return SomeOutput(message=inp)


@router.post("/cut_svg", response_model=GCodeOutput)
def svg_to_gcode(inp: SvgToGcodeInput) -> GCodeOutput:
    pipeline = full_pipline_unoptimized(
        inp.material_thickness, inp.laser_off, inp.cut_speed
    )
    return GCodeOutput(gcode=pipeline.run(inp.svg))


@router.post(
    "/generate_gcode",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/g-code": {}},
            "description": "Prompts a download of a .gcode file",
        }
    },
)
def generate_gcode(inp: SvgToGcodeInput) -> StreamingResponse:
    pipeline = gcode_pipeline(
        inp.material_thickness, inp.optimize, inp.laser_off, inp.cut_speed
    )
    file_like = io.StringIO(pipeline.run(inp.svg))

    return StreamingResponse(
        file_like,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=model.gcode"},
    )
