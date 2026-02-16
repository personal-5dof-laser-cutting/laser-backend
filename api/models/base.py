from typing import Any, Literal
from pydantic import BaseModel, Field

ScalingType = Literal["mm", "illustrator"]

"""Models used by endpoints. Descriptions provided will be visible in the docs UI (Swagger)."""


class GCodeOutput(BaseModel):
    gcode: Any = Field(description="Gcode")


class FrontendInput(BaseModel):
    material: str = Field(description="Material type")
    material_thickness: float = Field(description="Material thickness in mm")
    cut_speed: float = Field(description="Speed of the laser cutter in mm/s")
    laser_off: bool = Field(
        description="If true, the laser will be disabled, but the path will still be walked",
    )
    optimize: bool = Field(
        description="If true, the global optimizer will approximate an optimized cut order",
    )
    svg: str = Field(description="Content of the svg file")
    scaling: ScalingType = Field(
        description="Indicates if SVG was created with Adobe Illustrator scaling or has a scaling in mm",
    )
    x_offset: int = Field(
        description="How many millimeters the svg should be moved alongside the x-axis",
        default=0,
    )
    y_offset: int = Field(
        description="How many millimeters the svg should be moved alongside the y-axis",
        default=0,
    )
