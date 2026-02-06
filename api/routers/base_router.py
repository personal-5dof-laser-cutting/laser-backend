import io
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.models.base import FrontendInput
from core.pipeline.pipeline import full_pipeline

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
def generate_gcode(inp: FrontendInput) -> StreamingResponse:
    pipeline = full_pipeline(inp)
    file_like = io.StringIO(pipeline.run(inp.svg))

    return StreamingResponse(
        file_like,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=model.gcode"},
    )
