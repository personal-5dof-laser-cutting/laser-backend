from pydantic import BaseModel, Field


class MaterialData(BaseModel):
    id: str = Field(description="Material ID")
    label: str = Field(description="Material name / label")
    suggested_cutspeed: float = Field(description="Suggested cutspeed for the material")
    standard_thickness: float = Field(description="Standard thickness", default=5.0)


MATERIALS: list[MaterialData] = [
    MaterialData(id="wood", label="wood", suggested_cutspeed=20, standard_thickness=5),
    MaterialData(id="mdf", label="MDF", suggested_cutspeed=30, standard_thickness=5),
]
