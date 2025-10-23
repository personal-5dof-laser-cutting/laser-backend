from pydantic import BaseModel, Field

"""Models used by endpoints. Descriptions provided will be visible in the docs UI (Swagger)."""


class SomeInput(BaseModel):
    message: str = Field(description="Provide docs here")


class SomeOutput(BaseModel):
    message: str = Field(description="Provide docs here")
