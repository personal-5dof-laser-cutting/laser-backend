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


def segment_to_line(seg: Segment) -> Line:
    return Line(seg.start_point, seg.end_point)


class Geometry:
    def __init__(self, material_height: float) -> None:
        self.cuts: list[TrapezoidalCut] = []
        self.material_height: float = material_height

    def add_cut(self, cut: TrapezoidalCut):
        self.cuts.append(cut)

    def add_cut_from_configurations(
        self, start_config: Configuration, end_config: Configuration, cut_depth: float
    ):
        cut = TrapezoidalCut.from_configurations(
            start_config, end_config, cut_depth, self.material_height
        )
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
        self.alpha_deg: float = alpha
        self.beta_deg: float = beta

        self._validate_angles()

    def _validate_angles(self):
        if abs(self.alpha_deg) > 90:
            raise ValueError("Alpha angle over limits (-90° <= alpha <= 90°)")
        if abs(self.beta_deg) > 90:
            raise ValueError("Beta angle over limits (-90° <= beta <= 90°)")

    @property
    def alpha_rad(self) -> float:
        return math.radians(self.alpha_deg)

    @property
    def beta_rad(self) -> float:
        return math.radians(self.beta_deg)

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

        return Configuration(
            start_point.x, start_point.y, math.degrees(alpha), math.degrees(beta)
        )

    def __str__(self) -> str:
        return f"Configuration(x={self.x}, y={self.y}, alpha={self.alpha_deg}, beta={self.beta_deg})"

    def to_segment(self, cut_depth: float, material_height: float) -> Segment:
        start_point: Point = Point(self.x, self.y, material_height)
        direction_vector: Vector = Vector(
            math.tan(self.beta_rad) * cut_depth,
            math.tan(self.alpha_rad) * cut_depth,
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
        self._start_top: Point = start_top
        self._start_bottom: Point = start_bottom
        self._end_top: Point = end_top
        self._end_bottom: Point = end_bottom

        self._validate_cut()

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

    def _validate_trapezoid(self) -> None:
        top_line = segment_to_line(self.top_segment())
        bottom_line = segment_to_line(self.bottom_segment())

        if not top_line.parallel(bottom_line):
            raise ValueError(
                "The upper and lower points do not form two parallel lines."
            )

    def _validate_cut(self) -> None:
        self._validate_trapezoid()

        # The z-values must be exactly the same; otherwise, other calculations may fail.
        if self.start_top.z != self.end_top.z:
            raise ValueError("The upper points must be on the same z height.")
        if self.start_bottom.z != self.end_bottom.z:
            raise ValueError("The lower points must be on the same z height.")

        # Check if the cut depth is equal or less than the material height.
        if self.start_bottom.z < 0.0 or self.end_bottom.z < 0.0:
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
            self.start_top.move(v),
            self.end_top.move(v),
            self.start_bottom.move(v),
            self.end_bottom.move(v),
        )


if __name__ == "__main__":
    material_height = 2.0
    cut_depth = 2.0
    geo = Geometry(material_height)

    c1 = Configuration(-1, 0, 0, 0)
    c2 = Configuration(1, 0, 0, 45)
    geo.add_cut_from_configurations(c1, c2, cut_depth)

    c3 = Configuration(1, -1, -20, 45)
    geo.add_cut_from_configurations(c2, c3, cut_depth)

    c4 = Configuration(-1, -1, -20, 0)
    geo.add_cut_from_configurations(c3, c4, cut_depth)

    geo.show_debug()
