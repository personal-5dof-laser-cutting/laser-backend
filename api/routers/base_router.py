import io
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.models.base import SvgToGcodeInput
from core.pipeline.pipeline import gcode_pipeline

router = APIRouter()


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
