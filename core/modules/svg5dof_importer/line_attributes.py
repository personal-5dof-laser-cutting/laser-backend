"""Works out what a group of SVG lines is supposed to cut.

This is the semantic layer of the importer. It turns the markup on a line group -
either SVG5DOF classes or, in compatibility mode, the stroke colour - into an
``EdgeProfile``: which line lies on the top surface, which on the bottom, and how
deep the cut between them goes.

The two markup styles are separate readers rather than one shared rule, because
they disagree about what counts as malformed. Class markup demands exactly one
entry line and a positive depth; compatibility mode has no way to express either
and falls back on document order instead. Colours are only ever inspected in
compatibility mode: a class-marked group may legitimately use arbitrary strokes.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from svgelements import Color

from core.modules.svg5dof_importer.svg_document import LineGroup, SvgLine

_DEPTH_CLASS_RE = re.compile(r"^depth_(-?\d+(?:\.\d+)?)(mm|%)?$")

# In compatibility mode a light grey stroke means a full-depth cut. Anything
# lighter than this is out of range rather than deeper than a through cut.
_LIGHTEST_STROKE = 0.8


class DepthUnit(StrEnum):
    MILLIMETRES = "mm"
    PERCENT = "%"


@dataclass(frozen=True, slots=True)
class Depth:
    """How far below the top surface a line sits."""

    value: float
    unit: DepthUnit

    def in_mm(self, material_thickness: float) -> float:
        if self.unit is DepthUnit.MILLIMETRES:
            return self.value
        return material_thickness * self.value / 100.0

    @classmethod
    def parse(cls, token: str) -> "Depth | None":
        """Reads a ``depth_`` class, e.g. ``depth_5mm``, ``depth_50%`` or ``depth_50``."""
        match = _DEPTH_CLASS_RE.match(token)
        if match is None:
            return None
        unit = (
            DepthUnit.MILLIMETRES if match.group(2) == "mm" else DepthUnit.PERCENT
        )  # a bare number is relative
        return cls(value=float(match.group(1)), unit=unit)


class LineRole(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"


@dataclass(frozen=True, slots=True)
class LineAttributes:
    """The SVG5DOF markup carried by one line."""

    roles: frozenset[LineRole]
    depth: Depth | None

    @property
    def is_5dof(self) -> bool:
        return bool(self.roles) or self.depth is not None

    @classmethod
    def parse(cls, line: SvgLine) -> "LineAttributes":
        roles: set[LineRole] = set()
        depth: Depth | None = None
        for token in line.classes:
            if token in LineRole:
                roles.add(LineRole(token))
            elif (parsed := Depth.parse(token)) is not None:
                depth = parsed
        return cls(roles=frozenset(roles), depth=depth)


@dataclass(frozen=True, slots=True)
class EdgeProfile:
    """A resolved cut: where it enters the material, where it leaves, how deep."""

    top: SvgLine
    bottom: SvgLine
    cut_depth_mm: float

    @classmethod
    def through_cut(cls, line: SvgLine, material_thickness: float) -> "EdgeProfile":
        """A lone line cuts straight down through the whole material."""
        return cls(top=line, bottom=line, cut_depth_mm=material_thickness)

    @property
    def is_through_cut(self) -> bool:
        return self.top is self.bottom


def read_edge_profile(group: LineGroup, material_thickness: float) -> EdgeProfile:
    """Resolves one group of lines into the cut it describes."""
    match group:
        case [line]:
            return EdgeProfile.through_cut(line, material_thickness)
        case [first, second]:
            reader = _select_reader(group, material_thickness)
            return reader.read(first, second)
        case _:
            raise NotImplementedError(
                "SVG5DOF groups with more than two lines (multi-segment "
                "depth stacks / duplex cuts) are not yet supported."
            )


def _select_reader(group: LineGroup, material_thickness: float) -> "EdgeProfileReader":
    """Class markup wins for the whole group as soon as any one line carries it."""
    if any(LineAttributes.parse(line).is_5dof for line in group):
        return ClassEdgeProfileReader(material_thickness)
    return GrayscaleEdgeProfileReader(material_thickness)


class EdgeProfileReader(ABC):
    """Resolves the two lines of an edge profile into a cut."""

    def __init__(self, material_thickness: float) -> None:
        self.material_thickness = material_thickness

    @abstractmethod
    def read(self, first: SvgLine, second: SvgLine) -> EdgeProfile: ...


class ClassEdgeProfileReader(EdgeProfileReader):
    """Reads ``entry`` / ``exit`` / ``depth_`` classes."""

    def read(self, first: SvgLine, second: SvgLine) -> EdgeProfile:
        first_attributes = LineAttributes.parse(first)
        second_attributes = LineAttributes.parse(second)

        for attributes in (first_attributes, second_attributes):
            if attributes.roles == {LineRole.ENTRY, LineRole.EXIT}:
                raise ValueError("A line cannot be both 'entry' and 'exit'.")

        first_is_entry = LineRole.ENTRY in first_attributes.roles
        if first_is_entry == (LineRole.ENTRY in second_attributes.roles):
            raise ValueError(
                "An SVG5DOF group of two lines must contain exactly one 'entry' line."
            )

        if first_is_entry:
            entry, entry_attributes = first, first_attributes
            other, other_attributes = second, second_attributes
        else:
            entry, entry_attributes = second, second_attributes
            other, other_attributes = first, first_attributes

        self._check_entry_lies_on_the_surface(entry_attributes)
        cut_depth = self._read_cut_depth(other_attributes)

        # The entry line is by definition on the top surface (z=0).
        return EdgeProfile(top=entry, bottom=other, cut_depth_mm=cut_depth)

    def _check_entry_lies_on_the_surface(self, entry: LineAttributes) -> None:
        if entry.depth is None:
            return
        if entry.depth.in_mm(self.material_thickness) != 0.0:
            raise NotImplementedError(
                "Entry lines with a non-zero depth are not yet supported."
            )

    def _read_cut_depth(self, other: LineAttributes) -> float:
        if other.depth is not None:
            # An explicit depth overrides what the role would otherwise imply.
            cut_depth = other.depth.in_mm(self.material_thickness)
        elif LineRole.EXIT in other.roles:
            cut_depth = self.material_thickness
        else:
            raise ValueError(
                "The second line in an SVG5DOF group must be an 'exit' line or "
                "specify a 'depth_' class."
            )

        if cut_depth <= 0:
            raise ValueError(
                f"Resolved cut depth must be positive (got {cut_depth}mm)."
            )
        return cut_depth


class GrayscaleEdgeProfileReader(EdgeProfileReader):
    """Reads stroke lightness, for editors that cannot author CSS classes.

    Black marks the entry line; the depth of the cut is read off how light the
    other line is, up to light grey for a full through cut.
    """

    def read(self, first: SvgLine, second: SvgLine) -> EdgeProfile:
        # With no black line at all, document order decides which is which.
        top, bottom = (
            (first, second) if first.stroke.lightness == 0 else (second, first)
        )
        cut_depth = self.material_thickness * _depth_fraction(bottom.stroke)
        return EdgeProfile(top=top, bottom=bottom, cut_depth_mm=cut_depth)


def _depth_fraction(stroke: Color) -> float:
    """How deep a stroke's lightness reads, as a fraction of a through cut."""
    if stroke.saturation != 0.0:
        raise ValueError("Found non grayscale line in svg.")

    lightness: float = stroke.lightness  # type: ignore
    if lightness > _LIGHTEST_STROKE:
        raise ValueError("Found out of bounds color in svg.")

    return min(lightness / _LIGHTEST_STROKE, 1.0)
