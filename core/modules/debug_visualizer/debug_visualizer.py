from matplotlib.axes import Axes

from core.models.geometry import Configuration, Geometry, MotorPosition, TrapezoidalCut
from core.modules.debug_visualizer.geo_bbox import geo_bbox
from core.pipeline.base import Module

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.widgets as widgets
from matplotlib.animation import FuncAnimation
from Geometry3D import Point, Vector
from enum import IntFlag

import math

from core.service_container import Container
from core.services.laser_config_service import LaserConfigService


class VisualizerFlags(IntFlag):
    SHOW_AREA = 0b01
    SHOW_ORDER = 0b10


# Labels for the 4 configuration panels (row-major, top-left → top-right → bottom-left → bottom-right)
_PANEL_LABELS = ["prev end", "cur start", "cur end", "next start"]


class DebugVisualizerModule(Module[Geometry, Geometry]):
    max_x = 0
    max_y = 0
    shadeArea = False
    showOrder = False
    direction_identifiers = ["←", "↑", "→", "↓"]

    def __init__(
        self,
        material_height: float,
        flags: VisualizerFlags | None = None,
        laser_config: LaserConfigService = Container.laser_config,
    ) -> None:
        super().__init__()

        self.gantry_dim = laser_config.gantry_dim_mm()

        self.material_height = material_height
        if flags:
            self.shadeArea = bool(flags & VisualizerFlags.SHOW_AREA)
            self.showOrder = bool(flags & VisualizerFlags.SHOW_ORDER)

        self.lightest_grey_value = 0.8
        self.arrow_width = 0.1
        self.offset_x = 0
        self.offset_y = 0
        self.step_size = 3.0

        self._current_cut = 1
        self._animation: FuncAnimation | None = None
        self._is_playing = False
        self._play_interval_ms = 400
        self._previous: MotorPosition | None = None

    def process(self, data: Geometry) -> Geometry:
        self.geometry = data
        self.bbox = geo_bbox(data)
        Container.kinematics_service.generate_cache(
            [conf for cut in self.geometry.cuts for conf in cut.configurations()],
            self.material_height,
        )
        self._current_cut = len(self.geometry.cuts)

        self.fig = plt.figure()
        self.fig.subplots_adjust(bottom=0.22)

        # Main gantry plot: left ~65% of the figure
        self.ax = self.fig.add_axes((0.05, 0.22, 0.58, 0.72))

        # 2x2 grid of motor-position panels on the right
        # (left, bottom, width, height) in figure coordinates
        panel_w, panel_h = 0.16, 0.30
        left_col = 0.68
        right_col = 0.84
        top_row = 0.58
        bot_row = 0.22
        self._panel_axes: list[Axes] = [
            self.fig.add_axes((left_col, top_row, panel_w, panel_h)),  # prev end
            self.fig.add_axes((right_col, top_row, panel_w, panel_h)),  # cur start
            self.fig.add_axes((left_col, bot_row, panel_w, panel_h)),  # cur end
            self.fig.add_axes((right_col, bot_row, panel_w, panel_h)),  # next start
        ]

        self._build_widgets()
        self.fig.canvas.mpl_connect("key_press_event", self._on_key_press)

        self._redraw()
        plt.show()
        return self.geometry

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        n = len(self.geometry.cuts)

        ax_scroll_bar = self.fig.add_axes((0.05, 0.08, 0.65, 0.04))
        self._scroll_bar = widgets.Slider(
            ax=ax_scroll_bar,
            label="Cuts",
            valmin=1,
            valmax=n,
            valinit=self._current_cut,
            valstep=1,
            color="#4a90d9",
        )
        self._scroll_bar.on_changed(self._on_scroll_bar_changed)

        ax_play = self.fig.add_axes((0.80, 0.065, 0.08, 0.055))
        self._btn_play = widgets.Button(
            ax_play, "▶ Play", color="#e8f4e8", hovercolor="#c8eac8"
        )
        self._btn_play.on_clicked(self._on_play_clicked)

        ax_speed = self.fig.add_axes((0.05, 0.02, 0.65, 0.03))
        self._slider_speed = widgets.Slider(
            ax=ax_speed,
            label="Speed",
            valmin=50,
            valmax=2000,
            valinit=self._play_interval_ms,
            valstep=50,
            color="#d9a44a",
        )
        self._slider_speed.ax.invert_xaxis()
        self._slider_speed.on_changed(self._on_speed_changed)
        ax_speed.set_xlabel("← faster   slower →", fontsize=7, labelpad=1)

    # ------------------------------------------------------------------
    # Widget callbacks
    # ------------------------------------------------------------------

    def _on_scroll_bar_changed(self, val: float) -> None:
        self._stop_playback()
        self._current_cut = int(val)
        self._redraw()

    def _on_speed_changed(self, val: float) -> None:
        self._play_interval_ms = val
        if self._is_playing:
            self._stop_playback()
            self._start_playback()

    def _on_play_clicked(self, event) -> None:
        if self._is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _start_playback(self) -> None:
        n = len(self.geometry.cuts)
        if n == 0:
            return
        if self._current_cut >= n:
            self._current_cut = 1

        self._is_playing = True
        self._btn_play.label.set_text("⏸ Pause")
        self._redraw()

        self._animation = FuncAnimation(
            self.fig,
            self._animation_step,  # type: ignore[arg-type]
            blit=False,
            interval=self._play_interval_ms,
            repeat=False,
            cache_frame_data=False,
        )
        self.fig.canvas.draw_idle()

    def _animation_step(self, frame) -> None:
        n = len(self.geometry.cuts)
        if self._current_cut > n:
            self._stop_playback()
            return

        self._redraw()
        self._current_cut += 1

    def _stop_playback(self) -> None:
        if self._animation is not None:
            self._animation.event_source.stop()
            self._animation = None
        self._is_playing = False
        if hasattr(self, "_btn_play"):
            self._btn_play.label.set_text("▶ Play")
            self.fig.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Main redraw
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        self.ax.clear()
        self.max_x = 0
        self.max_y = 0
        self.min_x = -1
        self.min_y = -1

        n = len(self.geometry.cuts)
        visible_count = self._current_cut
        visible_cuts = self.geometry.cuts[:visible_count]

        # Sync slider
        self._scroll_bar.eventson = False
        self._scroll_bar.set_val(self._current_cut)
        self._scroll_bar.eventson = True

        # Gantry rectangle
        gantry_x, gantry_y = self.gantry_dim
        self.ax.plot(
            [0, gantry_x, gantry_x, 0, 0],
            [0, 0, gantry_y, gantry_y, 0],
            color="black",
            linestyle="-",
            linewidth=2,
            label="Gantry",
        )

        # Bounding box
        if self.bbox:
            xmin, xmax, ymin, ymax = self.bbox
            self.ax.plot(
                [xmin, xmax, xmax, xmin, xmin],
                [ymin, ymin, ymax, ymax, ymin],
                color="red",
                linestyle="--",
                linewidth=1.5,
                label="BBox",
            )
            self.max_x = max(self.max_x, xmax + 5)
            self.max_y = max(self.max_y, ymax + 5)
            self.min_x = min(self.min_x, xmin - 5)
            self.min_y = min(self.min_y, ymin - 5)

        for i, cut in enumerate(visible_cuts):
            self._draw_cut(cut, i)
            if i != len(visible_cuts) - 1:
                if visible_cuts[i + 1].start_configuration != cut.end_configuration:
                    self._draw_travel_move(
                        cut.end_configuration,
                        visible_cuts[i + 1].start_configuration,
                    )

        self.ax.set_xlim(self.min_x, max(gantry_x + 1, self.max_x + 5))
        self.ax.set_ylim(self.min_y, max(gantry_y + 1, self.max_y + 5))
        self.ax.set_aspect("equal")
        self.fig.suptitle(
            f"Offset X: {self.offset_x}  Y: {self.offset_y}"
            f"   [{visible_count}/{n} cuts]"
        )

        self._redraw_config_panels()
        self.fig.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Configuration panels
    # ------------------------------------------------------------------

    def _get_panel_configurations(self) -> list[Configuration | None]:
        """Return [prev_end, cur_start, cur_end, next_start]; None where out of range."""
        cuts = self.geometry.cuts
        c = self._current_cut - 1  # 0-indexed index of the current (last visible) cut

        prev_end = cuts[c - 1].end_configuration if c - 1 >= 0 else None
        cur_start = cuts[c].start_configuration
        cur_end = cuts[c].end_configuration
        next_start = cuts[c + 1].start_configuration if c + 1 < len(cuts) else None

        return [prev_end, cur_start, cur_end, next_start]

    def _redraw_config_panels(self) -> None:
        configurations = self._get_panel_configurations()
        for ax, config, label in zip(self._panel_axes, configurations, _PANEL_LABELS):
            self._draw_config_panel(ax, config, label)

    def _to_motor_position(self, config: Configuration) -> MotorPosition:
        closest, furthest = config.to_motor_positions(self.material_height)
        if self._previous is None:
            return closest
        closest_cost = Container.laser_cost.chebyshev_distance(self._previous, closest)
        furthest_cost = Container.laser_cost.chebyshev_distance(
            self._previous, furthest
        )
        if closest_cost <= furthest_cost:
            return closest
        else:
            return furthest

    def _draw_config_panel(
        self, ax: Axes, config: Configuration | None, label: str
    ) -> None:
        ax.clear()
        # Panel coordinate space is always [0, 1] x [0, 1]
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(label, fontsize=8, pad=3)

        # ── Disk: fixed at centre, fills most of the panel ────────────
        # Always drawn regardless of config so the panel never looks empty
        disk_cx, disk_cy = 0.5, 0.5
        disk_r = 0.42  # nearly fills the [0,1]x[0,1] space
        disk = mpatches.Circle(
            (disk_cx, disk_cy),
            disk_r,
            facecolor="#ddeeff",
            edgecolor="steelblue",
            linewidth=1.5,
            zorder=1,
        )
        ax.add_patch(disk)

        if config is None:
            return

        motor_pos = self._to_motor_position(config)
        self._previous = motor_pos
        gantry_w, gantry_h = self.gantry_dim

        # ── Radial marker on disk (table rotation, motor_pos.a) ───────
        # a is in [0, 2π), 0 → up, increases clockwise.
        # matplotlib CCW from +x → angle_mpl = π/2 − a
        marker_angle_mpl = math.pi / 2 - motor_pos.a
        ax.plot(
            [disk_cx, disk_cx + disk_r * math.cos(marker_angle_mpl)],
            [disk_cy, disk_cy + disk_r * math.sin(marker_angle_mpl)],
            color="steelblue",
            linewidth=2,
            zorder=2,
        )

        # ── Arrow (laser angle + position) ────────────────────────────
        # x, y normalised into [0, 1] panel space
        x_norm = motor_pos.x / gantry_w
        y_norm = motor_pos.y / gantry_h
        in_bounds = (0.0 <= x_norm <= 1.0) and (0.0 <= y_norm <= 1.0)

        if in_bounds:
            # b=0 → down (−y), b=−π/2 → −x, b=+π/2 → +x
            # angle_mpl = −π/2 − b
            max_arrow_len = 0.25
            arrow_len = (motor_pos.z / self.material_height) * max_arrow_len
            arrow_angle_mpl = -math.pi / 2 - motor_pos.b
            dx = arrow_len * math.cos(arrow_angle_mpl)
            dy = arrow_len * math.sin(arrow_angle_mpl)

            ax.annotate(
                "",
                xy=(x_norm + dx, y_norm + dy),
                xytext=(x_norm, y_norm),
                arrowprops=dict(arrowstyle="-|>", color="tomato", lw=1.5),
                zorder=3,
            )
            ax.plot(x_norm, y_norm, "o", color="tomato", markersize=3, zorder=3)
        else:
            ax.text(
                0.5,
                0.5,
                "✕",
                ha="center",
                va="center",
                fontsize=14,
                color="#888",
                zorder=3,
            )

        # Numeric readout just below the panel title (top of axes)
        ax.text(
            0.5,
            0.02,
            f"a={math.degrees(motor_pos.a):.1f}°  b={math.degrees(motor_pos.b):.1f}°"
            f"  z={motor_pos.z:.1f}",
            ha="center",
            va="bottom",
            fontsize=6,
            zorder=3,
        )

    # ------------------------------------------------------------------
    # Key press (pan)
    # ------------------------------------------------------------------

    def _on_key_press(self, event) -> None:
        dx, dy = 0, 0
        if event.key == "up":
            dy += self.step_size
        if event.key == "down":
            dy -= self.step_size
        if event.key == "left":
            dx -= self.step_size
        if event.key == "right":
            dx += self.step_size

        if dx == 0 and dy == 0:
            return

        move_vector = Vector(dx, dy, 0)
        for i, cut in enumerate(self.geometry.cuts):
            self.geometry.cuts[i] = cut.move(move_vector)

        self.offset_x += dx
        self.offset_y += dy
        if self.bbox:
            xmin, xmax, ymin, ymax = self.bbox
            self.bbox = (xmin + dx, xmax + dx, ymin + dy, ymax + dy)

        self._redraw()

    # ------------------------------------------------------------------
    # Cut drawing helpers
    # ------------------------------------------------------------------

    def _draw_cut(self, cut: TrapezoidalCut, cut_number: int) -> None:
        start_top = cut.top_segment().start_point
        end_top = cut.top_segment().end_point
        start_bottom = cut.bottom_segment().start_point
        end_bottom = cut.bottom_segment().end_point

        if cut_number == self._current_cut - 1:
            line_color = "red"
        else:
            line_color = "black"
        self._draw_line(start_top, end_top, line_color)
        if not cut.is_straight_cut():
            self._draw_line(
                start_bottom, end_bottom, self._get_grey_color(-start_bottom.z)
            )
            self._draw_connecting_lines(cut)

        if self.showOrder:
            cut_direction: Vector = Vector(cut.start_top, cut.end_top)
            angle = cut_direction.angle(Vector.y_unit_vector())
            direction = (
                int(angle * (-1 if cut_direction[0] < 0 else 1) * 2 / math.pi) + 1
            )
            text_point = Point(
                (start_top.x + end_top.x + start_bottom.x + end_bottom.x) / 4,
                (start_top.y + end_top.y + start_bottom.y + end_bottom.y) / 4,
                0,
            )
            self.ax.text(
                text_point.x,
                text_point.y,
                str(cut_number + 1) + self.direction_identifiers[direction],
            )

        self.max_x = max(
            [self.max_x, start_top.x, end_top.x, start_bottom.x, end_bottom.x]
        )
        self.max_y = max(
            [self.max_y, start_top.y, end_top.y, start_bottom.y, end_bottom.y]
        )
        self.min_x = min(
            self.min_x, start_top.x, end_top.x, start_bottom.x, end_bottom.x
        )
        self.min_y = min(
            self.min_y, start_top.y, end_top.y, start_bottom.y, end_bottom.y
        )

    def _draw_travel_move(
        self, from_config: Configuration, to_config: Configuration
    ) -> None:
        self.ax.arrow(
            from_config.x,
            from_config.y,
            to_config.x - from_config.x,
            to_config.y - from_config.y,
            length_includes_head=True,
            color="#0004",
            linestyle="dotted",
            width=self.arrow_width * 3 / 4,
        )

    def _draw_connecting_lines(self, cut: TrapezoidalCut) -> None:
        color = "#bbe"
        linestyle = "dashdot"
        self._draw_line(cut.start_top, cut.start_bottom, color, linestyle)
        self._draw_line(
            Point((cut.start_top.pv() + cut.end_top.pv()) * 0.5),
            Point((cut.start_bottom.pv() + cut.end_bottom.pv()) * 0.5),
            color,
            linestyle,
        )
        self._draw_line(cut.end_top, cut.end_bottom, color, linestyle)

    def _draw_line(
        self, start: Point, end: Point, color: str, linestyle: str = "solid"
    ) -> None:
        self.ax.plot(
            (start.x, end.x), (start.y, end.y), color=color, linestyle=linestyle
        )

    def _get_grey_color(self, cut_depth: float) -> str:
        assert cut_depth > 0
        assert cut_depth < self.material_height or math.isclose(
            cut_depth, self.material_height
        )
        percentage = cut_depth / self.material_height
        grey = self.lightest_grey_value * percentage
        return str(grey)
