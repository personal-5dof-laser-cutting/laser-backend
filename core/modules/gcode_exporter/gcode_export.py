from Geometry3D import Point

from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module

import math


class GCodeExporter(Module[Geometry, str]):
    def __init__(
        self,
        material_height: float,
        gcode_comments: bool = True,
        pretty_formatting: bool = True,
        cut_speed: float = 20,
        material_constant: float = 7.5,
        laser_off: bool = True,
        force_max_laser_power: bool = False,
        prop_up: float = 0.0,
    ) -> None:
        super().__init__()
        self._gcode: str = ""

        self.max_segment_deviation_mm: float = 0.1

        # workpiece settings
        self.material_height: float = material_height

        # gcode settings
        self.gcode_comments: bool = gcode_comments
        self.pretty_formatting: bool = pretty_formatting

        ### machine settings
        # movement
        self.cut_speed: float = cut_speed  # mm/s
        # laser
        self.material_constant: float = material_constant  # s/mm^2
        self.laser_off: bool = laser_off
        self.force_max_laser_power: bool = force_max_laser_power

        self.prop_up: float = prop_up

    def _add_command(self, command: str, comment: str = ""):
        self._gcode += command
        if self.gcode_comments and comment != "":
            self._gcode += f"; {comment}"
        self._gcode += "\n"

    def format_float(self, value, precision=3) -> str:
        rounded_value = round(value, precision)

        if self.pretty_formatting:
            return f"{rounded_value:z4.{precision}f}"
        else:
            return f"{rounded_value:z.{precision}f}".rstrip("0").rstrip(".")

    def calculate_laser_power(self, cut: TrapezoidalCut) -> float:
        # TODO: does the laser power actually scale linearly
        depth: float = cut.depth(0.5)

        if math.isclose(depth, 0):
            return 0

        angle: float = cut.effective_angle_abs

        laser_power: float = (
            depth * self.cut_speed * self.material_constant * (1 / math.cos(angle))
        )

        assert laser_power >= 0
        return laser_power

    def _discretize_cut(self, cut: TrapezoidalCut) -> list[TrapezoidalCut]:
        max_depth_deviation: float = 0.1
        step_resolution_mm: float = 0.2
        total_length: float = cut.top_vector().length()

        test_point: float = 0.0
        result: list[TrapezoidalCut] = []

        last_depth: float = cut.depth(test_point / total_length)
        last_cut_pos: float = 0.0

        while test_point <= total_length:
            test_depth = cut.depth(test_point / total_length)

            if abs(test_depth - last_depth) > max_depth_deviation:
                start_value: float = last_cut_pos / total_length
                end_value: float = min(test_point / total_length, 1.0)

                new_cut = TrapezoidalCut(
                    Point((cut.top_vector() * start_value) + cut.start_top.pv()),  # type: ignore
                    Point((cut.top_vector() * end_value) + cut.start_top.pv()),  # type: ignore
                    Point((cut.bottom_vector() * start_value) + cut.start_bottom.pv()),  # type: ignore
                    Point((cut.bottom_vector() * end_value) + cut.start_bottom.pv()),  # type: ignore
                )  # the linter is not smart enough to figure out that a vector multiplied with a scalar is always a vector and not an int
                result.append(new_cut)

                last_depth = test_depth
                last_cut_pos = test_point
            test_point += step_resolution_mm

        if len(result) == 0:
            return [cut]

        return result

    def process(self, data: Geometry) -> str:
        geometry = data

        self._add_command("G90", "absolute positioning")  # absolute positioning
        self._add_command("G21", "units in mm")  # use milimeters for XYZ
        self._add_command(
            f"F{self.format_float(self.cut_speed * 60)}", "feedrate"
        )  # set feedrate (in mm/minute)
        if not self.laser_off:
            self._add_command("M8", "air assist on")  # air assist on (flood pin)

        last_config: None | Configuration = None
        last_laser: None | float = None
        for raw_cut in geometry.cuts:
            for cut in self._discretize_cut(raw_cut):
                start_config = cut.start_configuration

                end_config = cut.end_configuration

                if not self.laser_off:
                    laser_power: float = (
                        255
                        if self.force_max_laser_power
                        else self.calculate_laser_power(cut)
                    )

                    if math.isclose(cut.cut_depth, self.material_height):
                        laser_power: float = 255

                    if laser_power > 255:
                        print("Cut speed to high or laser not powerful enough")

                    if laser_power != last_laser:
                        self._add_command(
                            f"M4 S{self.format_float(laser_power)}",
                            "laser on",
                        )  # laser on dynamic power
                        last_laser = laser_power

                if last_config != start_config:
                    self._add_command(
                        f"G0 X{self.format_float(start_config.x)} Y{self.format_float(start_config.y)} Z{self.format_float(self.material_height + self.prop_up)} A{self.format_float(math.degrees(start_config.alpha) + 0.0)} B{self.format_float(math.degrees(start_config.beta) + 0.0)}",
                        "travel move",
                    )  # travel move

                self._add_command(
                    f"G1 X{self.format_float(end_config.x)} Y{self.format_float(end_config.y)} Z{self.format_float(self.material_height + self.prop_up)} A{self.format_float(math.degrees(end_config.alpha) + 0.0)} B{self.format_float(math.degrees(end_config.beta) + 0.0)}",
                    "cut move",
                )  # cut

                last_config = end_config

        if not self.laser_off:
            self._add_command("M4 S0", "laser off")  # laser off

        if not self.laser_off:
            self._add_command("M8.1", "air assist off")  # air assist off
        self._add_command("G0 X200 Y300 A0 B0", "go to rest position")
        self._add_command("M2", "end")  # end of program
        return self._gcode
