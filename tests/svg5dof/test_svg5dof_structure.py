"""Characterization tests for SVG5DOF import behavior that ``test_svg5dof.py`` misses.

Those tests all use straight lines in trivial documents. The cases here lock the
structural rules instead: how the element tree is grouped, how closed paths and
curves are sampled, and which malformed inputs are tolerated rather than fatal.
"""

import pytest

from core.models.geometry import Geometry
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer

MATERIAL_THICKNESS = 5.0


def _svg(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" '
        f'viewBox="0 0 200 200">{body}</svg>'
    )


def _line(y: float, stroke: str = "#000", **attrs: str) -> str:
    extra = "".join(f' {name}="{value}"' for name, value in attrs.items())
    return f'<line x1="0" y1="{y}" x2="100" y2="{y}" stroke="{stroke}"{extra}/>'


def _import(body: str, material_thickness: float = MATERIAL_THICKNESS) -> Geometry:
    return SVG5DOF_Importer(material_thickness).process(_svg(body))


# A grayscale pair: black is the entry (top) line, #ccc is a full-depth exit.
_PAIR = _line(0) + _line(10, "#ccc")


# --- element tree grouping ------------------------------------------------


@pytest.mark.parametrize(
    "name,body,expected_cuts",
    [
        # The document root is never treated as an edge-profile group, so a flat
        # 3DOF-style export of many ungrouped lines stays a set of through-cuts.
        ("three lines at root", _line(0) + _line(10) + _line(20), 3),
        # A group holding a single line is indistinguishable from an ungrouped line.
        ("group of one", f"<g>{_line(0)}</g>", 1),
        # A group nested in a group still resolves to one slanted cut.
        ("group in group", f"<g><g>{_PAIR}</g></g>", 1),
        # A group mixing a resolved pair with loose lines is flattened, not rejected.
        (
            "nested pair plus loose lines",
            f"<g><g>{_PAIR}</g>{_line(50)}{_line(60)}</g>",
            3,
        ),
        # Unstroked shapes are dropped before the group is sized, so this is a pair.
        (
            "pair plus unstroked line",
            f'<g>{_PAIR}<line x1="0" y1="9" x2="1" y2="9" stroke="none"/></g>',
            1,
        ),
    ],
)
def test_grouping(name: str, body: str, expected_cuts: int):
    assert len(_import(body).cuts) == expected_cuts


def test_flat_group_of_three_lines_is_unsupported():
    """Multi-segment depth stacks / duplex cuts are specified but not implemented."""
    with pytest.raises(NotImplementedError):
        _import(f"<g>{_line(0)}{_line(10)}{_line(20)}</g>")


# --- path sampling --------------------------------------------------------


def test_closed_path_yields_one_cut_per_edge():
    """A rect closes into 4 edges; the shared vertices between them are deduplicated."""
    body = '<rect x="10" y="10" width="50" height="50" stroke="#000" fill="none"/>'
    assert len(_import(body).cuts) == 4


@pytest.mark.parametrize(
    "name,body,expected_cuts",
    [
        (
            "cubic bezier pair",
            '<g><path d="M 0 0 C 10 40 60 40 70 0" stroke="#000" fill="none"/>'
            '<path d="M 5 0 C 15 40 65 40 75 0" stroke="#ccc" fill="none"/></g>',
            99,
        ),
        (
            "arc pair",
            '<g><path d="M 0 0 A 30 30 0 0 1 60 0" stroke="#000" fill="none"/>'
            '<path d="M 5 0 A 30 30 0 0 1 65 0" stroke="#ccc" fill="none"/></g>',
            94,
        ),
        (
            "ungrouped circle",
            '<circle cx="50" cy="50" r="30" stroke="#000" fill="none"/>',
            188,
        ),
    ],
)
def test_curves_are_sampled(name: str, body: str, expected_cuts: int):
    """Curves are subdivided at roughly one point per SVG user unit of arc length."""
    assert len(_import(body).cuts) == expected_cuts


def test_through_cut_path_needing_a_closing_segment():
    """An ungrouped path whose ``Z`` spans a real distance gains a closing edge.

    Both surfaces of a through cut must be sampled from one shared path object:
    ``direct_close()`` mutates state that copies of the same element share, so two
    separate copies would close inconsistently and their segment counts would differ.
    """
    body = '<path d="M 0 0 L 50 0 L 50 50 Z" stroke="#000" fill="none"/>'
    assert len(_import(body).cuts) == 3


def test_degenerate_path_is_skipped_not_fatal():
    """Move-only paths are common in real exports and must not fail the whole import."""
    body = '<path d="M 0 0" stroke="#000" fill="none"/>' + _line(10)
    assert len(_import(body).cuts) == 1


# --- tolerated malformed input --------------------------------------------


def test_reversed_exit_line_is_flipped_into_a_valid_cut():
    """A paired line drawn in the opposite direction is retried with swapped ends."""
    forward = _import(
        '<g><line class="entry" x1="0" y1="0" x2="100" y2="0" stroke="red"/>'
        '<line class="exit" x1="5" y1="0" x2="105" y2="0" stroke="blue"/></g>'
    )
    reversed_exit = _import(
        '<g><line class="entry" x1="0" y1="0" x2="100" y2="0" stroke="red"/>'
        '<line class="exit" x1="105" y1="0" x2="5" y2="0" stroke="blue"/></g>'
    )
    assert len(reversed_exit.cuts) == 1
    assert set(reversed_exit.cuts) == set(forward.cuts)


def test_zero_depth_grayscale_group_is_skipped_without_raising():
    """Two black lines resolve to a zero-depth cut, which is dropped with a warning."""
    assert _import(f"<g>{_line(0)}{_line(0)}</g>").cuts == []
