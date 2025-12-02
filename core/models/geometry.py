from Geometry3D import (
    Point,
    Line,
    Vector,
    ConvexPolygon,
    x_unit_vector,
    y_unit_vector,
    Visualizer,
    Segment,
    origin,
)
import math
from copy import copy


def segment_to_line(seg: Segment) -> Line:
    return Line(seg.start_point, seg.end_point)


class Geometry:
    def __init__(self) -> None:
        self.cuts: list[TrapezoidalCut] = []

    def add_cut(self, cut: TrapezoidalCut):
        self.cuts.append(cut)

    def add_cut_from_configurations(
        self, start_config: Configuration, end_config: Configuration, cut_depth: float
    ):
        cut = TrapezoidalCut.from_configurations(start_config, end_config, cut_depth)
        self.add_cut(cut)

    def show_debug(self):
        vis = Visualizer()
        for cut in self.cuts:
            cut.plot_debug(vis)

        vis.add((origin(), "b", 5))
        vis.show()


class Configuration:
    """
    Representation of a laser cutter configuration with two rotation axes.

    Attributes
    ----------
    x : float
        Offset in mm on the x axis
    y : float
        Offset in mm on the y axis
    alpha_deg : float
        Rotation around the x axis in degrees. 0 points downwards and positive is CCW.
    beta_deg : float
        Rotation around the y axis in degrees. 0 points downwards and positve is CCW.
    """

    def __init__(self, x: float, y: float, alpha: float, beta: float) -> None:
        self.x: float = x
        self.y: float = y
        self.alpha: float = alpha
        self.beta: float = beta

        self._validate_angles()

    def _validate_angles(self):
        if abs(self.alpha) >= math.radians(90):
            raise ValueError(
                "Alpha angle over limits (-90° <= math.degrees(alpha) <= 90°)"
            )
        if abs(self.beta) >= math.radians(90):
            raise ValueError(
                "Beta angle over limits (-90° <= math.degrees(beta) <= 90°)"
            )

    @classmethod
    def from_segment(cls, segment: Segment) -> "Configuration":
        direction_vector: Vector = Vector(segment.start_point, segment.end_point)
        start_point: Point = segment.start_point
        x, y, z = direction_vector
        xz_vector: Vector = Vector(x, 0, z)
        yz_vector: Vector = Vector(0, y, z)
        alpha: float = (
            -(yz_vector.angle(y_unit_vector()) - math.pi / 2)
            if yz_vector != Vector.zero()
            else 0
        )
        beta: float = (
            -(xz_vector.angle(x_unit_vector()) - math.pi / 2)
            if xz_vector != Vector.zero()
            else 0
        )

        return Configuration(start_point.x, start_point.y, alpha, beta)

    def __str__(self) -> str:
        return f"Configuration(x={self.x}, y={self.y}, alpha={self.alpha}, beta={self.beta})"

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Configuration)
            and math.isclose(self.x, other.x)
            and math.isclose(self.y, other.y)
            and math.isclose(self.alpha, other.alpha)
            and math.isclose(self.beta, other.beta)
        )

    def to_segment(self, cut_depth: float) -> Segment:
        start_point: Point = Point(self.x, self.y, 0)
        direction_vector: Vector = Vector(
            math.tan(self.beta) * cut_depth,
            math.tan(self.alpha) * cut_depth,
            -cut_depth,
        )

        return Segment(start_point, direction_vector)


class TrapezoidalCut:
    """
    Represents a trapezoidal cut through a material, defined by four corner points.
    Provides methods for validation, geometric manipulation, and intersection checks.
    """

    def __init__(
        self, start_top: Point, end_top: Point, start_bottom: Point, end_bottom: Point
    ):
        """
        Initialize the geometry object with four corner points and perform validation.

        The top segment (start_top and end_top) must lie on z=0. The bottom segment (start_bottom and end_bottom) must be below the xy-plane and the -z coordinate is the cut depth.

        Parameters
        ----------
        start_top (Point)
            The starting point of the top edge of the trapezoid.
        end_top (Point)
            The ending point of the top edge of the trapezoid.
        start_bottom (Point)
            The starting point of the bottom edge of the trapezoid.
        end_bottom (Point)
            The ending point of the bottom edge of the trapezoid.

        Raises
        ------
        ValueError
            If the provided points do not form a valid trapezoid or the cut configuration is invalid.
        """
        self._start_top: Point = start_top
        self._start_bottom: Point = start_bottom
        self._end_top: Point = end_top
        self._end_bottom: Point = end_bottom

        self._validate_cut()

    @classmethod
    def from_configurations(
        cls, start_config: Configuration, end_config: Configuration, cut_depth: float
    ) -> "TrapezoidalCut":
        start_segment: Segment = start_config.to_segment(cut_depth)
        end_segment: Segment = end_config.to_segment(cut_depth)

        return TrapezoidalCut(
            start_segment.start_point,
            end_segment.start_point,
            start_segment.end_point,
            end_segment.end_point,
        )

    def _validate_trapezoid(self) -> None:
        top_line = segment_to_line(self.top_segment())
        bottom_line = segment_to_line(self.bottom_segment())

        if not top_line.parallel(bottom_line):
            raise ValueError(
                "The upper and lower points do not form two parallel lines."
            )

    def _validate_cut(self) -> None:
        self._validate_trapezoid()

        if self.start_top.z != 0 and self.end_top.z != 0:
            raise ValueError("The upper points must be at z=0.")

        # The z-values must be exactly the same; otherwise, other calculations may fail.
        if self.start_bottom.z != self.end_bottom.z:
            raise ValueError("The lower points must be on the same z height.")

        # Check if the cut depth is not zero
        if self.start_bottom.z >= 0.0 or self.end_bottom.z >= 0.0:
            raise ValueError("The lower points must not have negative z-values.")

    @property
    def start_bottom(self) -> Point:
        return self._start_bottom

    @property
    def end_bottom(self) -> Point:
        return self._end_bottom

    @property
    def start_top(self) -> Point:
        return self._start_top

    @property
    def end_top(self) -> Point:
        return self._end_top

    @property
    def cut_depth(self) -> float:
        return self._start_top.z - self._start_bottom.z

    def top_segment(self) -> Segment:
        return Segment(self.start_top, self.end_top)

    def bottom_segment(self) -> Segment:
        return Segment(self.start_bottom, self.end_bottom)

    def start_segment(self) -> Segment:
        return Segment(self.start_top, self.start_bottom)

    def end_segment(self) -> Segment:
        return Segment(self.end_top, self.end_bottom)

    def start_configuration(self) -> Configuration:
        return Configuration.from_segment(self.start_segment())

    def end_configuration(self) -> Configuration:
        return Configuration.from_segment(self.end_segment())

    def flip_direction(self) -> TrapezoidalCut:
        """Flip the cut direction by swapping its start and end endpoints."""
        return TrapezoidalCut(
            self.end_top,
            self.start_top,
            self.end_bottom,
            self.start_bottom,
        )

    def polygon(self) -> ConvexPolygon:
        """Return a geometry3d ConvexPolygon representation of the trapezoid."""
        return ConvexPolygon(
            (self.start_top, self.end_top, self.start_bottom, self.end_bottom)
        )

    def points(self) -> list[Point]:
        return [self.start_top, self.end_top, self.start_bottom, self.end_bottom]

    def intersects(self, other: "TrapezoidalCut") -> bool:
        """Checks if two cuts intersect."""
        return self.intersection(other) is not None

    def intersection(
        self, other: TrapezoidalCut
    ) -> None | Segment | Line | ConvexPolygon:
        return self.polygon().intersection(other.polygon)

    def plot_debug(self, visualizer, color="r"):
        """Debug function that plots the cut using matplotlib."""
        visualizer.add((self.polygon(), color, 1), normal_length=0)

    def move(self, v: Vector) -> TrapezoidalCut:
        """Translate the cut using a Vector."""

        return TrapezoidalCut(
            copy(self.start_top).move(v),
            copy(self.end_top).move(v),
            copy(self.start_bottom).move(v),
            copy(self.end_bottom).move(v),
        )


if __name__ == "__main__":
    cut_depth = 2.0
    geo = Geometry()

    c1 = Configuration(-1, 0, 0, 0)
    c2 = Configuration(1, 0, 0, math.radians(45))
    geo.add_cut_from_configurations(c1, c2, cut_depth)

    c3 = Configuration(1, -1, math.radians(-20), math.radians(45))
    geo.add_cut_from_configurations(c2, c3, cut_depth)

    c4 = Configuration(-1, -1, math.radians(-20), math.radians(0))
    geo.add_cut_from_configurations(c3, c4, cut_depth)

    geo.show_debug()
