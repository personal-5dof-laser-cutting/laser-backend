"""Reads an SVG file into the line groups that SVG5DOF is built from.

This is the document layer of the importer. It is concerned only with structure -
which elements are drawable and how they are grouped - and leaves every question
of meaning (which line is the entry, how deep the cut goes) to
``line_attributes``.
"""

import io
from dataclasses import dataclass

from svgelements import SVG, Color, Group, Path, Shape

from core.modules.svg5dof_importer.cut_builder import to_path

# The lines of one edge profile. A single line is an ungrouped through cut, two
# lines describe a slanted cut, and more than two is not supported yet.
type LineGroup = list["SvgLine"]

# SVG.parse resolves absolute units and the viewport against this, which is a
# property of the file rather than of the machine. It is deliberately unrelated to
# the importer's `dpi`, which only scales the finished geometry into millimetres.
_PARSE_PPI = 72


@dataclass(frozen=True, slots=True)
class SvgLine:
    """A drawable shape from the document, together with its SVG5DOF markup."""

    shape: Shape

    @property
    def classes(self) -> frozenset[str]:
        return frozenset(self.shape.values.get("class", "").split())  # pyright: ignore[reportOptionalMemberAccess]
        # self.shape.values will never end up being None

    @property
    def stroke(self) -> Color:
        return self.shape.stroke

    def to_path(self) -> Path:
        return to_path(self.shape)


@dataclass(frozen=True, slots=True)
class SvgDocument:
    """A parsed SVG, reduced to its bounding box and its line groups."""

    height: float
    scale_height: bool
    line_groups: list[LineGroup]

    @classmethod
    def parse(cls, data: str) -> "SvgDocument":
        svg: SVG = SVG.parse(io.StringIO(data), reify=True, ppi=_PARSE_PPI)

        # Taken over the whole document, before dropping undrawable elements, so
        # that unstroked geometry still contributes to the origin.
        if svg.viewbox is not None and svg.viewbox.height is not None:
            height: float = svg.viewbox.height
            scale_height = False
        elif (bbox := svg.bbox()) is not None:
            height: float = bbox[3]
            scale_height = True
        else:
            raise ValueError("SVG view box and bounding box is not identifiable")

        # The root itself is never an edge profile: a flat export of many ungrouped
        # lines is a set of through cuts, not one oversized group.
        line_groups = [
            entry if isinstance(entry, list) else [entry] for entry in _collect(svg)
        ]
        return cls(height=height, scale_height=scale_height, line_groups=line_groups)


def _collect(container: Group) -> list["SvgLine | LineGroup"]:
    """Flattens a container into loose lines and edge-profile groups.

    A stroked shape becomes a line. A nested group becomes one edge profile if it
    resolves to nothing but lines and holds at least two of them; otherwise its
    contents are hoisted into this level, which is what keeps a group that mixes an
    already-resolved profile with loose lines from being mistaken for a profile.
    """
    collected: list[SvgLine | LineGroup] = []
    for element in container:
        if isinstance(element, Shape):
            if element.stroke.value is not None:
                collected.append(SvgLine(element))
        elif isinstance(element, Group) and len(element) > 0:
            contents = _collect(element)
            if len(contents) >= 2 and all(
                isinstance(entry, SvgLine) for entry in contents
            ):
                collected.append(contents)  # type: ignore[arg-type]
            else:
                collected.extend(contents)
    return collected
