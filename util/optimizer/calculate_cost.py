import logging
import sys
import tkinter
import tkinter.filedialog

import Geometry3D

from core.models.geometry import Geometry
from core.modules.auto_nester.auto_nester import AutoNester
from core.modules.svg5dof_importer.import_svg5dof import SVG5DOF_Importer

logging.basicConfig(
    level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s", force=True
)

logger = logging.getLogger("Calculator" if __name__ == "__main__" else __name__)


def format_seconds(time: float) -> str:
    seconds = time % 60
    time = (time - seconds) / 60
    minutes = time % 60
    hours = (time - minutes) / 60

    output = ""
    if hours:
        output += f"{hours} hours, "
    if minutes:
        output += f"{minutes} minutes, "
    output += f"{seconds} seconds."
    return output


def calculate_costs():
    Geometry3D.set_sig_figures(4)
    svg_file = tkinter.filedialog.askopenfile(
        filetypes=[("SVG4DOF", "*.svg*")], initialdir="tests/svg5dof/svgs"
    )
    if svg_file is None:
        sys.exit(1)
    svg_string = svg_file.read()
    dpi: float = float(input("DPI: ") or "72")
    material_height: float = float(input("Material height: "))
    feedrate: float = float(input("Feedrate: "))
    nest_svg: bool = input("Nest SVG [y/N]: ").lower() == "y"
    importer = SVG5DOF_Importer(material_height, dpi)
    geometry: Geometry = importer.process(svg_string)
    if nest_svg:
        nester = AutoNester(200, 200)
        geometry = nester.process(geometry)
    travel_cost = geometry.calculate_travel_cost(material_height, False)
    cut_cost = geometry.calculate_cut_cost(material_height, feedrate)
    total_cost = travel_cost + cut_cost
    logger.info(f"Total time: {format_seconds(total_cost)}")
    logger.info(f"Cut time: {format_seconds(cut_cost)} ({cut_cost / total_cost:.2%})")
    logger.info(
        f"Travel time: {format_seconds(travel_cost)} ({travel_cost / total_cost:.2%})"
    )
    generate_gcode = input("Generate GCODE [y/N]").lower() == "y"
    if generate_gcode:
        pass


if __name__ == "__main__":
    calculate_costs()
