from core.models.geometry import Configuration, Geometry
from core.pipeline.base import Module


class GCodeExporter(Module[tuple[Geometry, float], str]):
    def __init__(self) -> None:
        super().__init__()
        self.gcode: str = ""

    def _add_command(self, command: str):
        self.gcode += f"{command}\n"

    def process(self, data: tuple[Geometry, float]) -> str:
        geometry, material_height = data

        cut_speed: float = 10  # mm/s
        material_constant: float = 3.21  # s/mm^2

        self._add_command("G90")  # absolute positioning
        self._add_command("G21")  # use milimeters for XYZ
        self._add_command("F1000")  # set feedrate
        self._add_command("M8")  # air assist on (flood pin)

        last_config: None | Configuration = None
        for cut in geometry.cuts:
            start_config = cut.start_configuration()

            if last_config is not None and last_config != start_config:
                self._add_command(
                    f"G0 {start_config.x} {start_config.y} {material_height} {start_config.alpha} {start_config.beta}"
                )  # travel move

            end_config = cut.end_configuration()
            self._add_command(
                f"M4 S{cut.cut_depth * cut_speed * material_constant}"
            )  # laser on dynamic power
            self._add_command(
                f"G1 {end_config.x} {end_config.y} {material_height} {end_config.alpha} {end_config.beta}"
            )  # cut
            self._add_command("M4 S0")  # laser off
            last_config = end_config

        self._add_command("M8.1")  # air assist off
        self._add_command("M2")  # end of program
        return self.gcode
