from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module

import math


class GCodeExporter(Module[tuple[Geometry, float], str]):
    def __init__(
        self,
        gcode_comments: bool = True,
        pretty_formatting: bool = True,
        cut_speed: float = 20,
        material_constant: float = 1.0,
        dry_run: bool = True,
        force_max_laser_power: bool = True,
    ) -> None:
        super().__init__()
        self._gcode: str = ""

        # gcode settings
        self.gcode_comments: bool = gcode_comments
        self.pretty_formatting: bool = pretty_formatting

        ### machine settings
        # movement
        self.cut_speed: float = cut_speed  # mm/s
        # laser
        self.material_constant: float = material_constant  # s/mm^2
        self.dry_run: bool = dry_run
        self.force_max_laser_power: bool = force_max_laser_power

    def _add_command(self, command: str, comment: str = ""):
        self._gcode += f"{command}"
        if self.gcode_comments and comment != "":
            self._gcode += f"; {comment}"
        self._gcode += "\n"

    def format_float(self, value, precision=8) -> str:
        rounded_value = round(value, precision)

        if self.pretty_formatting:
            return f"{rounded_value:4.{precision}f}"
        else:
            return f"{rounded_value:.{precision}}"

    def calculate_laser_power(self, cut: TrapezoidalCut) -> float:
        if self.force_max_laser_power:
            return 1000

        # TODO: this calculation is not that useful
        start_depth: float = cut.start_segment().length()
        end_depth: float = cut.end_segment().length()
        max_depth: float = max(start_depth, end_depth)
        return max_depth * self.cut_speed * self.material_constant

    def process(self, data: tuple[Geometry, float]) -> str:
        geometry, material_height = data

        self._add_command("G90", "absolute positioning")  # absolute positioning
        self._add_command("G21", "units in mm")  # use milimeters for XYZ
        self._add_command(
            f"F{self.format_float(self.cut_speed * 60)}", "feedrate"
        )  # set feedrate (in mm/minute)
        if not self.dry_run:
            self._add_command("M8", "air assist on")  # air assist on (flood pin)

        last_config: None | Configuration = None
        for cut in geometry.cuts:
            if not math.isclose(cut.cut_depth, material_height):
                raise NotImplementedError(
                    f"Partial cuts are currently not supported! cut depth={cut.cut_depth:.5f} mm, material_height={material_height:.5f} mm"
                )

            start_config = cut.start_configuration()

            if last_config != start_config:
                self._add_command(
                    f"G0 X{self.format_float(start_config.x)} Y{self.format_float(start_config.y)} Z{self.format_float(material_height)} A{self.format_float(math.degrees(start_config.alpha) + 0.0)} B{self.format_float(math.degrees(start_config.beta) + 0.0)}",
                    "travel move",
                )  # travel move

            end_config = cut.end_configuration()

            if not self.dry_run:
                self._add_command(
                    f"M4 S{self.calculate_laser_power(cut)}",
                    "laser on",
                )  # laser on dynamic power

            self._add_command(
                f"G1 X{self.format_float(end_config.x)} Y{self.format_float(end_config.y)} Z{self.format_float(material_height)} A{self.format_float(math.degrees(end_config.alpha) + 0.0)} B{self.format_float(math.degrees(end_config.beta) + 0.0)}",
                "cut move",
            )  # cut

            if not self.dry_run:
                self._add_command("M4 S0", "laser off")  # laser off
            last_config = end_config

        if not self.dry_run:
            self._add_command("M8.1", "air assist off")  # air assist off
        self._add_command("M2", "end")  # end of program
        return self._gcode
