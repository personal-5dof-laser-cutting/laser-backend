from Geometry3D import Point
import pytest
from core.models.geometry import Geometry, TrapezoidalCut
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


# /home/edi/dev/bachelor/control-software/svgs/whine-rack/whine-rack-svg5dof.svg
@pytest.mark.parametrize(
    "svg_string,material_height,expected_cuts",
    [
        (
            open("tests/svg5dof/svgs/one_line.svg").read(),
            5.0,
            [
                TrapezoidalCut(
                    Point(0.0, 0.0, 0.0),
                    Point(100.0, 100.0, 0.0),
                    Point(0.0, 0.0, -5.0),
                    Point(100.0, 100.0, -5.0),
                )
            ],
        ),
        (
            open("tests/svg5dof/svgs/one_line_angled.svg").read(),
            5.0,
            [
                TrapezoidalCut(
                    Point(0.0, 0.0, 0.0),
                    Point(100.0, 100.0, 0.0),
                    Point(5.0, 0.0, -5.0),
                    Point(105.0, 100.0, -5.0),
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
