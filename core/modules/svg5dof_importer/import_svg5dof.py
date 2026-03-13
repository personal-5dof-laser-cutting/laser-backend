from dataclasses import dataclass
import math

from Geometry3D import Point

import io


from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module

from svgelements import SVG, Group, Shape, Path, Line, Color


@dataclass
class Point2D:
    x: float
    y: float

    @classmethod
    def from_complex(cls, p: complex) -> "Point2D":
        return Point2D(x=float(p.real), y=float(p.imag))

    def __iter__(self):
        yield self.x
        yield self.y

    def to_point3d(self, z: float = 0) -> Point:
        return Point(self.x, self.y, z)

    def __eq__(self, other):
        return (
            isinstance(other, Point2D)
            and math.isclose(self.x, other.x)
            and math.isclose(self.y, other.y)
        )


def svg_elem_to_points(
    svg_element: Path,
    num_points: int = 2,
) -> list[Point2D]:
    if len(svg_element) == 0:
        return []

    if len(svg_element) == 1 and isinstance(svg_element[0], Line):
        num_points = 2

    num_points = 2

    # segment_lengths: list[float] = [
    #    elem.length() for elem in svg_element if elem.length() > 0
    # ]
    points_x: list[float] = [t / (num_points - 1) for t in range(num_points)]
    result = [Point2D.from_complex(svg_element.point(t)) for t in points_x]
    return result


def svg_element_to_path(element: Path | Shape) -> Path:
    if isinstance(element, Shape):
        path = Path(element)
        path.reify()
        return path
    return element


def path_total_length(element: Path) -> float:
    return sum([e.length() for e in element])


def svg_paths_to_points(
    bottom_path: Path, top_path: Path, resolution_mm=1
) -> tuple[list[Point2D], list[Point2D]]:
    max_length: float = max(path_total_length(top_path), path_total_length(bottom_path))
    num_segments: int = math.ceil(max_length / resolution_mm)

    top_points = svg_elem_to_points(top_path, num_points=num_segments)
    bottom_points = svg_elem_to_points(bottom_path, num_points=num_segments)

    return (bottom_points, top_points)


def points_to_trapezoids(
    bottom_points: list[Point2D], top_points: list[Point2D], material_height: float
) -> list[TrapezoidalCut]:
    if len(top_points) < 2 or len(bottom_points) < 2:
        raise ValueError("There must be at least two top and two bottom points.")
    if len(top_points) != len(bottom_points):
        raise ValueError(
            f"There must be an equal amount of top ({len(top_points)} points) and bottom ({len(bottom_points)} points) points."
        )

    points: list[tuple[Point2D, Point2D]] = list(zip(top_points, bottom_points))
    trapezoids: list[TrapezoidalCut] = []

    for end, start in zip(points + [(None, None)], [(None, None)] + points):
        if None in start or None in end:
            continue
        if end == start:
            continue

        start_top = start[0].to_point3d(0)  # type: ignore
        end_top = end[0].to_point3d(0)  # type: ignore
        start_bottom = start[1].to_point3d(-material_height)  # type: ignore
        end_bottom = end[1].to_point3d(-material_height)  # type: ignore
        cut = TrapezoidalCut(start_top, end_top, start_bottom, end_bottom)
        trapezoids.append(cut)

    return trapezoids


class SVG5DOF_Importer(Module[str, Geometry]):
    inch_to_mm = 25.4

    def __init__(
        self,
        material_thickness: float,
        dpi: float = 72,
    ) -> None:
        super().__init__()

        self.material_thickness: float = material_thickness
        self.dpi: float = dpi

    def _transform_points(self, points: list[Point2D]) -> list[Point2D]:
        # This flips the origin from top/left (SVG) to bottom/left (FluidNC) and scales from points to mm
        scaling_factor: float = 1 / self.dpi * self.inch_to_mm
        return [
            Point2D(
                p.x * scaling_factor,
                -p.y * scaling_factor,
            )
            for p in points
        ]

    def _5dof_color_to_percentage(self, color: Color) -> float:
        if color.saturation != 0.0:
            raise Exception("Found non grayscale line in svg.")

        value: float = color.lightness  # type: ignore
        if value > 0.8:
            raise Exception("Found out of bounds color in svg.")

        percentage: float = value / 0.8
        return min(percentage, 1.0)

    def _find_top_bottom_element(self, elem1: Path, elem2: Path) -> tuple[Path, Path]:
        if elem1.stroke == Color(r=0, g=0, b=0):
            return elem2, elem1
        else:
            return elem1, elem2

    def _filter_svg_elements(self, svg_elements: Group) -> list[Shape | list[Shape]]:
        output = []
        for element in svg_elements:
            if isinstance(element, Shape):
                if element.stroke.value is not None:
                    output.append(element)
            elif isinstance(element, Group) and len(element) > 0:
                result = self._filter_svg_elements(element)
                if (
                    len(result) == 2
                    and sum([isinstance(e, Shape) for e in result]) == 2
                ):
                    output.append(result)
                else:
                    output.extend(result)
        return output

    def process(
        self,
        data: str,
    ) -> Geometry:
        svg_file = io.StringIO(data)
        svg: SVG = SVG.parse(
            svg_file,
            reify=True,
            ppi=72,
        )

        geometry: Geometry = Geometry()

        filtered_elements = self._filter_svg_elements(svg)  # type: ignore

        for element in filtered_elements:
            top_points: list[Point2D] = []
            bottom_points: list[Point2D] = []
            cut_depth: float = self.material_thickness

            if isinstance(element, Group) or isinstance(element, list):
                bottom, top = self._find_top_bottom_element(
                    svg_element_to_path(element[0]),
                    svg_element_to_path(element[1]),
                )
                bottom_points, top_points = svg_paths_to_points(bottom, top)

            elif isinstance(element, Shape) or isinstance(element, Path):
                path = svg_element_to_path(element)
                bottom_points, top_points = svg_paths_to_points(path, path)
                cut_depth = self.material_thickness

            if len(bottom_points) == 0 or len(top_points) == 0:
                continue

            cuts: list[TrapezoidalCut] = points_to_trapezoids(
                bottom_points, top_points, cut_depth
            )

            geometry.add_cuts(cuts)
        return geometry
