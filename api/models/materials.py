from pydantic import BaseModel, Field


class MaterialData(BaseModel):
    id: str = Field(description="Material ID")
    label: str = Field(description="Material name / label")
    standard_thickness: float = Field(description="Standard thickness", default=5.0)


MATERIALS: list[MaterialData] = [
    MaterialData(id="wood", label="wood", standard_thickness=5),
    MaterialData(id="mdf", label="MDF", standard_thickness=5),
]
