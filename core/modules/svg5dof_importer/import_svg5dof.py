"""Imports an SVG5DOF drawing into the cut geometry the rest of the pipeline uses.

The work is split across three layers, each of which knows nothing about the ones
above it:

- ``svg_document`` reads the file and groups its drawable elements,
- ``line_attributes`` decides what each group is meant to cut,
- ``cut_builder`` samples the resulting paths into machine-space geometry.

This module is only the seam between them.
"""

from svgelements import Path

from core.models.geometry import Geometry, TrapezoidalCut
from core.modules.svg5dof_importer.cut_builder import (
    INCH_TO_MM,
    CoordinateTransform,
    build_trapezoids,
    sample_paths,
)
from core.modules.svg5dof_importer.line_attributes import EdgeProfile, read_edge_profile
from core.modules.svg5dof_importer.svg_document import SvgDocument
from core.pipeline.base import Module


class SVG5DOF_Importer(Module[str, Geometry]):
    inch_to_mm = INCH_TO_MM

    def __init__(
        self,
        material_thickness: float,
        dpi: float = 72,
        x_offset: float = 0,
        y_offset: float = 0,
        model_scale: float = 1,
    ) -> None:
        super().__init__()

        self.material_thickness: float = material_thickness
        self.dpi: float = dpi
        self.x_offset: float = x_offset
        self.y_offset: float = y_offset
        self.model_scale: float = model_scale

    def process(self, data: str) -> Geometry:
        document = SvgDocument.parse(data)
        transform = self._coordinate_transform(document)

        geometry: Geometry = Geometry()
        for group in document.line_groups:
            profile = read_edge_profile(group, self.material_thickness)
            top_points, bottom_points = sample_paths(*_profile_paths(profile))

            # Degenerate paths - a stray pen move, a zero-length shape - are common
            # in real exports and must not fail the import.
            if len(top_points) < 2 or len(bottom_points) < 2:
                continue

            cuts: list[TrapezoidalCut] = build_trapezoids(
                transform.apply_all(top_points),
                transform.apply_all(bottom_points),
                profile.cut_depth_mm,
            )
            geometry.add_cuts(cuts)
        return geometry

    def _coordinate_transform(self, document: SvgDocument) -> CoordinateTransform:
        return CoordinateTransform(
            scale=self.model_scale / self.dpi * self.inch_to_mm,
            min_x=document.min_x,
            max_y=document.max_y,
            x_offset=self.x_offset,
            y_offset=self.y_offset,
        )


def _profile_paths(profile: EdgeProfile) -> tuple[Path, Path]:
    """Converts a profile's lines into the two paths to sample.

    A through cut shares one path object between both surfaces: ``direct_close()``
    mutates state that copies of the same element share, so sampling two separate
    copies would close them inconsistently.
    """
    if profile.is_through_cut:
        path = profile.top.to_path()
        return path, path
    return profile.top.to_path(), profile.bottom.to_path()
