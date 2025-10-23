from dependency_injector.wiring import inject
from fastapi import APIRouter

from src.api.models.base import SomeOutput, SomeInput

router = APIRouter()


# sample get endpoint
# will be available under http://127.0.0.1:8000/?inp=foo
@router.get("/", response_model=SomeOutput)
@inject
def test_endpoint_1(inp: str) -> SomeOutput:
    return SomeOutput(message=inp)


# sample post endpoint
@router.post("/post")
def test_endpoint_post(inp: SomeInput) -> SomeOutput:
    return SomeOutput(message=inp.message)
