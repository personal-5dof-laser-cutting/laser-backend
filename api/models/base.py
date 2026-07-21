from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

"""Models used by endpoints. Descriptions provided will be visible in the docs UI (Swagger)."""


class GCodeOutput(BaseModel):
    gcode: Any = Field(description="Gcode")


class JobOutput(BaseModel):
    job_id: str = Field(
        description="Job ID used to create a websocket connection (/ws/{job_id})"
    )


class FrontendInput(BaseModel):
    material: str = Field(description="Material type")
    material_thickness: float = Field(description="Material thickness in mm")
    cut_speed: float = Field(description="Speed of the laser cutter in mm/s")
    laser_off: bool = Field(
        description="If true, the laser will be disabled, but the path will still be walked",
    )
    optimize: bool = Field(
        description="If true, an optimizer will approximate an optimized cut order",
    )
    svg: str = Field(description="Content of the svg file")
    dpi: float = Field(
        description="Indicates if SVG was created with Adobe Illustrator scaling or has a scaling in mm",
    )


class WebsocketMessage(BaseModel):
    type: Literal[
        "info",
        "error",
        "abort",
        "update",
        "job_id",
    ] = Field(description="Message Type")
    content: str = Field(
        description="Message content. Can by a singular value or a JSON String"
    )
