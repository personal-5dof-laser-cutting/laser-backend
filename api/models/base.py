from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

"""Models used by endpoints. Descriptions provided will be visible in the docs UI (Swagger)."""


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GCodeOutput(BaseModel):
    gcode: Any = Field(description="Gcode")


class ResponseMessage(BaseModel):
    type: Literal["info", "error"] = Field(description="Message Type")
    reason: str = Field(
        description="Short reason as to why this message is sent", default=""
    )
    content: str = Field(
        description="Message content. Can be a singular value or a JSON string"
    )


class FrontendInput(StrictBaseModel):
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


message_type_description = "Message Type"
type CutterActions = Literal["abort", "home"]


class InfoMessage(StrictBaseModel):
    type: Literal["info"] = Field(description=message_type_description)
    content: str = Field(description="Message content")


class ErrorMessage(StrictBaseModel):
    type: Literal["error"] = Field(description=message_type_description)
    content: str = Field(description="Message content")


class ActionMessage(StrictBaseModel):
    type: Literal["action"] = Field(description=message_type_description)
    action: CutterActions = Field(description="An action to be performed by the cutter")


class UpdateMessage(StrictBaseModel):
    type: Literal["update"] = Field(description=message_type_description)
    form: Literal["progress", "status"] = Field(
        description="Either the progress of the current job or the Machine status"
    )
    content: Optional[str] = Field(description="Update information")


class JobMessage(StrictBaseModel):
    type: Literal["job"] = Field(description=message_type_description)
    input: FrontendInput = Field(description="A FrontendInput object")


type WebsocketMessage = Annotated[
    Union[InfoMessage, ErrorMessage, ActionMessage, UpdateMessage, JobMessage],
    Field(discriminator="type"),
]
