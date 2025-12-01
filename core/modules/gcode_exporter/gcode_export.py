from core.models.geometry import Configuration, Geometry
from core.pipeline.base import Module


class GCodeExporter(Module[tuple[Geometry, float], str]):
    def __init__(self) -> None:
        super().__init__()
        self.gcode: str = ""
        self.add_comments: bool = True

    def _add_command(self, command: str, comment: str = ""):
        self.gcode += f"{command}"
        if self.add_comments and comment != "":
            self.gcode += f"; {comment}"
        self.gcode += "\n"

    def process(self, data: tuple[Geometry, float]) -> str:
        geometry, material_height = data

        cut_speed: float = 10  # mm/s
        material_constant: float = 3.21  # s/mm^2

        self._add_command("G90", "absolute positioning")  # absolute positioning
        self._add_command("G21", "units in mm")  # use milimeters for XYZ
        self._add_command("F1000", "feedrate")  # set feedrate
        self._add_command("M8", "air assist on")  # air assist on (flood pin)

        last_config: None | Configuration = None
        for cut in geometry.cuts:
            start_config = cut.start_configuration()

            if last_config != start_config:
                self._add_command(
                    f"G0 {start_config.x} {start_config.y} {material_height} {start_config.alpha + 0.0} {start_config.beta + 0.0}",
                    "travel move",
                )  # travel move

            end_config = cut.end_configuration()
            self._add_command(
                f"M4 S{cut.cut_depth * cut_speed * material_constant}", "laser on"
            )  # laser on dynamic power
            self._add_command(
                f"G1 {end_config.x} {end_config.y} {material_height} {end_config.alpha + 0.0} {end_config.beta + 0.0}",
                "cut move",
            )  # cut
            self._add_command("M4 S0", "laser off")  # laser off
            last_config = end_config

        self._add_command("M8.1", "air assist off")  # air assist off
        self._add_command("M2", "end")  # end of program
        return self.gcode
