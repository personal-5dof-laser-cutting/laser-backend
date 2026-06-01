from itertools import pairwise
from Geometry3D import (
    Plane,
    Point,
    Line,
    Vector,
    ConvexPolygon,
    x_unit_vector,
    y_unit_vector,
    Visualizer,
    Segment,
    origin,
    z_unit_vector,
)
import math
from copy import copy

from numpy import sign


def segment_to_line(seg: Segment) -> Line:
    return Line(seg.start_point, seg.end_point)


class Geometry:
    def __init__(self) -> None:
        self.cuts: list[TrapezoidalCut] = []

    def add_cut(self, cut: TrapezoidalCut):
        self.cuts.append(cut)

    def add_cuts(self, cuts: list[TrapezoidalCut]):
        self.cuts.extend(cuts)

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

    def calculate_travel_cost(self, material_height: float, as_cycle: bool) -> float:
        running_total: float = 0
        for a, b in pairwise(self.cuts):
            running_total += a.travel_time_to(b, material_height)
        if as_cycle:
            running_total += self.cuts[-1].travel_time_to(self.cuts[0], material_height)
        return running_total


class Configuration:
    """
    Representation of a laser cutter configuration with two rotation axes.

    Attributes
    ----------
    x : float
        Offset in mm on the x axis
    y : float
        Offset in mm on the y axis
    alpha : float
        Rotation around the x axis in radians. 0 points downwards and positive points towards positive y.
    beta : float
        Rotation around the y axis in radians. 0 points downwards and positve points towards positive x.
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
    def from_segment(cls, segment: Segment) -> Configuration:
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

    def __hash__(self) -> int:
        return hash(
            (
                round(self.x, 6),
                round(self.y, 6),
                round(self.alpha, 6),
                round(self.beta, 6),
            )
        )

    def to_segment(self, cut_depth: float) -> Segment:
        start_point: Point = Point(self.x, self.y, 0)
        direction_vector: Vector = Vector(
            math.tan(self.beta) * cut_depth,
            math.tan(self.alpha) * cut_depth,
            -cut_depth,
        )

        return Segment(start_point, direction_vector)

    def direction_vector(self) -> Vector:
        y = math.tan(self.alpha)
        x = math.tan(self.beta)
        return Vector(x, y, -1).normalized()

    def travel_time_to(self, other: Configuration, material_height: float) -> float:
        from core.service_container import Container

        return Container.laser_cost.get_cost(self, other, material_height)


class MotorPosition:
    """
    Motor position of a laser cutter configuration with a rotating cut rotation axes.

    Attributes
    ----------
    x : float
        Offset in mm on the x axis
    y : float
        Offset in mm on the y axis
    z : float
        Offset in mm on the z axis
    a : float
        Rotation of the table in radians.
    b : float
        Rotation of the laser head in radians. 0 points downwards and positve points towards positive x.
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        alpha: float,
        beta: float,
        isRadians: bool = False,
    ) -> None:
        if not isRadians:
            alpha = math.radians(alpha)
            beta = math.radians(beta)

        if beta < math.radians(-90) or beta > math.radians(90):
            raise ValueError("b must be between -90° and 90°")

        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)
        self.a: float = float(alpha) % math.radians(360) - math.radians(
            180
        )  # table motor
        self.b: float = float(beta)  # laser head motor

    def __eq__(self, value: object) -> bool:
        if type(value) is not MotorPosition:
            return False
        return all(
            [
                math.isclose(self.x, value.x),
                math.isclose(self.y, value.y),
                math.isclose(self.z, value.z),
                math.isclose(self.a, value.a),
                math.isclose(self.b, value.b),
            ]
        )

    def axes_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "a": self.a,
            "b": self.b,
        }

    def delta(self, other: MotorPosition) -> MotorPosition:
        d_x = abs(self.x - other.x)
        d_y = abs(self.y - other.y)
        if sign(self.b) != sign(other.b):
            d_z = self.z + other.z
        else:
            d_z = abs(self.z - other.z)

        d_a = abs(self.a - other.a)
        if d_a > math.radians(180):
            d_a = math.radians(360) - d_a
        d_b = abs(self.b - other.b)
        return MotorPosition(d_x, d_y, d_z, d_a, d_b)


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
        if self._start_top == self._end_top:
            raise ValueError(
                f"The top points are identical. Distance: {self._start_top.distance(self.end_top)}"
            )
        if self._start_bottom == self._end_bottom:
            raise ValueError(
                f"The bottom points are identical. Distance: {self._start_bottom.distance(self.end_bottom)}"
            )
        top_line = segment_to_line(self.top_segment())
        bottom_line = segment_to_line(self.bottom_segment())

        if not top_line.parallel(bottom_line):
            raise ValueError(
                "The upper and lower points do not form two parallel lines."
            )

        top_dv: Vector = self.top_vector().normalized()
        bottom_dv: Vector = self.bottom_vector().normalized()
        for a, b in zip(top_dv, bottom_dv):  # pyright: ignore[reportArgumentType] | .normalized() always returns a Vector
            if math.isclose(a, 0) or math.isclose(b, 0):
                continue
            if sign(a) != sign(b):
                raise ValueError(
                    "The top and bottom lines point in different directions!"
                )

    def _validate_cut(self) -> None:
        self._validate_trapezoid()

        if self.start_top.z != 0 or self.end_top.z != 0:
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
        # The height of the trapezoid
        return self._start_top.z - self._start_bottom.z

    @property
    def effective_angle_abs(self) -> float:
        # This is the absolute angle of the laser head in a lazy susan configuration
        cut_plane: Plane = Plane(self.start_bottom, self.start_top, self.end_bottom)
        parallel_plane: Plane = Plane(
            self.start_top, self.top_vector(), z_unit_vector()
        )
        return parallel_plane.angle(cut_plane)

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

    def configurations(self) -> list[Configuration]:
        return [self.start_configuration(), self.end_configuration()]

    def top_vector(self) -> Vector:
        return self.end_top.pv() - self.start_top.pv()

    def bottom_vector(self) -> Vector:
        return self.end_bottom.pv() - self.start_bottom.pv()

    def start_vector(self) -> Vector:
        return self.start_bottom.pv() - self.start_top.pv()

    def end_vector(self) -> Vector:
        return self.end_bottom.pv() - self.end_top.pv()

    def flipped_direction(self) -> TrapezoidalCut:
        """Flip the cut direction by swapping its start and end endpoints."""
        return TrapezoidalCut(
            self.end_top,
            self.start_top,
            self.end_bottom,
            self.start_bottom,
        )

    def flipped_vertical(self) -> TrapezoidalCut:
        """Swap top and bottom edge"""
        return TrapezoidalCut(
            self.start_bottom, self.end_bottom, self.start_top, self.end_top
        )

    def polygon(self) -> ConvexPolygon:
        """Return a geometry3d ConvexPolygon representation of the trapezoid."""
        return ConvexPolygon(
            (self.start_top, self.end_top, self.start_bottom, self.end_bottom)
        )

    def plane(self) -> Plane:
        return Plane(self.start_top, self.end_top, self.start_bottom)

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

    def depth(self, x: float) -> float:
        # For x = 0, this method will return the length of the start segment, for x = 1 it returns the length of the end segment
        # For x = 0.5 this will return distance between the middle points of the top and bottom line
        if not 0 <= x <= 1:
            raise ValueError("x must be between 0 and 1 (inclusive)")
        upper_point: Point = Point(self.start_top.pv() + self.top_vector() * x)
        lower_point: Point = Point(self.start_bottom.pv() + self.bottom_vector() * x)
        return upper_point.distance(lower_point)

    def get_slant_angle(self) -> float:
        return self.plane().n[2]

    def is_straight_cut(self) -> bool:
        return math.isclose(self.get_slant_angle(), 0)

    def get_internal_cost(self, material_height: float) -> float:
        from_conf, to_conf = self.configurations()
        return from_conf.travel_time_to(to_conf, material_height)

    def travel_time_to(self, other: TrapezoidalCut, material_height: float) -> float:
        return self.end_configuration().travel_time_to(
            other.start_configuration(), material_height
        )

    def __repr__(self) -> str:
        return f"Cut(({self.start_top.x}, {self.start_top.y}), ({self.end_top.x}, {self.end_top.y}), ({self.start_bottom.x}, {self.start_bottom.y}), ({self.end_bottom.x}, {self.end_bottom.y}), material_height={self.cut_depth})"

    def __eq__(self, other):
        return isinstance(other, TrapezoidalCut) and (
            self.start_top,
            self.end_top,
            self.start_bottom,
            self.end_bottom,
        ) == (
            other.start_top,
            other.end_top,
            other.start_bottom,
            other.end_bottom,
        )

    def __hash__(self) -> int:
        return hash((self.start_top, self.end_top, self.start_bottom, self.end_bottom))


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
