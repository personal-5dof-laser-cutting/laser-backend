from abc import ABC
from typing import TypeVar, Generic, Any

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class Module(Generic[TInput, TOutput], ABC):
    """Base class for pipeline modules.
    Sample usage:

    class TestModule(Module):
        @inject
        def process(self, data: str, laser_service: LaserService = Provide[Container.laser_service]) -> str:
            return laser_service.get_laser_status() + " " + data

    """

    def process(self, data: TInput) -> TOutput: ...


class Pipeline:
    """Pipeline class that handles the execution of modules (in-order).
    We might want to swap this out for a more complex data pipeline framework at some point.

    Sample usage:
        pipeline = Pipeline([TestModule()])
        output = pipeline.run(arguments)
    """

    def __init__(self, modules: list[Module]) -> None:
        self.modules = modules

    def run(self, initial_input: Any) -> Any:
        data = initial_input
        for module in self.modules:
            data = module.process(data)
        return data
