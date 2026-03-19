from dataclasses import dataclass
import math

from Geometry3D import Point

import io


from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module

from svgelements import (
    SVG,
    Group,
    Shape,
    Path,
    Color,
    Line,
    Arc,
    CubicBezier,
    QuadraticBezier,
    Move,
    Close,
)


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


def svg_element_to_path(element: Path | Shape) -> Path:
    if isinstance(element, Shape):
        path = Path(element)
        path.reify()
        return path
    return element


def filter_svg_path(element: Path) -> list[Arc | QuadraticBezier | CubicBezier]:
    return [
        seg for seg in element if not (isinstance(seg, Move) or isinstance(seg, Close))
    ]


def svg_paths_to_points(
    bottom_path: Path, top_path: Path, resolution_mm=1
) -> tuple[list[Point2D], list[Point2D]]:

    bottom_path.direct_close()
    top_path.direct_close()
    bottom_path.validate_connections()
    top_path.validate_connections()

    bottom_segments: list = filter_svg_path(bottom_path)
    top_segments: list = filter_svg_path(top_path)
    if (b := len(bottom_segments)) != (t := len(top_segments)):
        raise ValueError(
            f"Top and bottom path do not have the same number of segments. ({t} != {b})"
        )
    bottom_points = []
    top_points = []
    for bottom_segment, top_segment in zip(bottom_segments, top_segments):
        if isinstance(bottom_segment, Line) and isinstance(top_segment, Line):
            bottom_points.extend([Point2D.from_complex(p) for p in bottom_segment])
            top_points.extend([Point2D.from_complex(p) for p in top_segment])
        elif (
            (isinstance(bottom_segment, Arc) and isinstance(top_segment, Arc))
            or (
                isinstance(bottom_segment, CubicBezier)
                and isinstance(top_segment, CubicBezier)
            )
            or (
                isinstance(bottom_segment, QuadraticBezier)
                and isinstance(top_segment, QuadraticBezier)
            )
        ):
            max_len: float = max(bottom_segment.length(), top_segment.length())
            num_points: int = max(math.ceil(max_len / resolution_mm), 2)
            points_x: list[float] = [t / (num_points - 1) for t in range(num_points)]
            bottom_points.extend([bottom_segment.point(x) for x in points_x])
            top_points.extend([top_segment.point(x) for x in points_x])
        elif isinstance(bottom_segment, Move) and isinstance(top_segment, Move):
            continue
        elif isinstance(bottom_segment, Close) and isinstance(top_segment, Close):
            continue
        else:
            raise ValueError(f"This is bad. {type(bottom_segment)} {type(top_segment)}")

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
        try:
            try:
                cut = TrapezoidalCut(start_top, end_top, start_bottom, end_bottom)
            except ValueError:
                cut = TrapezoidalCut(start_top, end_top, end_bottom, start_bottom)
        except Exception as e:
            print(
                f"Warning: Skipped points because they do not form valid trapezoids: {e}"
            )
            continue
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
        if elem1.stroke.lightness == 0:
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

            if len(bottom_points) < 2 or len(top_points) < 2:
                continue

            cuts: list[TrapezoidalCut] = points_to_trapezoids(
                self._transform_points(bottom_points),
                self._transform_points(top_points),
                cut_depth,
            )

            geometry.add_cuts(cuts)
        return geometry
