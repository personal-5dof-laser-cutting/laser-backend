from dataclasses import dataclass
import math

from Geometry3D import Point
import svgpathtools as svg
import xml.etree.ElementTree as ET

from api.models.base import ScalingType
from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module

from PIL.ImageColor import getrgb


TOP_COLOR = (0, 0, 0, 255)  # black
BOTTOM_COLOR = (204, 204, 204, 255)  # 20% gray


@dataclass
class Point2D:
    x: float
    y: float

    @classmethod
    def from_complex(cls, p: complex) -> "Point2D":
        return Point2D(x=p.real, y=p.imag)

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


def compare_rgba_tuples(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> float:
    """
    Compare two numeric tuples element-wise and return the sum of absolute differences.
    """
    if len(a) != len(b):
        raise ValueError(f"Tuples must be of same length ({len(a)} != {len(b)})")

    differences = [abs(x - y) for x, y in zip(a, b)]
    return sum(differences)


def svg_elem_to_points(
    svg_elem: svg.Line | svg.Arc | svg.CubicBezier | svg.QuadraticBezier,
    num_points: int = 2,
) -> list[Point2D]:
    if isinstance(svg_elem, svg.Line):
        num_points = 2

    num_points = max(2, num_points)

    points: list[complex] = [
        svg_elem.point(t / (num_points - 1)) for t in range(num_points)
    ]

    return [Point2D.from_complex(p_complex) for p_complex in points]


def svg_paths_to_points(
    bottom_path: svg.Path, top_path: svg.Path, resolution_mm=1
) -> tuple[list[Point2D], list[Point2D]]:
    if len(bottom_path) != len(top_path):
        raise Exception("Top and bottom path must have the same number of elements.")

    top_points: list[Point2D] = []
    bottom_points: list[Point2D] = []

    for top_elem, bottom_elem in zip(top_path, bottom_path):
        top_length: float = top_elem.length()  # type: ignore
        bottom_length: float = bottom_elem.length()  # type: ignore

        max_length: float = max(top_length, bottom_length)
        num_segments: int = math.ceil(max_length / resolution_mm)

        top_points.extend(svg_elem_to_points(top_elem, num_points=num_segments))
        bottom_points.extend(svg_elem_to_points(bottom_elem, num_points=num_segments))

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


def svg_color_to_rgba(col: str) -> tuple[int, int, int, int]:
    """
    Convert an SVG/CSS color string into a 4-tuple RGBA color.
    """
    result = getrgb(col)
    return result if len(result) == 4 else result + (255,)


class SVG5DOF_Importer(Module[str, Geometry]):
    dpi = 72
    inch_to_mm = 25.4

    def __init__(
        self,
        material_thickness: float,
        scaling: ScalingType = "mm",
        x_offset: int = 0,
        y_offset: int = 0,
    ) -> None:
        super().__init__()
        scaling_factors: dict[str, float] = {
            "illustrator": (1 / self.dpi) * self.inch_to_mm,
            "mm": 1,
        }
        self.material_thickness: float = material_thickness
        self.scaling_factor: float = scaling_factors[scaling]
        self.x_offset = x_offset
        self.y_offset = y_offset

    def _transform_points(self, points: list[Point2D]) -> list[Point2D]:
        return [
            Point2D(
                p.x * self.scaling_factor + self.x_offset,
                -p.y * self.scaling_factor + self.y_offset,
            )
            for p in points
        ]

    def _5dof_color_to_percentage(self, color: tuple[int, int, int, int]) -> float:
        if not (color[0] == color[1] and color[1] == color[2]):
            raise Exception("Found non grayscale line in svg.")

        value: int = color[0]
        if value > BOTTOM_COLOR[0]:
            raise Exception("Found out of bounds color in svg.")

        percentage: float = value / BOTTOM_COLOR[0]
        return percentage

    def process(
        self,
        data: str,
    ) -> Geometry:
        svg_content: str = data

        svg_root = ET.fromstring(svg_content)
        svg_namespace = "{http://www.w3.org/2000/svg}"

        # remove svg: prefix for the ET.tostring(...) method
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        if svg_root.tag != svg_namespace + "svg":
            raise ValueError("Not a svg")

        geometry: Geometry = Geometry()

        for element in svg_root:
            tag = element.tag.split(svg_namespace)[-1]
            try:
                match tag:
                    case (
                        "line"
                        | "path"
                        | "rect"
                        | "circle"
                        | "polygon"
                        | "polyline"
                        | "ellipse"
                    ):
                        paths, _ = svg.svgstr2paths(  # type: ignore
                            ET.tostring(element, encoding="unicode")
                        )
                        if len(paths) != 1:
                            raise Exception(
                                f"SVG element '{element}' does not contain exactly one svg element"
                            )
                        path = paths[0]
                        top_points, bottom_points = svg_paths_to_points(path, path)

                        color = (
                            svg_color_to_rgba(element.attrib["stroke"])
                            if "stroke" in element.attrib
                            else (0, 0, 0, 255)
                        )
                        cut_depth: float = (
                            self._5dof_color_to_percentage(color)
                            * self.material_thickness
                        )

                        if math.isclose(cut_depth, 0):
                            cut_depth = self.material_thickness

                        cuts = points_to_trapezoids(
                            bottom_points=self._transform_points(bottom_points),
                            top_points=self._transform_points(top_points),
                            material_height=cut_depth,
                        )
                        geometry.add_cuts(cuts)
                    case "g":
                        if len(element) != 2:
                            raise ValueError(
                                f"Group contains {len(element)} elements, not 2."
                            )

                        elem1, elem2 = element
                        second_is_top: bool = (
                            compare_rgba_tuples(
                                svg_color_to_rgba(elem2.attrib["stroke"]), TOP_COLOR
                            )
                            < 20
                        )
                        top_element = elem2 if second_is_top else elem1
                        bottom_element = elem1 if second_is_top else elem2

                        top_path, _ = svg.svgstr2paths(  # type: ignore
                            ET.tostring(top_element, encoding="unicode")
                        )
                        bottom_path, _ = svg.svgstr2paths(  # type: ignore
                            ET.tostring(bottom_element, encoding="unicode")
                        )

                        bottom_points, top_points = svg_paths_to_points(
                            bottom_path[0], top_path[0]
                        )

                        if len(bottom_points) == 0 and len(top_points) == 0:
                            continue

                        bottom_color = svg_color_to_rgba(
                            bottom_element.attrib["stroke"]
                        )
                        cut_depth: float = (
                            self._5dof_color_to_percentage(bottom_color)
                            * self.material_thickness
                        )

                        cuts = points_to_trapezoids(
                            self._transform_points(bottom_points),
                            self._transform_points(top_points),
                            cut_depth,
                        )
                        geometry.add_cuts(cuts)
                    case _:
                        raise ValueError(f"Unknown tag {tag}")
            except Exception as e:
                if element.tag != "g":
                    element.attrib["stroke"] = "red"
                else:
                    for el in element:
                        el.attrib["stroke"] = "red"
                tree = ET.ElementTree(svg_root)
                tree.write("error.svg")

                raise e
        return geometry
