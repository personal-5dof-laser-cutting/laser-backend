from Geometry3D import (
    Point,
    Line,
    Vector,
    x_unit_vector,
    y_unit_vector,
    Visualizer,
    ConvexPolygon,
    Segment,
)
import math


def segment_to_line(seg: Segment) -> Line:
    return Line(seg.start_point, seg.end_point)


class Geometry:
    def __init__(self, material_thickness: float) -> None:
        self.cuts: list[TrapezoidalCut] = []
        self.material_thickness: float = material_thickness


class Configuration:
    def __init__(self, x: float, y: float, alpha: float, beta: float) -> None:
        self.x: float = x
        self.y: float = y
        self.alpha_deg: float = alpha
        self.beta_deg: float = beta

    @property
    def alpha_rad(self) -> float:
        return math.radians(self.alpha_deg)

    @property
    def beta_rad(self) -> float:
        return math.radians(self.beta_deg)

    @classmethod
    def from_segment(cls, line: Segment) -> "Configuration":
        direction_vector: Vector = Vector(line.start_point, line.end_point)
        x, y, z = direction_vector
        xz_vector: Vector = Vector(x, 0, z)
        yz_vector: Vector = Vector(0, y, z)
        alpha: float = (
            yz_vector.angle(x_unit_vector()) if yz_vector != Vector.zero() else 0
        )
        beta: float = (
            xz_vector.angle(y_unit_vector()) if xz_vector != Vector.zero() else 0
        )

        return Configuration(x, y, math.degrees(alpha), math.degrees(beta))

    def __str__(self) -> str:
        return f"Configuration(x={self.x}, y={self.y}, alpha={self.alpha_deg}, beta={self.beta_deg})"

    def to_segment(self, cut_depth: float, material_height: float) -> Segment:
        start_point: Point = Point(self.x, self.y, material_height)
        direction_vector: Vector = Vector(
            math.tan(self.alpha_rad) * cut_depth,
            math.tan(self.beta_rad) * cut_depth,
            cut_depth,
        )

        return Segment(start_point, direction_vector)


class TrapezoidalCut:
    """
    Represents a trapezoidal cut through a material, defined by four corner points.
    Provides methods for validation, geometric manipulation, and intersection checks.
    """

    def __init__(
        self, start_upper: Point, end_upper: Point, start_lower: Point, end_lower: Point
    ) -> None:
        """
        Initialize the geometry object with four corner points and perform validation.

        The upper segment (start_upper and end_upper) must lie on the upper surface of the material. The lower segment (start_lower and end_lower) must be in the material or at the lower surface.

        Parameters
        ----------
        start_upper (Point)
            The starting point of the upper edge of the trapezoid.
        end_upper (Point)
            The ending point of the upper edge of the trapezoid.
        start_lower (Point)
            The starting point of the lower edge of the trapezoid.
        end_lower (Point)
            The ending point of the lower edge of the trapezoid.

        Raises
        ------
        ValueError
            If the provided points do not form a valid trapezoid or the cut configuration is invalid.
        """
        self._start_upper: Point = start_upper
        self._start_lower: Point = start_lower
        self._end_upper: Point = end_upper
        self._end_lower: Point = end_lower

        self._is_valid_trapezoid()
        self._is_valid_cut()

    @classmethod
    def from_configurations(
        cls,
        start_config: Configuration,
        end_config: Configuration,
        cut_depth: float,
        material_height: float,
    ) -> "TrapezoidalCut":
        start_segment: Segment = start_config.to_segment(cut_depth, material_height)
        end_segment: Segment = end_config.to_segment(cut_depth, material_height)

        return TrapezoidalCut(
            start_segment.start_point,
            end_segment.start_point,
            start_segment.end_point,
            end_segment.end_point,
        )

    def _is_valid_trapezoid(self) -> None:
        upper = segment_to_line(self.upper_segment)
        lower = segment_to_line(self.lower_segment)
        assert upper.parallel(lower)

    def _is_valid_cut(self) -> None:
        # The z-values must be exactly the same; otherwise, other calculations may fail.
        assert self._start_upper.z == self._end_upper.z
        assert self._start_lower.z == self._end_lower.z

        # Check if the cut depth is equal or less than the material height.
        assert self._start_lower.z >= 0.0 and self._end_lower.z >= 0.0

    @property
    def start_lower(self) -> Point:
        return self._start_lower

    @property
    def end_lower(self) -> Point:
        return self._end_lower

    @property
    def start_upper(self) -> Point:
        return self._start_upper

    @property
    def end_upper(self) -> Point:
        return self._end_upper

    @property
    def cut_depth(self) -> float:
        return self._start_upper.z - self._start_lower.z

    @cut_depth.setter
    def cut_depth(self, value: float):
        current_depth: float = self.cut_depth

        dz: float = current_depth - value
        move_vector: Vector = Vector(0, 0, dz)

        self._start_lower.move(move_vector)
        self._end_lower.move(move_vector)

        self._is_valid_cut()

    @property
    def upper_segment(self) -> Segment:
        return Segment(self._start_upper, self._end_upper)

    @property
    def lower_segment(self) -> Segment:
        return Segment(self._start_lower, self._end_lower)

    @property
    def start_segment(self) -> Segment:
        return Segment(self._start_upper, self._start_lower)

    @property
    def end_segment(self) -> Segment:
        return Segment(self._end_upper, self._end_lower)

    @property
    def start_configuration(self) -> Configuration:
        return Configuration.from_segment(self.start_segment)

    @property
    def end_configuration(self) -> Configuration:
        return Configuration.from_segment(self.end_segment)

    def flip_direction(self):
        """Flip the cut direction by swapping its start and end endpoints."""

        self._start_lower, self._end_lower = self._end_lower, self._start_lower
        self._start_upper, self._end_upper = self._end_upper, self._start_upper

    def polygon(self) -> ConvexPolygon:
        """Return a geometry3d ConvexPolygon representation of the trapezoid."""
        return ConvexPolygon(
            (self._start_upper, self._end_upper, self._start_lower, self._end_lower)
        )

    def intersects(self, other: "TrapezoidalCut") -> bool:
        """Checks if two trapezoids intersect."""
        return self.polygon().intersection(other.polygon()) is not None

    def show(self):
        """Debug function that plots the Trapezoid using matplotlib."""
        r = Visualizer()
        r.add((t.polygon(), "r", 1), normal_length=0)
        r.show()

    def move(self, v: Vector):
        self._start_lower.move(v)
        self._start_upper.move(v)
        self._end_lower.move(v)
        self._end_upper.move(v)

        self._is_valid_cut()


if __name__ == "__main__":
    t = TrapezoidalCut(Point(0, 0, 1), Point(1, 0, 1), Point(0, 0, 0), Point(1.2, 0, 0))

    print(t.cut_depth)
    t.show()
    t.cut_depth = 0.2
    t.show()

    print(t._start_upper)
    print(t._start_lower)

    # c = Configuration.from_line(Line(Point(0,0,0), Point(1,0,0)))
    # print(c)
