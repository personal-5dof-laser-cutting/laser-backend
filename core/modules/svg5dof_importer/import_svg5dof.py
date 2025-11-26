from dataclasses import dataclass
from typing import Tuple

from Geometry3D import Point
import svgpathtools as svg
import xml.etree.ElementTree as ET

from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module

from PIL.ImageColor import getrgb


TOP_COLOR = (255, 0, 0, 255)  # red
BOTTOM_COLOR = (0, 125, 255, 255)  # blue


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


def compare_tuples(a: tuple, b: tuple) -> float:
    """
    Compare two numeric tuples element-wise and return the sum of absolute differences.
    """
    if len(a) != len(b):
        raise ValueError(f"Tuples must be of same length ({len(a)} != {len(b)})")

    differences = [abs(x - y) for x, y in zip(a, b)]
    return sum(differences)


def svg_elem_to_points(
    element: svg.Line | svg.Path | svg.CubicBezier | svg.Arc | svg.QuadraticBezier,
    num_points: int = 2,
) -> list[Point2D]:
    if num_points < 2:
        raise ValueError("At least two points are required.")

    if element is svg.Line:
        num_points = 2

    points_complex: list[complex] = [
        element.point(t / (num_points - 1)) for t in range(num_points)
    ]

    return [Point2D.from_complex(p_complex) for p_complex in points_complex]


def points_to_trapezoids(
    top_points: list[Point2D], bottom_points: list[Point2D], material_height: float
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


class SVG5DOF_Importer(Module[tuple[str, float], Geometry]):
    dpi = 72
    inch_to_mm = 25.4

    def process(
        self,
        data: Tuple[str, float],
    ) -> Geometry:
        svg_content, material_height = data

        svg_root = ET.fromstring(svg_content)
        svg_namespace = "{http://www.w3.org/2000/svg}"

        # remove svg: prefix for the ET.tostring(...) method
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        if svg_root.tag != svg_namespace + "svg":
            raise ValueError("Not a svg")

        geometry: Geometry = Geometry()

        for element in svg_root:
            tag = element.tag.split(svg_namespace)[-1]
            match tag:
                case "line" | "path":
                    paths, _ = svg.svgstr2paths(
                        ET.tostring(element, encoding="unicode")
                    )  # type: ignore
                    points = svg_elem_to_points(paths[0])
                    cuts = points_to_trapezoids(
                        top_points=points,
                        bottom_points=points,
                        material_height=material_height,
                    )
                    geometry.add_cuts(cuts)
                case "g":
                    if len(element) != 2:
                        raise ValueError(
                            f"Group contains {len(element)} elements, not 2."
                        )

                    elem1, elem2 = element
                    second_is_top: bool = (
                        compare_tuples(
                            svg_color_to_rgba(elem2.attrib["stroke"]), TOP_COLOR
                        )
                        < 20
                    )

                    top_path, _ = svg.svgstr2paths(  # type: ignore
                        ET.tostring(
                            elem2 if second_is_top else elem1, encoding="unicode"
                        )
                    )
                    bottom_path, _ = svg.svgstr2paths(  # type: ignore
                        ET.tostring(
                            elem1 if second_is_top else elem2, encoding="unicode"
                        )
                    )

                    bottom_points, top_points = (
                        svg_elem_to_points(bottom_path[0]),
                        svg_elem_to_points(top_path[0]),
                    )

                    cuts = points_to_trapezoids(
                        top_points, bottom_points, material_height
                    )
                    geometry.add_cuts(cuts)
                case _:
                    raise ValueError(f"Unknown tag {tag}")

        return geometry
