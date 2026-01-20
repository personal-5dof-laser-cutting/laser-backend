from typing import Any
from pydantic import BaseModel, Field

"""Models used by endpoints. Descriptions provided will be visible in the docs UI (Swagger)."""


class SomeInput(BaseModel):
    message: str = Field(description="Provide docs here")


class SvgToGcodeInput(BaseModel):
    material_thickness: float
    laser_off: bool
    cut_speed: float
    svg: str
    optimize: bool


class GCodeOutput(BaseModel):
    gcode: Any = Field(description="Gcode")


class SomeOutput(BaseModel):
    message: str = Field(description="Provide docs here")
