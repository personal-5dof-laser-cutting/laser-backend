from Geometry3D import Point
import pytest
from core.models.geometry import Geometry, TrapezoidalCut
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer

DPI = 72
MM_PER_DOTS = 25.4 / DPI
MIN_X = 0
MAX_Y = 100.0


def _expected_point(x: float, y: float, z: float, scale: float = 1.0):
    return Point((x - MIN_X) * scale, (MAX_Y - y) * scale, z)


# /home/edi/dev/bachelor/control-software/svgs/whine-rack/whine-rack-svg5dof.svg
@pytest.mark.parametrize(
    "svg_string,material_height,expected_cuts",
    [
        (
            open("tests/svg5dof/svgs/one_line.svg").read(),
            5.0,
            [
                TrapezoidalCut(
                    _expected_point(0.0, 0.0, 0.0, MM_PER_DOTS),
                    _expected_point(100.0, 100.0, 0.0, MM_PER_DOTS),
                    _expected_point(0.0, 0.0, -5.0, MM_PER_DOTS),
                    _expected_point(100.0, 100.0, -5.0, MM_PER_DOTS),
                )
            ],
        ),
        (
            open("tests/svg5dof/svgs/one_line_angled.svg").read(),
            5.0,
            [
                TrapezoidalCut(
                    _expected_point(0.0, 0.0, 0.0, MM_PER_DOTS),
                    _expected_point(100.0, 100.0, 0.0, MM_PER_DOTS),
                    _expected_point(5.0, 0.0, -5.0, MM_PER_DOTS),
                    _expected_point(105.0, 100.0, -5.0, MM_PER_DOTS),
                )
            ],
        ),
        (
            open("tests/svg5dof/svgs/one_line_partial.svg").read(),
            10.0,
            [
                TrapezoidalCut(
                    _expected_point(0.0, 0.0, 0.0, MM_PER_DOTS),
                    _expected_point(100.0, 100.0, 0.0, MM_PER_DOTS),
                    _expected_point(0.0, 0.0, -5.0, MM_PER_DOTS),
                    _expected_point(100.0, 100.0, -5.0, MM_PER_DOTS),
                )
            ],
        ),
        # (open("tests/svg5dof/svgs/square_45degrees_5dof.svg").read(), 6.0, []),
        # (open("tests/svg5dof/svgs/circle.svg").read(), 6.0, []),
        # (open("tests/svg5dof/svgs/whine-rack.svg").read(), 6.0, []),
    ],
)
def test_import(
    svg_string: str, material_height: float, expected_cuts: list[TrapezoidalCut]
):
    dof = SVG5DOF_Importer(material_height)
    geometry: Geometry = dof.process(svg_string)
    cuts: set[TrapezoidalCut] = set(geometry.cuts)
    assert cuts == set(expected_cuts)
