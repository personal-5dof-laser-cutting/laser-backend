from typing import Tuple

import numpy as np
from Geometry3D import Point
from svgpathtools import Arc, CubicBezier, Path, svgstr2paths

from core.models.geometry import Geometry, TrapezoidalCut
from core.pipeline.base import Module


def extract_rgb(stroke_value: str) -> Tuple[int, int, int]:
    if stroke_value.startswith("rgb"):
        numbers = stroke_value[4:-1]
        parts = numbers.split(",")
        return int(parts[0]), int(parts[1]), int(parts[2])
    else:
        print("Error in extract_rgb")
        return 0, 0, 0


# getting rgb values from hexcode/named colors
def get_color_rgb(color: str) -> tuple[int, int, int]:
    if color == "gray":
        return int("80", 16), int("80", 16), int("80", 16)
    else:
        if len(color) <= 5:
            return int(color[1], 16), int(color[2], 16), int(color[3], 16)
        return (
            int(color[1] + color[2], 16),
            int(color[3] + color[4], 16),
            int(color[5] + color[6], 16),
        )


def coord_to_tuple(p: complex) -> tuple[float, float]:
    """
    coord is complex like tuple[float, float],
    svg has coords in inch, we have to convert to metric system
    """
    conversion_factor_dots_to_mm = (
        1  # inch_to_mm / dpi # inch_to_mm #1 / dpi * inch_to_mm
    )
    return (
        p.real * conversion_factor_dots_to_mm,
        p.imag * conversion_factor_dots_to_mm,
    )


def get_coords(segment: Path | Arc | CubicBezier) -> list[complex]:
    if isinstance(segment, CubicBezier):
        bezier_path = Path(segment)
        coords = [bezier_path.point(t) for t in np.linspace(0, 1, 32)]
    elif isinstance(segment, Arc):
        coords = []
    else:
        coords = [segment[0], segment[-1]]

    return coords


class SVG5DOF_Importer(Module[tuple[str, float], Geometry]):
    dpi = 72
    inch_to_mm = 25.4

    def process(
        self,
        data: Tuple[str, float],
    ) -> Geometry:
        svg_lines = []
        svg_lines_grouped = []

        geo: Geometry = Geometry()
        svg_content, material_height = data
        for line in svg_content.split("\n"):
            svg_lines.append(line.strip())

        is_in_group = False

        # grouping angled lines in 2-dimensional array
        # lines without angle are cloned to calculate 0° angle
        # stored as strings directly from file
        i = 0
        while i < len(svg_lines):
            if "line" in svg_lines[i]:
                line2 = []
                if not is_in_group:
                    line2.append(svg_lines[i])
                    line2.append(svg_lines[i])
                    svg_lines_grouped.append(line2)
                else:
                    line2.append(svg_lines[i])
                    i += 1
                    line2.append(svg_lines[i])
                    svg_lines_grouped.append(line2)
                    is_in_group = False
            elif (
                "<g>" in svg_lines[i]
                and i + 3 < len(svg_lines)
                and "</g>" in svg_lines[i + 3]
            ):
                is_in_group = True
            i += 1

        for i in range(len(svg_lines_grouped)):
            ln1 = (svg_lines_grouped[i])[0]
            ln2 = (svg_lines_grouped[i])[1]
            ln1, attr1 = svgstr2paths(ln1)  # type: ignore
            ln2, attr2 = svgstr2paths(ln2)  # type: ignore

            stroke1_color = attr1[0].get("stroke", "rgb(0,0,0)")
            stroke2_color = attr2[0].get("stroke", "rgb(0,0,0)")

            r1, g1, b1 = get_color_rgb(stroke1_color)
            r2, g2, b2 = get_color_rgb(stroke2_color)

            rgb_mean1 = (r1 + g1 + b1) / 3

            # slightly different tones of gray allowed
            # differentiating black and gray by brightness
            allowed_variance = 10
            min_brightness = 50

            if (
                abs(r1 - rgb_mean1) < allowed_variance
                and abs(g1 - rgb_mean1) < allowed_variance
                and abs(b1 - rgb_mean1) < allowed_variance
                and rgb_mean1 > min_brightness
            ):
                # this is gray
                if (
                    abs(r2 - r1) < allowed_variance
                    and abs(g2 - g1) < allowed_variance
                    and abs(b2 - b1) < allowed_variance
                ):
                    print("error: two gray lines", r1, g1, b1, r2, g2, b2)
                ln1, ln2 = ln2, ln1
                attr1, attr2 = attr1, attr2
                stroke1_color, stroke2_color = stroke2_color, stroke1_color

            coords1 = []
            coords2 = []

            for segment in ln1[0]:
                coords1.extend(get_coords(segment))

            for segment in ln2[0]:
                coords2.extend(get_coords(segment))

            start1, end1 = coords1[0], coords1[-1]
            start2, end2 = coords2[0], coords2[-1]

            start1, end1 = coord_to_tuple(start1), coord_to_tuple(end1)
            start2, end2 = coord_to_tuple(start2), coord_to_tuple(end2)

            # start and end point for both lines, can be used for creation of trapezoids
            # currently just using start point of second line for calculating unchanging angle
            start1 = Point(start1[0], start1[1], 0)
            end1 = Point(end1[0], end1[1], 0)

            start2 = Point(start2[0], start2[1], -material_height)
            end2 = Point(end2[0], end2[1], -material_height)

            trapezoid = TrapezoidalCut(start1, end1, start2, end2)
            geo.add_cut(trapezoid)

            if start1.distance(end1) < 0.001:
                continue

            # TODO: why not used?
            # diff_mm = (start1.distance(start2) / self.dpi) * self.inch_to_mm
            # miter = math.atan(diff_mm / material_height) / math.pi * 180

            table = round(float(attr1[0].get("data-rotation", -10000)), 4)
            depth = round(float(attr1[0].get("data-depth", 10000)), 4)

            if depth >= material_height:
                depth = 10000

            opacity = float(attr1[0].get("opacity", 1.0))

            if opacity != 1.0:
                continue

            if table == -10000:
                table = None

            if (
                stroke1_color == "#ffffff"
                or stroke1_color == "#fff"
                or stroke1_color == "white"
            ):
                raise NotImplementedError()

            geo.add_cut(trapezoid)

            # TODO: configure output
        geo.show_debug()
        return geo
