"""Turns a pair of SVG paths into machine-space cuts.

This is the geometry layer of the SVG5DOF importer. It knows nothing about the
SVG5DOF format itself: it is handed a top path, a bottom path and a cut depth,
and it samples them into matching point lists and stitches those into
``TrapezoidalCut``s.

Top and bottom are kept in that order throughout - parameters, return values and
locals - because swapping them silently produces upside-down cuts.
"""

import logging
import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from Geometry3D import Point
from svgelements import (
    Arc,
    Close,
    CubicBezier,
    Line,
    Move,
    Path,
    PathSegment,
    QuadraticBezier,
    Shape,
)

from core.models.geometry import TrapezoidalCut

log = logging.getLogger("SVG5DOF")

INCH_TO_MM: Final[float] = 25.4

# A vertex of a cut: the same position on the top and on the bottom surface.
type Vertex = tuple["Point2D", "Point2D"]


@dataclass(frozen=True, eq=False)
class Point2D:
    """A point in the SVG plane, before or after conversion to machine mm."""

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
        # Deliberately tolerant: sampled points that should coincide rarely do so
        # exactly. Defining __eq__ here also leaves Point2D unhashable.
        return (
            isinstance(other, Point2D)
            and math.isclose(self.x, other.x)
            and math.isclose(self.y, other.y)
        )


@dataclass(frozen=True, slots=True)
class CoordinateTransform:
    """Maps SVG user units (origin top left) to machine mm (origin bottom left)."""

    scale: float
    min_x: float
    max_y: float
    x_offset: float
    y_offset: float

    def apply(self, point: Point2D) -> Point2D:
        return Point2D(
            (point.x - self.min_x) * self.scale + self.x_offset,
            (self.max_y - point.y) * self.scale + self.y_offset,
        )

    def apply_all(self, points: Iterable[Point2D]) -> list[Point2D]:
        return [self.apply(point) for point in points]


def to_path(shape: Shape) -> Path:
    """Converts any shape (including a ``Path``) into a fresh, reified path.

    The copy matters: sampling mutates the path, so handing out the element from
    the parsed document would let repeated visits accumulate segments.
    """
    path = Path(shape)
    path.reify()
    return path


def sample_paths(
    top_path: Path, bottom_path: Path, resolution: float = 1
) -> tuple[list[Point2D], list[Point2D]]:
    """Samples two paths into point lists that line up index by index.

    ``resolution`` is the target spacing in SVG user units, not mm - at 72 dpi one
    unit is roughly 0.35 mm.
    """
    # Closing both paths before counting segments keeps the two sides aligned:
    # direct_close() inserts a segment for shapes whose end does not meet its start.
    top_path.direct_close()
    bottom_path.direct_close()
    top_path.validate_connections()
    bottom_path.validate_connections()

    top_segments = _drawable_segments(top_path)
    bottom_segments = _drawable_segments(bottom_path)
    if len(top_segments) != len(bottom_segments):
        raise ValueError(
            "Top and bottom path do not have the same number of segments. "
            f"({len(top_segments)} != {len(bottom_segments)})"
        )

    top_points: list[Point2D] = []
    bottom_points: list[Point2D] = []
    for top_segment, bottom_segment in zip(top_segments, bottom_segments):
        segment_top, segment_bottom = _sample_segment_pair(
            top_segment, bottom_segment, resolution
        )
        top_points.extend(segment_top)
        bottom_points.extend(segment_bottom)

    return top_points, bottom_points


def build_trapezoids(
    top_points: list[Point2D], bottom_points: list[Point2D], cut_depth: float
) -> list[TrapezoidalCut]:
    """Stitches consecutive sampled vertices into cuts of the given depth."""
    if len(top_points) < 2 or len(bottom_points) < 2:
        raise ValueError("There must be at least two top and two bottom points.")
    if len(top_points) != len(bottom_points):
        raise ValueError(
            f"There must be an equal amount of top ({len(top_points)} points) and "
            f"bottom ({len(bottom_points)} points) points."
        )

    vertices: list[Vertex] = list(zip(top_points, bottom_points))
    cuts: list[TrapezoidalCut] = []
    for start, end in pairwise(vertices):
        # Adjacent segments repeat the vertex they share.
        if start == end:
            continue
        cut = _build_trapezoid(start, end, cut_depth)
        if cut is not None:
            cuts.append(cut)
    return cuts


def _drawable_segments(path: Path) -> list[PathSegment]:
    """Drops the segments that carry no material: pen moves and closing markers."""
    return [segment for segment in path if not isinstance(segment, (Move, Close))]


def _sample_segment_pair(
    top_segment: PathSegment, bottom_segment: PathSegment, resolution: float
) -> tuple[list[Point2D], list[Point2D]]:
    match top_segment, bottom_segment:
        case Line(), Line():
            return (
                [Point2D.from_complex(p) for p in top_segment],
                [Point2D.from_complex(p) for p in bottom_segment],
            )
        case (
            (Arc(), Arc())
            | (CubicBezier(), CubicBezier())
            | (QuadraticBezier(), QuadraticBezier())
        ):
            # Both sides are subdivided at the same parameter values so that the
            # resulting points still correspond one to one.
            longest = max(top_segment.length(), bottom_segment.length())
            count = max(math.ceil(longest / resolution), 2)
            offsets = [step / (count - 1) for step in range(count)]
            return (
                [Point2D.from_complex(top_segment.point(t)) for t in offsets],
                [Point2D.from_complex(bottom_segment.point(t)) for t in offsets],
            )
        case _:
            raise ValueError(
                "Top and bottom segments have mismatched types: "
                f"{type(top_segment).__name__} vs {type(bottom_segment).__name__}"
            )


def _build_trapezoid(
    start: Vertex, end: Vertex, cut_depth: float
) -> TrapezoidalCut | None:
    """Builds one cut, or returns ``None`` if these four points cannot form one."""
    start_top, start_bottom = start
    end_top, end_bottom = end
    try:
        try:
            return TrapezoidalCut(
                start_top.to_point3d(0),
                end_top.to_point3d(0),
                start_bottom.to_point3d(-cut_depth),
                end_bottom.to_point3d(-cut_depth),
            )
        except ValueError:
            # The bottom line is drawn in the opposite direction from the top one.
            return TrapezoidalCut(
                start_top.to_point3d(0),
                end_top.to_point3d(0),
                end_bottom.to_point3d(-cut_depth),
                start_bottom.to_point3d(-cut_depth),
            )
    except Exception as e:
        log.warning("Skipped points because they do not form valid trapezoids: %s", e)
        return None
