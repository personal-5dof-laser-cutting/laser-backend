#!/usr/bin/env python3
"""
fix_paths.py - Validate and generate fixed SVG files for 5DOF laser cutter.

Ensures that in every <g> group containing a black (#000) and gray (#666) path:
  1. Both paths have the same number of anchor points.
  2. Points matched by proportional path position (parameter t) are spatially
     consistent (i.e. point at t=0.5 on the black path is near the point at
     t=0.5 on the gray path).

Subcommands:
  validate <input.svg>   - Check constraints; produce error.svg with violations
                           color-coded (red = unequal point count,
                           green = misordered points).
  generate <input.svg> <output.svg>
                         - Fix constraint violations and write a new SVG.
"""

import argparse
import copy
import math
import re
import sys
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# SVG namespace handling
# ---------------------------------------------------------------------------
SVG_NS = "http://www.w3.org/2000/svg"
NS = {"svg": SVG_NS}

# Register namespace so output doesn't get ns0: prefixes
ET.register_namespace("", SVG_NS)

# ---------------------------------------------------------------------------
# Path tokenizer / parser
# ---------------------------------------------------------------------------


def tokenize_path(d: str) -> list[tuple[str, list[float]]]:
    """Split an SVG path `d` attribute into (command, [args]) pairs."""
    tokens = re.findall(
        r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?",
        d,
    )
    commands: list[tuple[str, list[float]]] = []
    cmd = None
    args: list[float] = []
    for tok in tokens:
        if tok.isalpha():
            if cmd is not None:
                commands.append((cmd, args))
            cmd = tok
            args = []
        else:
            args.append(float(tok))
    if cmd is not None:
        commands.append((cmd, args))
    return commands


# Argument counts per command letter (uppercase = absolute)
_ARG_COUNTS = {
    "M": 2,
    "L": 2,
    "H": 1,
    "V": 1,
    "C": 6,
    "S": 4,
    "Q": 4,
    "T": 2,
    "A": 7,
    "Z": 0,
}


def _split_implicit(
    commands: list[tuple[str, list[float]]],
) -> list[tuple[str, list[float]]]:
    """Expand implicit repeated commands into individual commands.

    E.g. ``C x1 y1 x2 y2 x3 y3 x4 y4 x5 y5 x6 y6`` becomes two ``C`` commands.
    Also handles implicit L after M.
    """
    out: list[tuple[str, list[float]]] = []
    for cmd, args in commands:
        key = cmd.upper()
        n = _ARG_COUNTS.get(key, 0)
        if n == 0:
            out.append((cmd, []))
            continue
        if key == "M" and len(args) > 2:
            # First pair is M, rest are implicit L/l
            out.append((cmd, args[:2]))
            implicit = "L" if cmd == "M" else "l"
            for i in range(2, len(args), 2):
                out.append((implicit, args[i : i + 2]))
            continue
        if len(args) <= n:
            out.append((cmd, args))
        else:
            for i in range(0, len(args), n):
                out.append((cmd, args[i : i + n]))
    return out


def commands_to_absolute(
    commands: list[tuple[str, list[float]]],
) -> list[tuple[str, list[float]]]:
    """Convert all relative commands to absolute and normalize to a canonical set.

    Returns a list of individual commands, each absolute:
      M, L, C, S, Q, T, A, Z  (and H/V are converted to L).
    """
    commands = _split_implicit(commands)
    out: list[tuple[str, list[float]]] = []
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0  # subpath start

    for cmd, args in commands:
        if cmd == "M":
            cx, cy = args[0], args[1]
            sx, sy = cx, cy
            out.append(("M", [cx, cy]))
        elif cmd == "m":
            cx += args[0]
            cy += args[1]
            sx, sy = cx, cy
            out.append(("M", [cx, cy]))
        elif cmd == "L":
            cx, cy = args[0], args[1]
            out.append(("L", [cx, cy]))
        elif cmd == "l":
            cx += args[0]
            cy += args[1]
            out.append(("L", [cx, cy]))
        elif cmd == "H":
            cx = args[0]
            out.append(("L", [cx, cy]))
        elif cmd == "h":
            cx += args[0]
            out.append(("L", [cx, cy]))
        elif cmd == "V":
            cy = args[0]
            out.append(("L", [cx, cy]))
        elif cmd == "v":
            cy += args[0]
            out.append(("L", [cx, cy]))
        elif cmd == "C":
            out.append(("C", list(args)))
            cx, cy = args[4], args[5]
        elif cmd == "c":
            a = [
                cx + args[0],
                cy + args[1],
                cx + args[2],
                cy + args[3],
                cx + args[4],
                cy + args[5],
            ]
            out.append(("C", a))
            cx, cy = a[4], a[5]
        elif cmd == "S":
            out.append(("S", list(args)))
            cx, cy = args[2], args[3]
        elif cmd == "s":
            a = [cx + args[0], cy + args[1], cx + args[2], cy + args[3]]
            out.append(("S", a))
            cx, cy = a[2], a[3]
        elif cmd == "Q":
            out.append(("Q", list(args)))
            cx, cy = args[2], args[3]
        elif cmd == "q":
            a = [cx + args[0], cy + args[1], cx + args[2], cy + args[3]]
            out.append(("Q", a))
            cx, cy = a[2], a[3]
        elif cmd == "T":
            out.append(("T", list(args)))
            cx, cy = args[0], args[1]
        elif cmd == "t":
            a = [cx + args[0], cy + args[1]]
            out.append(("T", a))
            cx, cy = a[0], a[1]
        elif cmd == "A":
            out.append(("A", list(args)))
            cx, cy = args[5], args[6]
        elif cmd == "a":
            a = list(args)
            a[5] += cx
            a[6] += cy
            out.append(("A", a))
            cx, cy = a[5], a[6]
        elif cmd.upper() == "Z":
            out.append(("Z", []))
            cx, cy = sx, sy

    return out


# ---------------------------------------------------------------------------
# Anchor-point extraction
# ---------------------------------------------------------------------------


def get_anchor_points(
    abs_commands: list[tuple[str, list[float]]],
) -> list[tuple[float, float]]:
    """Return list of anchor (endpoint) coordinates from absolute commands.

    Includes the starting M point and each segment endpoint.
    """
    pts: list[tuple[float, float]] = []
    for cmd, args in abs_commands:
        if cmd == "M":
            pts.append((args[0], args[1]))
        elif cmd == "L":
            pts.append((args[0], args[1]))
        elif cmd == "C":
            pts.append((args[4], args[5]))
        elif cmd == "S":
            pts.append((args[2], args[3]))
        elif cmd == "Q":
            pts.append((args[2], args[3]))
        elif cmd == "T":
            pts.append((args[0], args[1]))
        elif cmd == "A":
            pts.append((args[5], args[6]))
        # Z doesn't add a new unique point
    return pts


# ---------------------------------------------------------------------------
# Segment-length computation (for proportional matching)
# ---------------------------------------------------------------------------


def _line_length(x0, y0, x1, y1):
    return math.hypot(x1 - x0, y1 - y0)


def _cubic_bezier_length(x0, y0, x1, y1, x2, y2, x3, y3, n=20):
    """Approximate cubic bezier arc length by sampling n+1 points."""
    length = 0.0
    px, py = x0, y0
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * x0 + 3 * u**2 * t * x1 + 3 * u * t**2 * x2 + t**3 * x3
        y = u**3 * y0 + 3 * u**2 * t * y1 + 3 * u * t**2 * y2 + t**3 * y3
        length += math.hypot(x - px, y - py)
        px, py = x, y
    return length


def compute_segment_lengths(abs_commands: list[tuple[str, list[float]]]) -> list[float]:
    """Return a list of segment lengths (one per command after the initial M)."""
    lengths: list[float] = []
    cx, cy = 0.0, 0.0
    prev_cp = None  # previous control point for S command

    for cmd, args in abs_commands:
        if cmd == "M":
            cx, cy = args[0], args[1]
            prev_cp = None
        elif cmd == "L":
            lengths.append(_line_length(cx, cy, args[0], args[1]))
            cx, cy = args[0], args[1]
            prev_cp = None
        elif cmd == "C":
            lengths.append(
                _cubic_bezier_length(
                    cx,
                    cy,
                    args[0],
                    args[1],
                    args[2],
                    args[3],
                    args[4],
                    args[5],
                )
            )
            prev_cp = (args[2], args[3])
            cx, cy = args[4], args[5]
        elif cmd == "S":
            # Reflect previous control point
            if prev_cp:
                cp1x = 2 * cx - prev_cp[0]
                cp1y = 2 * cy - prev_cp[1]
            else:
                cp1x, cp1y = cx, cy
            lengths.append(
                _cubic_bezier_length(
                    cx,
                    cy,
                    cp1x,
                    cp1y,
                    args[0],
                    args[1],
                    args[2],
                    args[3],
                )
            )
            prev_cp = (args[0], args[1])
            cx, cy = args[2], args[3]
        elif cmd == "Z":
            # skip
            prev_cp = None
        else:
            # Fallback: use straight-line distance to the endpoint
            if len(args) >= 2:
                ex, ey = args[-2], args[-1]
                lengths.append(_line_length(cx, cy, ex, ey))
                cx, cy = ex, ey
            prev_cp = None

    return lengths


def cumulative_t(segment_lengths: list[float]) -> list[float]:
    """Return the cumulative parameter t ∈ [0,1] at each anchor point.

    Index 0 → t=0.0 (start), index len(segment_lengths) → t=1.0 (end).
    Returns len(segment_lengths)+1 values.
    """
    total = sum(segment_lengths)
    if total == 0:
        n = len(segment_lengths) + 1
        return [i / max(n - 1, 1) for i in range(n)]
    ts = [0.0]
    acc = 0.0
    for sl in segment_lengths:
        acc += sl
        ts.append(acc / total)
    return ts


# ---------------------------------------------------------------------------
# Evaluate a point on a segment at parameter t ∈ [0,1]
# ---------------------------------------------------------------------------


def _eval_cubic(sx, sy, x1, y1, x2, y2, x3, y3, t):
    """Evaluate cubic bezier (sx,sy)→(x1,y1)→(x2,y2)→(x3,y3) at t."""
    u = 1 - t
    x = u**3 * sx + 3 * u**2 * t * x1 + 3 * u * t**2 * x2 + t**3 * x3
    y = u**3 * sy + 3 * u**2 * t * y1 + 3 * u * t**2 * y2 + t**3 * y3
    return x, y


def _eval_line(sx, sy, ex, ey, t):
    """Evaluate a line segment at t."""
    return sx + t * (ex - sx), sy + t * (ey - sy)


def _eval_segment(cmd, args, sx, sy, t):
    """Evaluate any segment (L or C) at parameter t."""
    if cmd == "L":
        return _eval_line(sx, sy, args[0], args[1], t)
    elif cmd == "C":
        return _eval_cubic(
            sx, sy, args[0], args[1], args[2], args[3], args[4], args[5], t
        )
    else:
        # Fallback: treat as line to endpoint
        if len(args) >= 2:
            return _eval_line(sx, sy, args[-2], args[-1], t)
        return sx, sy


# ---------------------------------------------------------------------------
# Cubic bezier tangent (for offset normal computation)
# ---------------------------------------------------------------------------


def _cubic_tangent(sx, sy, x1, y1, x2, y2, x3, y3, t):
    """Return the tangent vector (dx, dy) of a cubic bezier at t."""
    u = 1 - t
    dx = 3 * u**2 * (x1 - sx) + 6 * u * t * (x2 - x1) + 3 * t**2 * (x3 - x2)
    dy = 3 * u**2 * (y1 - sy) + 6 * u * t * (y2 - y1) + 3 * t**2 * (y3 - y2)
    return dx, dy


def _segment_normal(cmd, args, sx, sy, t):
    """Return the unit outward normal of a segment at parameter t.

    Convention: rotate tangent 90° clockwise → (dy, -dx) normalized.
    This gives a consistent "right-side" normal.
    """
    if cmd == "C":
        dx, dy = _cubic_tangent(
            sx, sy, args[0], args[1], args[2], args[3], args[4], args[5], t
        )
    elif cmd == "L":
        dx, dy = args[0] - sx, args[1] - sy
    else:
        if len(args) >= 2:
            dx, dy = args[-2] - sx, args[-1] - sy
        else:
            dx, dy = 1.0, 0.0
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return 0.0, 0.0
    return dy / length, -dx / length


# ---------------------------------------------------------------------------
# Equidistance / parallel check
# ---------------------------------------------------------------------------

# Maximum allowed spread (max_dist - min_dist) within a segment pair
# before flagging as non-equidistant.
EQUIDIST_SPREAD_THRESHOLD = 0.5

# Number of samples per segment for equidistance check.
EQUIDIST_SAMPLES = 11


def _segment_startpoint(abs_commands, seg_index):
    """Get the start point of segment at seg_index (0-based among drawing cmds).

    abs_commands[0] is assumed to be M.  Drawing commands start at index 1.
    """
    cx, cy = abs_commands[0][1][0], abs_commands[0][1][1]
    for i in range(1, seg_index + 1):
        cmd, args = abs_commands[i]
        if cmd == "L":
            cx, cy = args[0], args[1]
        elif cmd == "C":
            cx, cy = args[4], args[5]
        elif cmd == "M":
            cx, cy = args[0], args[1]
    return cx, cy


def check_equidistance(
    b_cmds: list[tuple[str, list[float]]],
    g_cmds: list[tuple[str, list[float]]],
) -> list[int]:
    """Check per-segment equidistance between black and gray paths.

    For each pair of corresponding segments, sample at the same local
    parameter t and measure the distance.  If the spread (max-min) exceeds
    the threshold, flag that segment index.

    Line pairs with significantly different lengths (>1.0 unit difference)
    are skipped — these are intentional bevel geometry (e.g. slot lines).

    Returns a list of segment indices (0-based among drawing commands)
    where equidistance is violated.
    """
    # Drawing commands (skip initial M)
    b_draw = b_cmds[1:] if b_cmds and b_cmds[0][0] == "M" else b_cmds
    g_draw = g_cmds[1:] if g_cmds and g_cmds[0][0] == "M" else g_cmds

    if len(b_draw) != len(g_draw):
        return []  # can't check with different segment counts

    bad_segments: list[int] = []

    # Walk through segments, tracking current point for each path
    b_cx, b_cy = b_cmds[0][1][0], b_cmds[0][1][1]
    g_cx, g_cy = g_cmds[0][1][0], g_cmds[0][1][1]

    for seg_i in range(len(b_draw)):
        b_cmd, b_args = b_draw[seg_i]
        g_cmd, g_args = g_draw[seg_i]

        # Skip Z commands
        if b_cmd == "Z" or g_cmd == "Z":
            continue

        # Compute segment lengths for the skip check
        if b_cmd == "L":
            b_len = _line_length(b_cx, b_cy, b_args[0], b_args[1])
        elif b_cmd == "C":
            b_len = _cubic_bezier_length(
                b_cx,
                b_cy,
                b_args[0],
                b_args[1],
                b_args[2],
                b_args[3],
                b_args[4],
                b_args[5],
            )
        else:
            b_len = 0

        if g_cmd == "L":
            g_len = _line_length(g_cx, g_cy, g_args[0], g_args[1])
        elif g_cmd == "C":
            g_len = _cubic_bezier_length(
                g_cx,
                g_cy,
                g_args[0],
                g_args[1],
                g_args[2],
                g_args[3],
                g_args[4],
                g_args[5],
            )
        else:
            g_len = 0

        # Skip line pairs with significantly different lengths (bevel geometry)
        if b_cmd == "L" and g_cmd == "L" and abs(b_len - g_len) > 1.0:
            # Update current points and continue
            b_cx, b_cy = b_args[0], b_args[1]
            g_cx, g_cy = g_args[0], g_args[1]
            continue

        # Sample at EQUIDIST_SAMPLES evenly-spaced t values
        distances: list[float] = []
        for si in range(EQUIDIST_SAMPLES):
            t = si / (EQUIDIST_SAMPLES - 1)
            bx, by = _eval_segment(b_cmd, b_args, b_cx, b_cy, t)
            gx, gy = _eval_segment(g_cmd, g_args, g_cx, g_cy, t)
            distances.append(math.hypot(bx - gx, by - gy))

        if distances:
            spread = max(distances) - min(distances)
            if spread > EQUIDIST_SPREAD_THRESHOLD:
                bad_segments.append(seg_i)

        # Update current points
        if b_cmd == "L":
            b_cx, b_cy = b_args[0], b_args[1]
        elif b_cmd == "C":
            b_cx, b_cy = b_args[4], b_args[5]

        if g_cmd == "L":
            g_cx, g_cy = g_args[0], g_args[1]
        elif g_cmd == "C":
            g_cx, g_cy = g_args[4], g_args[5]

    return bad_segments


# ---------------------------------------------------------------------------
# Ordering-consistency check
# ---------------------------------------------------------------------------


def check_ordering(
    black_pts: list[tuple[float, float]],
    gray_pts: list[tuple[float, float]],
    black_t: list[float],
    gray_t: list[float],
    max_offset: float,
) -> list[int]:
    """Check whether matching by proportional arc length gives consistent pairing.

    For each black anchor point at parameter t_b, find the two surrounding gray
    points (by their t_g values) and see if the interpolated gray position is
    within `max_offset` of the black point's expected neighborhood.

    Returns list of black-point indices where the ordering is inconsistent.
    """
    bad_indices: list[int] = []

    if len(black_pts) != len(gray_pts):
        return []  # can't check ordering with different counts

    # Simple pairwise check: matched points should move in roughly the same
    # direction along the path.
    for i in range(len(black_pts)):
        bx, by = black_pts[i]
        gx, gy = gray_pts[i]
        dist = math.hypot(bx - gx, by - gy)
        if dist > max_offset:
            bad_indices.append(i)

    # Also check monotonicity of displacement direction
    if len(black_pts) >= 2:
        # Compute direction vectors between consecutive matched pairs
        for i in range(len(black_pts) - 1):
            bx0, by0 = black_pts[i]
            bx1, by1 = black_pts[i + 1]
            gx0, gy0 = gray_pts[i]
            gx1, gy1 = gray_pts[i + 1]

            # Direction of travel on black vs gray path
            bdx, bdy = bx1 - bx0, by1 - by0
            gdx, gdy = gx1 - gx0, gy1 - gy0

            # If both segments are non-trivial, check that they go in roughly
            # the same direction (dot product > 0)
            blen = math.hypot(bdx, bdy)
            glen = math.hypot(gdx, gdy)
            if blen > 0.01 and glen > 0.01:
                dot = (bdx * gdx + bdy * gdy) / (blen * glen)
                if dot < -0.5:  # significantly opposite direction
                    if i not in bad_indices:
                        bad_indices.append(i)
                    if (i + 1) not in bad_indices:
                        bad_indices.append(i + 1)

    return sorted(set(bad_indices))


def check_segment_types(
    b_cmds: list[tuple[str, list[float]]],
    g_cmds: list[tuple[str, list[float]]],
) -> list[int]:
    """Return drawing-segment indices where the black and gray paths have
    different command types (e.g. one is L and the other is C).

    Both command lists must already be normalized (S expanded, zero-length
    removed) and have the same number of drawing segments.  Only drawing
    commands (L, C) are compared; the leading M is skipped.
    """
    b_draw = b_cmds[1:] if b_cmds and b_cmds[0][0] == "M" else b_cmds
    g_draw = g_cmds[1:] if g_cmds and g_cmds[0][0] == "M" else g_cmds

    bad: list[int] = []
    for i in range(min(len(b_draw), len(g_draw))):
        bc = b_draw[i][0]
        gc = g_draw[i][0]
        if bc != gc:
            bad.append(i)
    return bad


# ---------------------------------------------------------------------------
# Expand S (smooth cubic) into C
# ---------------------------------------------------------------------------


def expand_smooth_cubics(
    abs_commands: list[tuple[str, list[float]]],
) -> list[tuple[str, list[float]]]:
    """Convert all S commands to C by computing the reflected control point."""
    out: list[tuple[str, list[float]]] = []
    cx, cy = 0.0, 0.0
    prev_cp = None

    for cmd, args in abs_commands:
        if cmd == "M":
            out.append((cmd, list(args)))
            cx, cy = args[0], args[1]
            prev_cp = None
        elif cmd == "C":
            out.append((cmd, list(args)))
            prev_cp = (args[2], args[3])
            cx, cy = args[4], args[5]
        elif cmd == "S":
            if prev_cp:
                cp1x = 2 * cx - prev_cp[0]
                cp1y = 2 * cy - prev_cp[1]
            else:
                cp1x, cp1y = cx, cy
            out.append(("C", [cp1x, cp1y, args[0], args[1], args[2], args[3]]))
            prev_cp = (args[0], args[1])
            cx, cy = args[2], args[3]
        elif cmd == "L":
            out.append((cmd, list(args)))
            cx, cy = args[0], args[1]
            prev_cp = None
        elif cmd == "Z":
            out.append((cmd, []))
            prev_cp = None
        else:
            out.append((cmd, list(args)))
            if len(args) >= 2:
                cx, cy = args[-2], args[-1]
            prev_cp = None
    return out


# ---------------------------------------------------------------------------
# Remove zero-length segments
# ---------------------------------------------------------------------------


def remove_zero_segments(
    abs_commands: list[tuple[str, list[float]]], eps: float = 0.05
) -> list[tuple[str, list[float]]]:
    """Remove segments whose start and end are within eps of each other."""
    out: list[tuple[str, list[float]]] = []
    cx, cy = 0.0, 0.0
    for cmd, args in abs_commands:
        if cmd == "M":
            out.append((cmd, list(args)))
            cx, cy = args[0], args[1]
        elif cmd == "L":
            ex, ey = args[0], args[1]
            if math.hypot(ex - cx, ey - cy) > eps:
                out.append((cmd, list(args)))
                cx, cy = ex, ey
            # else: skip zero-length line
        elif cmd == "C":
            ex, ey = args[4], args[5]
            # Check if all control points and endpoint are at current pos
            all_close = all(
                math.hypot(args[i] - cx, args[i + 1] - cy) < eps for i in range(0, 6, 2)
            )
            if not all_close:
                out.append((cmd, list(args)))
                cx, cy = ex, ey
        elif cmd == "Z":
            out.append((cmd, []))
        else:
            out.append((cmd, list(args)))
            if len(args) >= 2:
                cx, cy = args[-2], args[-1]
    return out


# ---------------------------------------------------------------------------
# Convert a line segment into a degenerate cubic bezier (for count matching)
# ---------------------------------------------------------------------------


def line_to_cubic(cx, cy, ex, ey) -> tuple[str, list[float]]:
    """Convert L to a degenerate C with control points on the line."""
    return (
        "C",
        [
            cx + (ex - cx) / 3,
            cy + (ey - cy) / 3,
            cx + 2 * (ex - cx) / 3,
            cy + 2 * (ey - cy) / 3,
            ex,
            ey,
        ],
    )


# ---------------------------------------------------------------------------
# Subdivide a cubic bezier at t using de Casteljau
# ---------------------------------------------------------------------------


def subdivide_cubic(cx, cy, x1, y1, x2, y2, x3, y3, t):
    """Split cubic (cx,cy)→(x1,y1)→(x2,y2)→(x3,y3) at parameter t.

    Returns (left_args, right_args) where each is [cp1x,cp1y,cp2x,cp2y,ex,ey].
    """
    u = 1 - t
    # Level 1
    ax, ay = u * cx + t * x1, u * cy + t * y1
    bx, by = u * x1 + t * x2, u * y1 + t * y2
    dx, dy = u * x2 + t * x3, u * y2 + t * y3
    # Level 2
    ex_, ey_ = u * ax + t * bx, u * ay + t * by
    fx, fy = u * bx + t * dx, u * by + t * dy
    # Level 3 (point on curve)
    gx, gy = u * ex_ + t * fx, u * ey_ + t * fy

    left = [ax, ay, ex_, ey_, gx, gy]
    right = [fx, fy, dx, dy, x3, y3]
    return left, right


# ---------------------------------------------------------------------------
# Discretize cubic beziers into line segments (tangent-preserving)
# ---------------------------------------------------------------------------


def _discretize_cubic(
    sx: float,
    sy: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
    n: int,
) -> list[tuple[str, list[float]]]:
    """Replace a cubic bezier with n-1 line segments through n control points.

    The first and last line segments are aligned with the cubic's tangent at
    t=0 and t=1 respectively, so that the angle with neighboring segments is
    preserved exactly.

    Strategy:
    - Point 0 = (sx, sy)           [start, implicit — not emitted]
    - Point n-1 = (x3, y3)         [end]
    - Point 1: placed on the t=0 tangent ray from (sx,sy), at a distance
      equal to the chord from (sx,sy) to cubic(1/(n-1)).
    - Point n-2: placed on the t=1 tangent ray toward (x3,y3), at a distance
      equal to the chord from cubic((n-2)/(n-1)) to (x3,y3).
    - Interior points 2..n-3: sampled directly on the cubic.

    For n <= 2 this degenerates: n=2 gives a single line from start to end.
    For n = 3 we get two line segments forced along the tangents; the meeting
    point is the intersection of the two tangent rays (or the midpoint if
    rays are parallel).
    """
    if n < 2:
        n = 2

    if n == 2:
        # Single line segment from start to end
        return [("L", [x3, y3])]

    # Tangent at t=0: derivative of cubic
    tan0_dx = 3 * (x1 - sx)
    tan0_dy = 3 * (y1 - sy)
    # If first control point coincides with start, use second derivative
    if abs(tan0_dx) < 1e-12 and abs(tan0_dy) < 1e-12:
        tan0_dx = 6 * (x2 - 2 * x1 + sx)
        tan0_dy = 6 * (y2 - 2 * y1 + sy)
    tan0_len = math.hypot(tan0_dx, tan0_dy)
    if tan0_len > 1e-12:
        tan0_ux, tan0_uy = tan0_dx / tan0_len, tan0_dy / tan0_len
    else:
        tan0_ux, tan0_uy = (x3 - sx), (y3 - sy)
        d = math.hypot(tan0_ux, tan0_uy)
        if d > 1e-12:
            tan0_ux /= d
            tan0_uy /= d
        else:
            tan0_ux, tan0_uy = 1.0, 0.0

    # Tangent at t=1: derivative of cubic at t=1
    tan1_dx = 3 * (x3 - x2)
    tan1_dy = 3 * (y3 - y2)
    if abs(tan1_dx) < 1e-12 and abs(tan1_dy) < 1e-12:
        tan1_dx = 6 * (x3 - 2 * x2 + x1)
        tan1_dy = 6 * (y3 - 2 * y2 + y1)
    tan1_len = math.hypot(tan1_dx, tan1_dy)
    if tan1_len > 1e-12:
        tan1_ux, tan1_uy = tan1_dx / tan1_len, tan1_dy / tan1_len
    else:
        tan1_ux, tan1_uy = (x3 - sx), (y3 - sy)
        d = math.hypot(tan1_ux, tan1_uy)
        if d > 1e-12:
            tan1_ux /= d
            tan1_uy /= d
        else:
            tan1_ux, tan1_uy = 1.0, 0.0

    # Sample n evenly-spaced points on the cubic (including endpoints)
    raw_pts: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        px, py = _eval_cubic(sx, sy, x1, y1, x2, y2, x3, y3, t)
        raw_pts.append((px, py))

    # Build final point list
    pts: list[tuple[float, float]] = [None] * n  # type: ignore
    pts[0] = (sx, sy)
    pts[n - 1] = (x3, y3)

    # Minimum distance threshold: tangent-aligned points that would be closer
    # than this to their anchor endpoint fall back to the raw curve sample,
    # preventing near-zero-length segments that confuse the validator.
    min_seg = 0.06

    # Chord direction from start to end
    chord_dx, chord_dy = x3 - sx, y3 - sy

    # Point 1: on the tangent at t=0, at the same distance as the raw sample
    raw_dist_1 = math.hypot(raw_pts[1][0] - sx, raw_pts[1][1] - sy)
    if raw_dist_1 > min_seg:
        cand = (sx + tan0_ux * raw_dist_1, sy + tan0_uy * raw_dist_1)
        # Guard against overshoot: if the tangent direction opposes the
        # chord direction (dot product < 0), or the tangent-placed point
        # is farther from the end than the start is, fall back to raw.
        dot0 = tan0_ux * chord_dx + tan0_uy * chord_dy
        cand_dist_to_end = math.hypot(cand[0] - x3, cand[1] - y3)
        start_dist_to_end = math.hypot(sx - x3, sy - y3)
        if dot0 < 0 or cand_dist_to_end > start_dist_to_end + 1e-9:
            pts[1] = raw_pts[1]
        else:
            pts[1] = cand
    else:
        pts[1] = raw_pts[1]

    # Point n-2: on the tangent at t=1, behind (x3,y3) by the raw distance
    if n >= 3:
        raw_dist_last = math.hypot(raw_pts[n - 2][0] - x3, raw_pts[n - 2][1] - y3)
        if raw_dist_last > min_seg:
            # The tangent at t=1 points *forward* from the curve, so the
            # point before the end is in the -tangent direction from the end.
            cand_last = (
                x3 - tan1_ux * raw_dist_last,
                y3 - tan1_uy * raw_dist_last,
            )
            # Guard against overshoot: if the reversed tangent direction
            # opposes the reversed chord, or the candidate is farther from
            # the start than the end is, fall back to raw.
            dot1 = (-tan1_ux) * (-chord_dx) + (-tan1_uy) * (-chord_dy)
            cand_dist_to_start = math.hypot(cand_last[0] - sx, cand_last[1] - sy)
            end_dist_to_start = math.hypot(x3 - sx, y3 - sy)
            if dot1 < 0 or cand_dist_to_start > end_dist_to_start + 1e-9:
                pts[n - 2] = raw_pts[n - 2]
            else:
                pts[n - 2] = cand_last
        else:
            pts[n - 2] = raw_pts[n - 2]

    # Interior points (2..n-3): use raw samples directly
    for i in range(2, n - 2):
        pts[i] = raw_pts[i]

    # Emit n-1 line segments (point 0 is implicit start, not emitted)
    result: list[tuple[str, list[float]]] = []
    for i in range(1, n):
        result.append(("L", [pts[i][0], pts[i][1]]))
    return result


def discretize_commands(
    abs_commands: list[tuple[str, list[float]]],
    n: int,
) -> list[tuple[str, list[float]]]:
    """Replace all cubic bezier (C) segments with tangent-preserving
    line-segment approximations using n control points per arc.

    L, M, Z commands are passed through unchanged.
    """
    out: list[tuple[str, list[float]]] = []
    cx, cy = 0.0, 0.0

    for cmd, args in abs_commands:
        if cmd == "M":
            out.append((cmd, list(args)))
            cx, cy = args[0], args[1]
        elif cmd == "C":
            lines = _discretize_cubic(
                cx,
                cy,
                args[0],
                args[1],
                args[2],
                args[3],
                args[4],
                args[5],
                n,
            )
            out.extend(lines)
            cx, cy = args[4], args[5]
        elif cmd == "L":
            out.append((cmd, list(args)))
            cx, cy = args[0], args[1]
        elif cmd == "Z":
            out.append((cmd, []))
        else:
            out.append((cmd, list(args)))
            if len(args) >= 2:
                cx, cy = args[-2], args[-1]

    return out


def _subdivide_line(
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    n: int,
) -> list[tuple[str, list[float]]]:
    """Subdivide a line segment into n-1 equal-length line segments
    through n control points (matching the output count of a discretized
    cubic so that paired paths maintain segment-count parity).
    """
    if n < 2:
        n = 2
    result: list[tuple[str, list[float]]] = []
    for i in range(1, n):
        t = i / (n - 1)
        px = sx + t * (ex - sx)
        py = sy + t * (ey - sy)
        result.append(("L", [px, py]))
    return result


def _discretize_pair_member(
    this_cmds: list[tuple[str, list[float]]],
    other_cmds: list[tuple[str, list[float]]],
    n: int,
    collapse_indices: set[int] | None = None,
) -> list[tuple[str, list[float]]]:
    """Discretize *this_cmds*, expanding segments to n-1 line segments
    whenever *either* this path or the *other* path has a C at that index.

    If *collapse_indices* is provided, segments at those indices are
    collapsed to a single L from start to end instead of being discretized,
    regardless of whether they are C or L.  This is used to avoid producing
    many tiny segments from very short curves.

    This ensures both paths in a pair produce the same number of output
    segments after discretization.
    """
    if collapse_indices is None:
        collapse_indices = set()

    # Separate M from drawing commands
    this_draw = this_cmds[1:] if this_cmds and this_cmds[0][0] == "M" else this_cmds
    other_draw = (
        other_cmds[1:] if other_cmds and other_cmds[0][0] == "M" else other_cmds
    )

    out: list[tuple[str, list[float]]] = []
    if this_cmds and this_cmds[0][0] == "M":
        out.append(("M", list(this_cmds[0][1])))

    cx, cy = (this_cmds[0][1][0], this_cmds[0][1][1]) if this_cmds else (0.0, 0.0)

    for i, (cmd, args) in enumerate(this_draw):
        # Check if the other path has a C at this index
        other_is_curve = i < len(other_draw) and other_draw[i][0] == "C"

        # If this segment is flagged for collapsing, emit a single L
        if i in collapse_indices:
            if cmd == "C":
                out.append(("L", [args[4], args[5]]))
                cx, cy = args[4], args[5]
            elif cmd == "L":
                out.append(("L", list(args)))
                cx, cy = args[0], args[1]
            elif cmd == "M":
                out.append((cmd, list(args)))
                cx, cy = args[0], args[1]
            else:
                out.append((cmd, list(args)))
            continue

        if cmd == "M":
            out.append((cmd, list(args)))
            cx, cy = args[0], args[1]
        elif cmd == "C":
            # Always discretize curves
            lines = _discretize_cubic(
                cx,
                cy,
                args[0],
                args[1],
                args[2],
                args[3],
                args[4],
                args[5],
                n,
            )
            out.extend(lines)
            cx, cy = args[4], args[5]
        elif cmd == "L":
            if other_is_curve:
                # Subdivide this line into n-1 segments to match the
                # other path's discretized curve
                lines = _subdivide_line(cx, cy, args[0], args[1], n)
                out.extend(lines)
            else:
                out.append((cmd, list(args)))
            cx, cy = args[0], args[1]
        elif cmd == "Z":
            out.append((cmd, []))
        else:
            out.append((cmd, list(args)))
            if len(args) >= 2:
                cx, cy = args[-2], args[-1]

    return out


def _find_collapse_indices(
    b_cmds: list[tuple[str, list[float]]],
    g_cmds: list[tuple[str, list[float]]],
    n: int,
    eps: float = 0.05,
) -> set[int]:
    """Identify segment indices where at least one path's curve has a chord
    length so small that discretizing it into n-1 segments would produce
    segments shorter than *eps*.  Both paths should collapse such segments
    together to maintain parity.

    Also collapses curves with a very high control-polygon-to-chord ratio
    (S-curves) where discretization would produce direction reversals.
    """
    b_draw = b_cmds[1:] if b_cmds and b_cmds[0][0] == "M" else b_cmds
    g_draw = g_cmds[1:] if g_cmds and g_cmds[0][0] == "M" else g_cmds

    # Minimum chord length: if chord/(n-1) < eps, the segments would be
    # individually shorter than the zero-segment threshold.
    min_chord = eps * (n - 1)
    # Maximum control-polygon/chord ratio before collapsing.  A high ratio
    # indicates an S-curve that will zig-zag when discretized.
    max_poly_chord_ratio = 3.0

    collapse = set()
    b_cx, b_cy = (b_cmds[0][1][0], b_cmds[0][1][1]) if b_cmds else (0.0, 0.0)
    g_cx, g_cy = (g_cmds[0][1][0], g_cmds[0][1][1]) if g_cmds else (0.0, 0.0)

    for i in range(max(len(b_draw), len(g_draw))):
        b_collapse = False
        g_collapse = False

        if i < len(b_draw):
            bc, ba = b_draw[i]
            if bc == "C":
                chord = math.hypot(ba[4] - b_cx, ba[5] - b_cy)
                if chord < min_chord:
                    b_collapse = True
                elif chord > 1e-9:
                    # Check control polygon length / chord ratio
                    poly = (
                        math.hypot(ba[0] - b_cx, ba[1] - b_cy)
                        + math.hypot(ba[2] - ba[0], ba[3] - ba[1])
                        + math.hypot(ba[4] - ba[2], ba[5] - ba[3])
                    )
                    if poly / chord > max_poly_chord_ratio:
                        b_collapse = True
                b_cx, b_cy = ba[4], ba[5]
            elif bc == "L":
                b_cx, b_cy = ba[0], ba[1]

        if i < len(g_draw):
            gc, ga = g_draw[i]
            if gc == "C":
                chord = math.hypot(ga[4] - g_cx, ga[5] - g_cy)
                if chord < min_chord:
                    g_collapse = True
                elif chord > 1e-9:
                    poly = (
                        math.hypot(ga[0] - g_cx, ga[1] - g_cy)
                        + math.hypot(ga[2] - ga[0], ga[3] - ga[1])
                        + math.hypot(ga[4] - ga[2], ga[5] - ga[3])
                    )
                    if poly / chord > max_poly_chord_ratio:
                        g_collapse = True
                g_cx, g_cy = ga[4], ga[5]
            elif gc == "L":
                g_cx, g_cy = ga[0], ga[1]

        if b_collapse or g_collapse:
            collapse.add(i)

    return collapse


def _remove_zero_segments_paired(
    b_cmds: list[tuple[str, list[float]]],
    g_cmds: list[tuple[str, list[float]]],
    eps: float = 0.05,
) -> tuple[list[tuple[str, list[float]]], list[tuple[str, list[float]]]]:
    """Remove zero-length segments from both paths in sync.

    A segment at index i is only removed if it is zero-length in *both*
    paths.  This preserves point-count parity.
    """
    # Separate M from drawing commands
    b_m = b_cmds[0] if b_cmds and b_cmds[0][0] == "M" else ("M", [0.0, 0.0])
    g_m = g_cmds[0] if g_cmds and g_cmds[0][0] == "M" else ("M", [0.0, 0.0])
    b_draw = b_cmds[1:] if b_cmds and b_cmds[0][0] == "M" else b_cmds
    g_draw = g_cmds[1:] if g_cmds and g_cmds[0][0] == "M" else g_cmds

    if len(b_draw) != len(g_draw):
        # Can't do paired removal if lengths differ; return as-is
        return b_cmds, g_cmds

    b_out = [b_m]
    g_out = [g_m]
    b_cx, b_cy = b_m[1][0], b_m[1][1]
    g_cx, g_cy = g_m[1][0], g_m[1][1]

    for i in range(len(b_draw)):
        b_cmd, b_args = b_draw[i]
        g_cmd, g_args = g_draw[i]

        # Determine endpoints
        b_ex, b_ey = b_args[0], b_args[1]  # works for L
        g_ex, g_ey = g_args[0], g_args[1]
        if b_cmd == "C":
            b_ex, b_ey = b_args[4], b_args[5]
        if g_cmd == "C":
            g_ex, g_ey = g_args[4], g_args[5]

        b_zero = math.hypot(b_ex - b_cx, b_ey - b_cy) < eps
        g_zero = math.hypot(g_ex - g_cx, g_ey - g_cy) < eps

        if b_zero and g_zero:
            # Both are zero-length: skip both
            pass
        else:
            b_out.append((b_cmd, list(b_args)))
            g_out.append((g_cmd, list(g_args)))

        b_cx, b_cy = b_ex, b_ey
        g_cx, g_cy = g_ex, g_ey

    return b_out, g_out


# ---------------------------------------------------------------------------
# Offset curve generation and cubic bezier fitting
# ---------------------------------------------------------------------------

# Number of sample points for offset curve fitting.
OFFSET_FIT_SAMPLES = 40


def _compute_group_offset(
    b_cmds: list[tuple[str, list[float]]],
    g_cmds: list[tuple[str, list[float]]],
) -> float:
    """Determine the signed offset distance from black to gray path.

    Positive = gray is on the right-hand-normal side of the black path.
    Negative = gray is on the left-hand-normal side.

    Uses the first well-behaved segment (low equidistance spread) to
    determine the sign and magnitude.
    """
    b_draw = b_cmds[1:] if b_cmds and b_cmds[0][0] == "M" else b_cmds
    g_draw = g_cmds[1:] if g_cmds and g_cmds[0][0] == "M" else g_cmds

    if len(b_draw) != len(g_draw):
        return 4.25  # fallback

    b_cx, b_cy = b_cmds[0][1][0], b_cmds[0][1][1]
    g_cx, g_cy = g_cmds[0][1][0], g_cmds[0][1][1]

    for seg_i in range(len(b_draw)):
        b_cmd, b_args = b_draw[seg_i]
        g_cmd, g_args = g_draw[seg_i]

        if b_cmd == "Z" or g_cmd == "Z":
            continue

        # Check if this segment has reasonable distance (not degenerate)
        bx, by = _eval_segment(b_cmd, b_args, b_cx, b_cy, 0.5)
        gx, gy = _eval_segment(g_cmd, g_args, g_cx, g_cy, 0.5)
        dist = math.hypot(bx - gx, by - gy)

        if dist > 1.0:
            # Check equidistance spread for this segment
            distances = []
            for si in range(EQUIDIST_SAMPLES):
                t = si / (EQUIDIST_SAMPLES - 1)
                bxi, byi = _eval_segment(b_cmd, b_args, b_cx, b_cy, t)
                gxi, gyi = _eval_segment(g_cmd, g_args, g_cx, g_cy, t)
                distances.append(math.hypot(bxi - gxi, byi - gyi))

            spread = max(distances) - min(distances)
            if spread < EQUIDIST_SPREAD_THRESHOLD:
                # This is a well-behaved segment — use it to determine offset
                nx, ny = _segment_normal(b_cmd, b_args, b_cx, b_cy, 0.5)
                dx, dy = gx - bx, gy - by
                dot = dx * nx + dy * ny
                # sign: positive means gray is in the normal direction
                avg_dist = sum(distances) / len(distances)
                return avg_dist if dot > 0 else -avg_dist

        if b_cmd == "L":
            b_cx, b_cy = b_args[0], b_args[1]
        elif b_cmd == "C":
            b_cx, b_cy = b_args[4], b_args[5]
        if g_cmd == "L":
            g_cx, g_cy = g_args[0], g_args[1]
        elif g_cmd == "C":
            g_cx, g_cy = g_args[4], g_args[5]

    # Fallback: use start points
    bx0, by0 = b_cmds[0][1][0], b_cmds[0][1][1]
    gx0, gy0 = g_cmds[0][1][0], g_cmds[0][1][1]
    return math.hypot(gx0 - bx0, gy0 - by0) or 4.25


def _fit_cubic_bezier(
    points: list[tuple[float, float]],
    t_values: list[float],
) -> list[float]:
    """Fit a cubic bezier to a set of 2D points with known parameter values.

    Given points P_i at parameters t_i, find control points CP1, CP2 that
    minimize the least-squares error, with endpoints pinned to points[0]
    and points[-1].

    Returns [cp1x, cp1y, cp2x, cp2y, ex, ey] where (ex, ey) = points[-1].
    """
    sx, sy = points[0]
    ex, ey = points[-1]

    # We solve for CP1 and CP2 in the least-squares sense.
    # B(t) = (1-t)^3 P0 + 3(1-t)^2 t CP1 + 3(1-t) t^2 CP2 + t^3 P3
    # Rearranging: B(t) - (1-t)^3 P0 - t^3 P3 = 3(1-t)^2 t CP1 + 3(1-t) t^2 CP2
    # This is a linear system in [CP1x, CP1y, CP2x, CP2y].

    # Use interior points only (skip first and last)
    n = len(points)
    if n <= 2:
        # Degenerate: straight line
        return [
            sx + (ex - sx) / 3,
            sy + (ey - sy) / 3,
            sx + 2 * (ex - sx) / 3,
            sy + 2 * (ey - sy) / 3,
            ex,
            ey,
        ]

    # Build the normal equations (2x2 system, solved for x and y separately)
    # A1(t) = 3(1-t)^2 * t
    # A2(t) = 3(1-t) * t^2
    # For each point: A1(t)*CP1 + A2(t)*CP2 = P(t) - (1-t)^3*P0 - t^3*P3

    a11 = a12 = a22 = 0.0
    bx1 = by1 = bx2 = by2 = 0.0

    for i in range(n):
        t = t_values[i]
        u = 1 - t
        a1 = 3 * u * u * t
        a2 = 3 * u * t * t
        # Right-hand side
        rx = points[i][0] - u**3 * sx - t**3 * ex
        ry = points[i][1] - u**3 * sy - t**3 * ey

        a11 += a1 * a1
        a12 += a1 * a2
        a22 += a2 * a2
        bx1 += a1 * rx
        by1 += a1 * ry
        bx2 += a2 * rx
        by2 += a2 * ry

    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-12:
        # Degenerate: use 1/3 rule
        return [
            sx + (ex - sx) / 3,
            sy + (ey - sy) / 3,
            sx + 2 * (ex - sx) / 3,
            sy + 2 * (ey - sy) / 3,
            ex,
            ey,
        ]

    cp1x = (a22 * bx1 - a12 * bx2) / det
    cp1y = (a22 * by1 - a12 * by2) / det
    cp2x = (a11 * bx2 - a12 * bx1) / det
    cp2y = (a11 * by2 - a12 * by1) / det

    return [cp1x, cp1y, cp2x, cp2y, ex, ey]


def _generate_offset_segment(
    b_cmd: str,
    b_args: list[float],
    b_sx: float,
    b_sy: float,
    g_cmd: str,
    g_args: list[float],
    g_sx: float,
    g_sy: float,
    offset: float,
) -> tuple[str, list[float]]:
    """Generate a corrected gray segment as an offset of the black segment.

    The offset is applied along the black path's normal at each sample point.
    A cubic bezier is then fitted to the resulting offset points.

    For line segments, we offset start and end along the normal and return
    a line (keeping it as L, not C).
    """
    if b_cmd == "L":
        # Offset line: compute normal (constant for a line)
        nx, ny = _segment_normal(b_cmd, b_args, b_sx, b_sy, 0.0)
        new_sx = b_sx + offset * nx
        new_sy = b_sy + offset * ny
        new_ex = b_args[0] + offset * nx
        new_ey = b_args[1] + offset * ny
        # Return as L, keeping start point implicit (it's carried over)
        return ("L", [new_ex, new_ey])

    # For cubic bezier segments: sample, offset, fit
    n_samples = OFFSET_FIT_SAMPLES
    offset_pts: list[tuple[float, float]] = []
    t_vals: list[float] = []

    for i in range(n_samples + 1):
        t = i / n_samples
        bx, by = _eval_segment(b_cmd, b_args, b_sx, b_sy, t)
        nx, ny = _segment_normal(b_cmd, b_args, b_sx, b_sy, t)
        # Handle degenerate normals at endpoints
        if abs(nx) < 1e-12 and abs(ny) < 1e-12:
            # Try a nearby t value
            t_alt = t + 0.01 if t < 0.5 else t - 0.01
            nx, ny = _segment_normal(b_cmd, b_args, b_sx, b_sy, t_alt)
        offset_pts.append((bx + offset * nx, by + offset * ny))
        t_vals.append(t)

    # Fit cubic bezier
    fitted = _fit_cubic_bezier(offset_pts, t_vals)
    return ("C", fitted)


def _fix_equidistance(
    b_cmds: list[tuple[str, list[float]]],
    g_cmds: list[tuple[str, list[float]]],
    bad_segments: list[int],
    offset: float,
) -> list[tuple[str, list[float]]]:
    """Fix non-equidistant segments in the gray path by recomputing them
    as offset curves of the corresponding black segments.

    Returns a new gray command list with bad segments replaced.
    """
    g_out = list(g_cmds)  # shallow copy

    b_draw_start = 1 if b_cmds and b_cmds[0][0] == "M" else 0
    g_draw_start = 1 if g_cmds and g_cmds[0][0] == "M" else 0

    # Walk the black path to get start points for each segment
    b_starts: list[tuple[float, float]] = []
    cx, cy = b_cmds[0][1][0], b_cmds[0][1][1]
    for i in range(b_draw_start, len(b_cmds)):
        b_starts.append((cx, cy))
        cmd, args = b_cmds[i]
        if cmd == "L":
            cx, cy = args[0], args[1]
        elif cmd == "C":
            cx, cy = args[4], args[5]

    # Walk the gray path to get start points
    g_starts: list[tuple[float, float]] = []
    cx, cy = g_cmds[0][1][0], g_cmds[0][1][1]
    for i in range(g_draw_start, len(g_cmds)):
        g_starts.append((cx, cy))
        cmd, args = g_cmds[i]
        if cmd == "L":
            cx, cy = args[0], args[1]
        elif cmd == "C":
            cx, cy = args[4], args[5]

    for seg_i in bad_segments:
        b_idx = b_draw_start + seg_i
        g_idx = g_draw_start + seg_i

        if b_idx >= len(b_cmds) or g_idx >= len(g_cmds):
            continue
        if seg_i >= len(b_starts) or seg_i >= len(g_starts):
            continue

        b_cmd, b_args = b_cmds[b_idx]
        g_cmd, g_args = g_cmds[g_idx]
        b_sx, b_sy = b_starts[seg_i]
        g_sx, g_sy = g_starts[seg_i]

        new_cmd, new_args = _generate_offset_segment(
            b_cmd,
            b_args,
            b_sx,
            b_sy,
            g_cmd,
            g_args,
            g_sx,
            g_sy,
            offset,
        )

        # For curves, we need to ensure endpoint continuity with the next
        # segment. The fitted endpoint should already be close, but we also
        # need to update the gray start point for the M command if seg_i == 0.
        if seg_i == 0 and new_cmd == "L":
            # Update M point of gray to match offset of black start
            b_mx, b_my = b_cmds[0][1][0], b_cmds[0][1][1]
            nx, ny = _segment_normal(b_cmd, b_args, b_sx, b_sy, 0.0)
            if abs(nx) < 1e-12 and abs(ny) < 1e-12:
                nx, ny = _segment_normal(b_cmd, b_args, b_sx, b_sy, 0.01)
            g_out[0] = ("M", [b_mx + offset * nx, b_my + offset * ny])

        g_out[g_idx] = (new_cmd, new_args)

    # Fix endpoint continuity: ensure each segment's start matches the
    # previous segment's end
    cx, cy = g_out[0][1][0], g_out[0][1][1]
    for i in range(g_draw_start, len(g_out)):
        cmd, args = g_out[i]
        if cmd == "L":
            cx, cy = args[0], args[1]
        elif cmd == "C":
            # If this segment was replaced, its start point should match cx,cy
            # (which is the endpoint of the previous segment). The fitted
            # cubic endpoints are already correct because we used the black
            # path's offset. But we need to check that the endpoint of the
            # previous gray segment matches the fitted curve's start.
            cx, cy = args[4], args[5]
        elif cmd == "Z":
            pass

    return g_out


# ---------------------------------------------------------------------------
# Normalize command sequences to have the same segment structure
# ---------------------------------------------------------------------------


def normalize_pair(
    black_cmds: list[tuple[str, list[float]]],
    gray_cmds: list[tuple[str, list[float]]],
) -> tuple[list[tuple[str, list[float]]], list[tuple[str, list[float]]]]:
    """Normalize a pair of absolute command lists so they have the same
    number of anchor points with consistent segment types.

    Strategy:
    1. Expand S→C on both.
    2. Remove zero-length segments on both.
    3. If counts differ, subdivide segments of the shorter path at the
       proportional arc-length positions of the longer path's anchor points.
    4. Convert L↔C where the pair has mismatched segment types.
    """
    b = expand_smooth_cubics(black_cmds)
    g = expand_smooth_cubics(gray_cmds)
    b = remove_zero_segments(b)
    g = remove_zero_segments(g)

    # Extract just the drawing commands (skip initial M)
    b_draw = b[1:] if b and b[0][0] == "M" else b
    g_draw = g[1:] if g and g[0][0] == "M" else g

    b_n = len(b_draw)
    g_n = len(g_draw)

    if b_n != g_n:
        if b_n < g_n:
            b = _add_segments_to_match(b, target_count=g_n)
        else:
            g = _add_segments_to_match(g, target_count=b_n)

    # Final unification of segment types (L↔C)
    b, g = _unify_segment_types(b, g)
    return b, g


def _unify_segment_types(
    b: list[tuple[str, list[float]]],
    g: list[tuple[str, list[float]]],
) -> tuple[list[tuple[str, list[float]]], list[tuple[str, list[float]]]]:
    """Where one has L and the other C at the same index, convert L→C."""
    b_out = list(b)
    g_out = list(g)
    cx_b, cy_b = 0.0, 0.0
    cx_g, cy_g = 0.0, 0.0
    min_len = min(len(b_out), len(g_out))

    for i in range(min_len):
        bc, ba = b_out[i]
        gc, ga = g_out[i]

        if bc == "M":
            cx_b, cy_b = ba[0], ba[1]
        if gc == "M":
            cx_g, cy_g = ga[0], ga[1]

        if bc == "L" and gc == "C":
            b_out[i] = line_to_cubic(cx_b, cy_b, ba[0], ba[1])
        elif bc == "C" and gc == "L":
            g_out[i] = line_to_cubic(cx_g, cy_g, ga[0], ga[1])

        # Update current point
        if bc in ("L", "C", "S"):
            if bc == "L":
                cx_b, cy_b = ba[0], ba[1]
            elif bc == "C":
                cx_b, cy_b = ba[4], ba[5]
        if gc in ("L", "C", "S"):
            if gc == "L":
                cx_g, cy_g = ga[0], ga[1]
            elif gc == "C":
                cx_g, cy_g = ga[4], ga[5]

    return b_out, g_out


def _add_segments_to_match(
    cmds: list[tuple[str, list[float]]],
    target_count: int,
) -> list[tuple[str, list[float]]]:
    """Subdivide segments in *cmds* until it has exactly *target_count*
    drawing segments (i.e. target_count + 1 anchor points including the M).

    At each iteration, the longest segment (by arc length) is split at its
    midpoint.  This keeps the result well-balanced.
    """
    draw = cmds[1:] if cmds and cmds[0][0] == "M" else cmds
    current_count = len(draw)
    if current_count >= target_count:
        return cmds

    # We'll work with a flat list of (cmd, args, start_x, start_y)
    # Build it once, then iteratively split the longest entry.
    entries: list[list] = []  # each: [cmd, args, sx, sy, arc_length]
    cx, cy = cmds[0][1][0], cmds[0][1][1]
    m_cmd = cmds[0]

    seg_lens = compute_segment_lengths(cmds)
    for idx, (cmd, args) in enumerate(draw):
        length = seg_lens[idx] if idx < len(seg_lens) else 0.0
        entries.append([cmd, list(args), cx, cy, length])
        if cmd == "L":
            cx, cy = args[0], args[1]
        elif cmd == "C":
            cx, cy = args[4], args[5]

    while len(entries) < target_count:
        # Find the longest segment
        best_i = max(range(len(entries)), key=lambda i: entries[i][4])
        e = entries[best_i]
        cmd, args, sx, sy, _ = e

        if cmd == "L":
            # Split line at midpoint
            ex, ey = args[0], args[1]
            mx, my = (sx + ex) / 2, (sy + ey) / 2
            left = ["L", [mx, my], sx, sy, _line_length(sx, sy, mx, my)]
            right = ["L", [ex, ey], mx, my, _line_length(mx, my, ex, ey)]
            entries[best_i : best_i + 1] = [left, right]
        elif cmd == "C":
            left_args, right_args = subdivide_cubic(
                sx,
                sy,
                args[0],
                args[1],
                args[2],
                args[3],
                args[4],
                args[5],
                0.5,
            )
            mid_x, mid_y = left_args[4], left_args[5]
            left_len = _cubic_bezier_length(
                sx,
                sy,
                left_args[0],
                left_args[1],
                left_args[2],
                left_args[3],
                left_args[4],
                left_args[5],
            )
            right_len = _cubic_bezier_length(
                mid_x,
                mid_y,
                right_args[0],
                right_args[1],
                right_args[2],
                right_args[3],
                right_args[4],
                right_args[5],
            )
            left_e = ["C", left_args, sx, sy, left_len]
            right_e = ["C", right_args, mid_x, mid_y, right_len]
            entries[best_i : best_i + 1] = [left_e, right_e]
        else:
            # Can't subdivide unknown commands; just stop
            break

    # Reassemble
    result = [m_cmd]
    for cmd, args, sx, sy, _ in entries:
        result.append((cmd, args))
    return result


# ---------------------------------------------------------------------------
# Serialize absolute commands back to a path d string
# ---------------------------------------------------------------------------


def _fmt(v: float) -> str:
    """Format a float compactly: no trailing zeros, reasonable precision."""
    s = f"{v:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def commands_to_d(cmds: list[tuple[str, list[float]]]) -> str:
    """Serialize absolute commands to a path d attribute string."""
    parts: list[str] = []
    for cmd, args in cmds:
        part = cmd + ",".join(_fmt(a) for a in args)
        parts.append(part)
    return "".join(parts)


# ---------------------------------------------------------------------------
# SVG group analysis
# ---------------------------------------------------------------------------


def find_groups(root: ET.Element) -> list[dict]:
    """Find all <g> groups that contain both a black and a gray path.

    Returns list of dicts with keys:
      'group': the <g> Element
      'black_elem': the black <path> Element
      'gray_elem':  the gray <path> Element
      'group_index': index among all <g> elements
    """
    groups = []
    for i, g in enumerate(root.iter(f"{{{SVG_NS}}}g")):
        paths = list(g.iter(f"{{{SVG_NS}}}path"))
        black_elem = gray_elem = None
        for p in paths:
            stroke = p.get("stroke", "")
            if stroke in ("#000", "#000000", "black"):
                black_elem = p
            elif stroke in ("#666", "#666666"):
                gray_elem = p
        if black_elem is not None and gray_elem is not None:
            groups.append(
                {
                    "group": g,
                    "black_elem": black_elem,
                    "gray_elem": gray_elem,
                    "group_index": i,
                }
            )
    return groups


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

# Max allowed distance between matched points (in SVG user units).
# The bevel offset is ~4.25 units, so we allow a generous margin.
MAX_PAIR_DISTANCE = 15.0


def validate_groups(groups: list[dict]) -> list[dict]:
    """Validate all groups. Returns list of issue dicts."""
    issues = []
    for gi, ginfo in enumerate(groups):
        black_d = ginfo["black_elem"].get("d", "")
        gray_d = ginfo["gray_elem"].get("d", "")
        b_cmds = commands_to_absolute(tokenize_path(black_d))
        g_cmds = commands_to_absolute(tokenize_path(gray_d))

        # Expand S→C and remove zero-length for fair comparison
        b_cmds = remove_zero_segments(expand_smooth_cubics(b_cmds))
        g_cmds = remove_zero_segments(expand_smooth_cubics(g_cmds))

        b_pts = get_anchor_points(b_cmds)
        g_pts = get_anchor_points(g_cmds)

        if len(b_pts) != len(g_pts):
            issues.append(
                {
                    "group_index": ginfo["group_index"],
                    "type": "unequal_count",
                    "black_count": len(b_pts),
                    "gray_count": len(g_pts),
                    "black_d": black_d,
                    "gray_d": gray_d,
                }
            )
        else:
            b_lengths = compute_segment_lengths(b_cmds)
            g_lengths = compute_segment_lengths(g_cmds)
            b_t = cumulative_t(b_lengths)
            g_t = cumulative_t(g_lengths)
            bad = check_ordering(b_pts, g_pts, b_t, g_t, MAX_PAIR_DISTANCE)
            if bad:
                issues.append(
                    {
                        "group_index": ginfo["group_index"],
                        "type": "misordered",
                        "bad_indices": bad,
                        "black_d": black_d,
                        "gray_d": gray_d,
                        "black_pts": b_pts,
                        "gray_pts": g_pts,
                    }
                )
            else:
                # Check segment type consistency (constraint 4)
                type_bad = check_segment_types(b_cmds, g_cmds)
                if type_bad:
                    issues.append(
                        {
                            "group_index": ginfo["group_index"],
                            "type": "type_mismatch",
                            "bad_segments": type_bad,
                            "black_d": black_d,
                            "gray_d": gray_d,
                        }
                    )
                else:
                    # Check equidistance (constraint 3)
                    bad_segs = check_equidistance(b_cmds, g_cmds)
                    if bad_segs:
                        issues.append(
                            {
                                "group_index": ginfo["group_index"],
                                "type": "non_equidistant",
                                "bad_segments": bad_segs,
                                "black_d": black_d,
                                "gray_d": gray_d,
                            }
                        )
    return issues


# ---------------------------------------------------------------------------
# Generate error.svg
# ---------------------------------------------------------------------------


def generate_error_svg(
    tree: ET.ElementTree,
    groups: list[dict],
    issues: list[dict],
    output_path: str,
):
    """Write an error.svg with problematic paths color-coded."""
    root = copy.deepcopy(tree.getroot())

    # Build lookup: group_index -> issue
    issue_map = {iss["group_index"]: iss for iss in issues}

    # Re-find groups in the copy
    copy_groups = []
    for i, g in enumerate(root.iter(f"{{{SVG_NS}}}g")):
        paths = list(g.iter(f"{{{SVG_NS}}}path"))
        black_elem = gray_elem = None
        for p in paths:
            stroke = p.get("stroke", "")
            if stroke in ("#000", "#000000", "black"):
                black_elem = p
            elif stroke in ("#666", "#666666"):
                gray_elem = p
        if black_elem is not None and gray_elem is not None:
            copy_groups.append(
                {
                    "group": g,
                    "black_elem": black_elem,
                    "gray_elem": gray_elem,
                    "group_index": i,
                }
            )

    for cg in copy_groups:
        idx = cg["group_index"]
        if idx in issue_map:
            iss = issue_map[idx]
            if iss["type"] == "unequal_count":
                color = "red"
            elif iss["type"] == "non_equidistant":
                color = "cyan"
            elif iss["type"] == "type_mismatch":
                color = "magenta"
            else:
                color = "#0a0"  # green for misordered
            cg["black_elem"].set("stroke", color)
            cg["gray_elem"].set("stroke", color)
            cg["black_elem"].set("stroke-width", "2")
            cg["gray_elem"].set("stroke-width", "2")

    # Add a legend
    vb = root.get("viewBox", "0 0 595.28 841.89").split()
    vy = float(vb[1]) if len(vb) > 1 else 0

    legend_g = ET.SubElement(root, f"{{{SVG_NS}}}g")
    legend_g.set("id", "error-legend")

    # Red legend
    r = ET.SubElement(legend_g, f"{{{SVG_NS}}}rect")
    r.set("x", "10")
    r.set("y", str(vy + 5))
    r.set("width", "12")
    r.set("height", "12")
    r.set("fill", "red")
    r.set("stroke", "none")
    t = ET.SubElement(legend_g, f"{{{SVG_NS}}}text")
    t.set("x", "28")
    t.set("y", str(vy + 15))
    t.set("fill", "red")
    t.set("font-size", "10")
    t.set("font-family", "sans-serif")
    t.text = "Unequal point count"

    # Green legend
    r2 = ET.SubElement(legend_g, f"{{{SVG_NS}}}rect")
    r2.set("x", "10")
    r2.set("y", str(vy + 22))
    r2.set("width", "12")
    r2.set("height", "12")
    r2.set("fill", "#0a0")
    r2.set("stroke", "none")
    t2 = ET.SubElement(legend_g, f"{{{SVG_NS}}}text")
    t2.set("x", "28")
    t2.set("y", str(vy + 32))
    t2.set("fill", "#0a0")
    t2.set("font-size", "10")
    t2.set("font-family", "sans-serif")
    t2.text = "Misordered points"

    # Cyan legend
    r3 = ET.SubElement(legend_g, f"{{{SVG_NS}}}rect")
    r3.set("x", "10")
    r3.set("y", str(vy + 39))
    r3.set("width", "12")
    r3.set("height", "12")
    r3.set("fill", "cyan")
    r3.set("stroke", "none")
    t3 = ET.SubElement(legend_g, f"{{{SVG_NS}}}text")
    t3.set("x", "28")
    t3.set("y", str(vy + 49))
    t3.set("fill", "cyan")
    t3.set("font-size", "10")
    t3.set("font-family", "sans-serif")
    t3.text = "Non-equidistant curves"

    # Magenta legend
    r4 = ET.SubElement(legend_g, f"{{{SVG_NS}}}rect")
    r4.set("x", "10")
    r4.set("y", str(vy + 56))
    r4.set("width", "12")
    r4.set("height", "12")
    r4.set("fill", "magenta")
    r4.set("stroke", "none")
    t4 = ET.SubElement(legend_g, f"{{{SVG_NS}}}text")
    t4.set("x", "28")
    t4.set("y", str(vy + 66))
    t4.set("fill", "magenta")
    t4.set("font-size", "10")
    t4.set("font-family", "sans-serif")
    t4.text = "Segment type mismatch"

    new_tree = ET.ElementTree(root)
    ET.indent(new_tree, space="  ")
    new_tree.write(output_path, xml_declaration=True, encoding="UTF-8")
    print(f"Wrote {output_path}")


# ---------------------------------------------------------------------------
# Generate fixed SVG
# ---------------------------------------------------------------------------


def generate_fixed_svg(
    tree: ET.ElementTree,
    groups: list[dict],
    output_path: str,
    discretize_n: int | None = None,
):
    """Write a new SVG with normalized paths.

    If discretize_n is given, all cubic bezier segments are replaced with
    tangent-preserving line-segment approximations using that many control
    points per arc.
    """
    root = copy.deepcopy(tree.getroot())

    # Re-find groups in the copy
    copy_groups = []
    for i, g in enumerate(root.iter(f"{{{SVG_NS}}}g")):
        paths = list(g.iter(f"{{{SVG_NS}}}path"))
        black_elem = gray_elem = None
        for p in paths:
            stroke = p.get("stroke", "")
            if stroke in ("#000", "#000000", "black"):
                black_elem = p
            elif stroke in ("#666", "#666666"):
                gray_elem = p
        if black_elem is not None and gray_elem is not None:
            copy_groups.append(
                {
                    "group": g,
                    "black_elem": black_elem,
                    "gray_elem": gray_elem,
                    "group_index": i,
                }
            )

    fixed_count = 0
    equidist_count = 0
    for cg in copy_groups:
        black_d = cg["black_elem"].get("d", "")
        gray_d = cg["gray_elem"].get("d", "")
        b_cmds = commands_to_absolute(tokenize_path(black_d))
        g_cmds = commands_to_absolute(tokenize_path(gray_d))

        b_norm, g_norm = normalize_pair(b_cmds, g_cmds)

        b_pts_before = get_anchor_points(
            remove_zero_segments(expand_smooth_cubics(b_cmds))
        )
        g_pts_before = get_anchor_points(
            remove_zero_segments(expand_smooth_cubics(g_cmds))
        )
        b_pts_after = get_anchor_points(b_norm)
        g_pts_after = get_anchor_points(g_norm)

        changed = len(b_pts_before) != len(g_pts_before) or len(b_pts_after) != len(
            b_pts_before
        )

        if changed:
            cg["black_elem"].set("d", commands_to_d(b_norm))
            cg["gray_elem"].set("d", commands_to_d(g_norm))
            fixed_count += 1
            print(
                f"  Group {cg['group_index']}: "
                f"black {len(b_pts_before)}→{len(b_pts_after)} pts, "
                f"gray {len(g_pts_before)}→{len(g_pts_after)} pts"
            )

        # Check and fix equidistance on the (possibly normalized) paths
        # Re-read the current d attributes (may have been updated above)
        cur_b_d = cg["black_elem"].get("d", "")
        cur_g_d = cg["gray_elem"].get("d", "")
        cur_b = remove_zero_segments(
            expand_smooth_cubics(commands_to_absolute(tokenize_path(cur_b_d)))
        )
        cur_g = remove_zero_segments(
            expand_smooth_cubics(commands_to_absolute(tokenize_path(cur_g_d)))
        )

        bad_segs = check_equidistance(cur_b, cur_g)
        if bad_segs:
            offset = _compute_group_offset(cur_b, cur_g)
            # Iterate: fixing some segments may reveal or create issues in
            # adjacent segments (endpoint continuity), so re-check and fix
            # until stable (max 5 iterations to avoid infinite loops).
            for _iteration in range(5):
                g_fixed = _fix_equidistance(cur_b, cur_g, bad_segs, offset)
                cg["gray_elem"].set("d", commands_to_d(g_fixed))
                # Re-read and re-check
                cur_g_d2 = cg["gray_elem"].get("d", "")
                cur_g = remove_zero_segments(
                    expand_smooth_cubics(commands_to_absolute(tokenize_path(cur_g_d2)))
                )
                bad_segs = check_equidistance(cur_b, cur_g)
                if not bad_segs:
                    break
            # Unify segment types: the equidistance fix mirrors the black
            # path's command types onto gray, which may introduce L/C
            # mismatches at non-fixed segment indices.
            cur_b_d3 = cg["black_elem"].get("d", "")
            cur_g_d3 = cg["gray_elem"].get("d", "")
            ub = remove_zero_segments(
                expand_smooth_cubics(commands_to_absolute(tokenize_path(cur_b_d3)))
            )
            ug = remove_zero_segments(
                expand_smooth_cubics(commands_to_absolute(tokenize_path(cur_g_d3)))
            )
            ub, ug = _unify_segment_types(ub, ug)
            cg["black_elem"].set("d", commands_to_d(ub))
            cg["gray_elem"].set("d", commands_to_d(ug))

            equidist_count += 1
            if bad_segs:
                print(
                    f"  Group {cg['group_index']}: equidistance partially fixed "
                    f"(offset={offset:.2f}), remaining segments {bad_segs}"
                )
            else:
                print(
                    f"  Group {cg['group_index']}: fixed equidistance "
                    f"(offset={offset:.2f})"
                )

    # Discretize cubic beziers into line segments if requested.
    # This must be done as a final pass after all normalization and
    # equidistance fixes so that the point-count parity is maintained.
    # Both paths in a pair are discretized together: whenever *either*
    # path has a C at a given segment index, both paths produce n-1
    # line segments for that index (an L is subdivided evenly).
    if discretize_n is not None and discretize_n >= 2:
        disc_count = 0
        for cg in copy_groups:
            b_d = cg["black_elem"].get("d", "")
            g_d = cg["gray_elem"].get("d", "")
            b_abs = remove_zero_segments(
                expand_smooth_cubics(commands_to_absolute(tokenize_path(b_d)))
            )
            g_abs = remove_zero_segments(
                expand_smooth_cubics(commands_to_absolute(tokenize_path(g_d)))
            )

            # Check if there are any C commands to discretize
            has_curves = any(cmd == "C" for cmd, _ in b_abs) or any(
                cmd == "C" for cmd, _ in g_abs
            )

            if has_curves:
                # Find segments where curves are too short to discretize
                # into n-1 segments without producing sub-threshold pieces.
                collapse = _find_collapse_indices(b_abs, g_abs, discretize_n)
                b_disc = _discretize_pair_member(b_abs, g_abs, discretize_n, collapse)
                g_disc = _discretize_pair_member(g_abs, b_abs, discretize_n, collapse)
                # Remove zero-length segments that may result from
                # discretizing very short curves, but only when both
                # paths agree the segment is zero-length, to keep parity.
                b_disc, g_disc = _remove_zero_segments_paired(b_disc, g_disc)

                # Post-discretization cleanup: simulate what the validator
                # does (independent remove_zero_segments on each path) and
                # re-normalize if counts diverge.  This ensures the
                # validator won't later remove different numbers of
                # segments from each path.
                b_clean = remove_zero_segments(b_disc)
                g_clean = remove_zero_segments(g_disc)
                b_draw = b_clean[1:] if b_clean and b_clean[0][0] == "M" else b_clean
                g_draw = g_clean[1:] if g_clean and g_clean[0][0] == "M" else g_clean
                if len(b_draw) != len(g_draw):
                    if len(b_draw) < len(g_draw):
                        b_clean = _add_segments_to_match(
                            b_clean, target_count=len(g_draw)
                        )
                    else:
                        g_clean = _add_segments_to_match(
                            g_clean, target_count=len(b_draw)
                        )
                # Unify segment types after count re-normalization:
                # _add_segments_to_match may split a C into two C's where
                # the partner path has L's at those indices.
                b_disc, g_disc = _unify_segment_types(b_clean, g_clean)

                cg["black_elem"].set("d", commands_to_d(b_disc))
                cg["gray_elem"].set("d", commands_to_d(g_disc))
                disc_count += 1

        print(
            f"  Discretized arcs in {disc_count} group(s) ({discretize_n} pts per arc)"
        )

    new_tree = ET.ElementTree(root)
    ET.indent(new_tree, space="  ")
    new_tree.write(output_path, xml_declaration=True, encoding="UTF-8")
    print(
        f"\nFixed {fixed_count} point-count group(s), "
        f"{equidist_count} equidistance group(s). Wrote {output_path}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_validate(args):
    tree = ET.parse(args.input)
    groups = find_groups(tree.getroot())
    print(f"Found {len(groups)} black/gray path groups.")

    issues = validate_groups(groups)
    if not issues:
        print("All groups pass validation.")
        return

    print(f"\n{len(issues)} group(s) have issues:\n")
    for iss in issues:
        gi = iss["group_index"]
        if iss["type"] == "unequal_count":
            print(
                f"  Group {gi}: UNEQUAL POINT COUNT "
                f"(black={iss['black_count']}, gray={iss['gray_count']})"
            )
        elif iss["type"] == "misordered":
            print(f"  Group {gi}: MISORDERED POINTS at indices {iss['bad_indices']}")
        elif iss["type"] == "non_equidistant":
            print(
                f"  Group {gi}: NON-EQUIDISTANT curves at segments "
                f"{iss['bad_segments']}"
            )
        elif iss["type"] == "type_mismatch":
            print(
                f"  Group {gi}: SEGMENT TYPE MISMATCH at segments {iss['bad_segments']}"
            )

    error_path = args.output or "error.svg"
    generate_error_svg(tree, groups, issues, error_path)
    sys.exit(1)


def cmd_generate(args):
    tree = ET.parse(args.input)
    groups = find_groups(tree.getroot())
    print(f"Found {len(groups)} black/gray path groups.\n")
    generate_fixed_svg(tree, groups, args.output, discretize_n=args.discretize)


def main():
    parser = argparse.ArgumentParser(
        description="Validate and fix black/gray path pairs in 5DOF laser-cutter SVGs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser(
        "validate", help="Check path constraints and produce error.svg"
    )
    p_val.add_argument("input", help="Input SVG file")
    p_val.add_argument(
        "-o", "--output", default=None, help="Output error SVG (default: error.svg)"
    )
    p_val.set_defaults(func=cmd_validate)

    p_gen = sub.add_parser(
        "generate", help="Generate a fixed SVG with normalized paths"
    )
    p_gen.add_argument("input", help="Input SVG file")
    p_gen.add_argument("output", help="Output SVG file")
    p_gen.add_argument(
        "--discretize",
        type=int,
        default=None,
        metavar="N",
        help="Convert arcs to line segments using N control points per arc "
        "(N >= 2). Tangent direction at arc endpoints is preserved.",
    )
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
