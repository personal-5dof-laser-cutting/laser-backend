from typing import Any
from pydantic import BaseModel, Field

"""Models used by endpoints. Descriptions provided will be visible in the docs UI (Swagger)."""


class SvgToGcodeInput(BaseModel):
    material_thickness: float = Field(description="Material thickness in mm")
    laser_off: bool = Field(
        description="If true, the laser will be disabled, but the path will still be walked"
    )
    cut_speed: float = Field(description="Speed of the laser cutter in mm/s")
    svg: str = Field(description="Content of the svg file")
    optimize: bool = Field(description="If true, the global optimizer will try")


class GCodeOutput(BaseModel):
    gcode: Any = Field(description="Gcode")
