from typing import Any

from dataclasses import dataclass

from core.pipeline.base import Pipeline


@dataclass
class Job:
    pipeline: Pipeline
    init_value: Any


jobs: dict[str, Job] = {}
