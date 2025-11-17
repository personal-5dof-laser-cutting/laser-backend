from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer


def test_import():
    dof = SVG5DOF_Importer()
    dof.process(
        (
            open(
                "/home/edi/dev/bachelor/control-software/svgs/whine-rack/whine-rack-svg5dof.svg",
                "r",
            ).read(),
            5.0,
        )
    )
