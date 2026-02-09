from core.models.geometry import Configuration, Geometry, TrapezoidalCut
from core.pipeline.base import Module

import math
from copy import deepcopy


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
        depth: float = cut.depth(0.5)
        laser_power: float = depth * self.cut_speed * self.material_constant
        assert laser_power >= 0
        return laser_power

    def _disretize_cut_one_step(self, cut: TrapezoidalCut) -> list[TrapezoidalCut]:
        # If we cut through the material, we do not need to discretize as the laser power can be constant
        if math.isclose(self.material_height, cut.cut_depth):
            return [cut]

        start_depth: float = cut.start_segment().length()
        end_depth: float = cut.end_segment().length()
        cut_depth: float = cut.cut_depth  # Distance of top and bottom of the trapezoid

        # Calculate max and min cut depth
        max_depth: float = max(start_depth, end_depth, cut_depth)
        min_depth: float = min(start_depth, cut_depth, end_depth)

        delta_depth: float = abs(max_depth - min_depth)

        if delta_depth <= self.max_segment_deviation_mm:
            return [cut]

        y = self.max_segment_deviation_mm
        c = cut.bottom_segment().length()
        beta = cut.bottom_vector().angle(cut.end_vector())
        alpha = math.pi - cut.bottom_vector().angle(cut.start_vector())
        gamma = math.pi - beta - alpha
        b = math.sin(beta) * (c / math.sin(gamma))
        e = math.cos(beta) * b
        x = (c - math.cos(beta) * b) - math.sqrt(
            math.pow(c, 2) - math.pow(y + math.tan(beta) * e, 2)
        )

        f = x / c
        x2 = f * cut.top_segment().length()

        top_norm_vector = (cut.end_top.pv() - cut.start_top.pv()).normalized()
        bottom_norm_vector = (cut.end_bottom.pv() - cut.start_bottom.pv()).normalized()
        new_top_point = deepcopy(cut.start_top).move(top_norm_vector * x2)
        new_bottom_point = deepcopy(cut.start_bottom).move(bottom_norm_vector * x)

        return [
            TrapezoidalCut(
                cut.start_top, new_top_point, cut.start_bottom, new_bottom_point
            ),
            TrapezoidalCut(
                new_top_point, cut.end_top, new_bottom_point, cut.end_bottom
            ),
        ]

    def _discretize_cut(self, cut: TrapezoidalCut) -> list[TrapezoidalCut]:
        if (
            cut.start_configuration().direction_vector()
            != cut.end_configuration().direction_vector()
            and not math.isclose(cut.cut_depth, self.material_height)
        ):
            raise Exception(
                "Partial cuts that are not straight are not supported (yet)"
            )
        return [cut]

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
                start_config = cut.start_configuration()

                if last_config != start_config:
                    self._add_command(
                        f"G0 X{self.format_float(start_config.x)} Y{self.format_float(start_config.y)} Z{self.format_float(self.material_height)} A{self.format_float(math.degrees(start_config.alpha) + 0.0)} B{self.format_float(math.degrees(start_config.beta) + 0.0)}",
                        "travel move",
                    )  # travel move

                end_config = cut.end_configuration()

                if not self.laser_off:
                    laser_power: float = (
                        1000
                        if self.force_max_laser_power
                        else self.calculate_laser_power(cut)
                    )
                    if laser_power > 1000:
                        raise Exception(
                            "Cut speed to high or laser not powerful enough"
                        )

                    if laser_power != last_laser:
                        self._add_command(
                            f"M4 S{self.format_float(laser_power)}",
                            "laser on",
                        )  # laser on dynamic power
                        last_laser = laser_power

                self._add_command(
                    f"G1 X{self.format_float(end_config.x)} Y{self.format_float(end_config.y)} Z{self.format_float(self.material_height)} A{self.format_float(math.degrees(end_config.alpha) + 0.0)} B{self.format_float(math.degrees(end_config.beta) + 0.0)}",
                    "cut move",
                )  # cut

                last_config = end_config

        if not self.laser_off:
            self._add_command("M4 S0", "laser off")  # laser off

        if not self.laser_off:
            self._add_command("M8.1", "air assist off")  # air assist off
        self._add_command("M2", "end")  # end of program
        return self._gcode
