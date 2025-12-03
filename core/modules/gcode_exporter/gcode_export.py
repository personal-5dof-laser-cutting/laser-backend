from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module

import math


class GCodeExporter(Module[tuple[Geometry, float], str]):
    def __init__(self) -> None:
        super().__init__()
        self._gcode: str = ""

        # gcode settings
        self.add_comments: bool = True
        self.pretty_formatting: bool = True

        # machine settings
        self.cut_speed: float = 10  # mm/s
        self.material_constant: float = 3.21  # s/mm^2
        self.dry_run: bool = True

    def _add_command(self, command: str, comment: str = ""):
        self._gcode += f"{command}"
        if self.add_comments and comment != "":
            self._gcode += f"; {comment}"
        self._gcode += "\n"

    def format_float(self, value, precision=8) -> str:
        rounded_value = round(value, precision)

        if self.pretty_formatting:
            return f"{rounded_value:5.{precision}}"
        else:
            return f"{rounded_value:.{precision}}"

    def discretize_cut_by_depth(
        self, cut: TrapezoidalCut, max_deviation_mm: float = 0.5
    ) -> list[TrapezoidalCut]:
        return []

    def process(self, data: tuple[Geometry, float]) -> str:
        geometry, material_height = data

        self._add_command("G90", "absolute positioning")  # absolute positioning
        self._add_command("G21", "units in mm")  # use milimeters for XYZ
        self._add_command("F6000", "feedrate")  # set feedrate
        self._add_command("M8", "air assist on")  # air assist on (flood pin)

        last_config: None | Configuration = None
        for cut in geometry.cuts:
            start_config = cut.start_configuration()

            if last_config != start_config:
                self._add_command(
                    f"G0 X{self.format_float(start_config.x)} Y{self.format_float(start_config.y)} Z{self.format_float(material_height)} A{self.format_float(math.degrees(start_config.alpha) + 0.0)} B{self.format_float(math.degrees(start_config.beta) + 0.0)}",
                    "travel move",
                )  # travel move

            end_config = cut.end_configuration()

            if not self.dry_run:
                self._add_command(
                    f"M4 S{self.format_float(cut.cut_depth * self.cut_speed * self.material_constant)}",
                    "laser on",
                )  # laser on dynamic power

            self._add_command(
                f"G1 X{self.format_float(end_config.x)} Y{self.format_float(end_config.y)} Z{self.format_float(material_height)} A{self.format_float(math.degrees(end_config.alpha) + 0.0)} B{self.format_float(math.degrees(end_config.beta) + 0.0)}",
                "cut move",
            )  # cut
            if not self.dry_run:
                self._add_command("M4 S0", "laser off")  # laser off
            last_config = end_config

        self._add_command("M8.1", "air assist off")  # air assist off
        self._add_command("M2", "end")  # end of program
        return self._gcode
