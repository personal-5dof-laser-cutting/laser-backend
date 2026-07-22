import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from api.models.base import FrontendInput
from core.pipeline.pipeline import full_pipeline
from api.models.materials import MATERIALS, MaterialData

router = APIRouter()


@router.get(
    path="/get_materials",
    response_class=JSONResponse,
    responses={
        200: {
            "content": {"application/json": {}},
            "description": "JSON object representing all available materials",
        }
    },
)
def get_materials() -> list[MaterialData]:
    return MATERIALS


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
    try:
        file_like = io.StringIO(pipeline.run(inp.svg))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        file_like,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=model.gcode"},
    )
