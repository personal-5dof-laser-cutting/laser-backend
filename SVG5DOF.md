# SVG5DOF
SVG5DOF is a fully SVG-compliant file format to encode cutting plans for 5DOF laser cutting in 2D, which means every SVG5DOF file MUST fully adhere to the SVG specification, in the respective version indicated in the file header.
Its key feature is describing slanted cuts as a group (`<g>`) of "entry" and "exit" lines (this group is also called an "edge profile"). It does so by using CSS classes (also called "attributes" in this document). To maintain backwards compatibility, ungrouped lines are interpreted as straight through-cuts.


The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT",
"RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).


## classes
### depth_{VALUE}
{VALUE} can be absolute (such as `depth_5mm`) or relative (such as `depth_50%` (meaning 50% of the depth of a throughcut at the same angle)).
Negative values are permitted (such as `depth_-2mm`). Relative values may leave the `%` sign out.


### entry
Each group MUST have at least one entry line.
Entry lines MAY be combined with a depth attribute. When cutting, the entry line is projected onto the top surface of the material piece along the cuttting angle.
Not providing a depth attribute in addition to `entry` is equivalent to `depth_0`


### exit
Each group MAY have one or more exit lines.
Exit lines MAY be combined with a depth attribute. When cutting, the exit line is projected onto the bottom surface of the material piece along the cuttting angle.
Not providing a depth attribute in addition to `exit` is equivalent to `depth_100`


### depth-ramp
// TODO


### start_{VALUE}
MUST NOT be used if `depth-ramp` is not present.
// TODO


### end_{VALUE}
MUST NOT be used if `depth-ramp` is not present.
// TODO


## compatibility mode
To allow use with SVG editors that do not support editing classes, lines without a class MUST be interpreted the same as a specific class adhering to the following rules:
- a gray line with 100% darkness (black) is treated the same as an `entry` line
- a gray line with 20% darkness (light gray) is treated the same as an `exit` line
- a gray line with darkness in the interval (100%, 20%) is treated the same as a `depth_{VALUE}` line, where `VALUE = 100% - (darkness - 20%) / 0.8`, e.g., 40% darkness indicates a cutting depth of 75%.

To further allow SVG5DOF being a superset of the common SVG representations used by users of 3DOF laser cutters, ungrouped lines are treated as straight (0° tilt angle) through-cuts.

## cutting
### segment
A cuttable segment is formed by two subsequent lines of a group. At least one of these two lines MUST be either an `entry` or `exit` line.


### angles
// TODO (we have this implemented already)


### order
By default, the order of cut lines in a group is determined by their z-height.


### duplex
Cuttable segments that only have an `exit` line but not an `entry` line are cut from the backside. An application for cutting SVG5DOF SHOULD prompt the user to flip the material piece after cutting all segments with an `entry` line to cut segments that include only an `exit` line without an `entry` line


#### example
The following snippet of SVG5DOF MUST be cut from two sides:


```SVG
<g>
    <line class="entry"    x1="10" y1="10" x2="50" y2="10" />
    <line class="depth_50" x1="10" y1="15" x2="50" y2="15" />
    <line class="exit"     x1="10" y1="10" x2="50" y2="10" />
</g>
```
The group above would be cut by two cuts, the first of which is cut from the top surface of the material and is described by the `entry` line and the `depth_50` line. The second cut is cut from the bottom surface of the material and is described by the `exit` line and the `depth_50` line.


### control points
Paths describing a cut segment MUST have the same number of control points (`len(a) == len(b)`). An application processing SVG5DOF SHOULD alert the user if this constraint is violated by highlighting the violating segments. The application MAY provide a way to attempt to correct segments with non-matching paths (`a`, `b`) by resampling paths with equidistant control points, the number of control points to sample the curve in may be determined by `LCM(len(a), len(b))`.


## visualization
A frontend application visualizing the file format SHOULD render the depth attribute as a blur effect (such as `filter: blur(4px);` in CSS) where the blur radius increases with depth.


As an alternative, a renderer MAY instead visualize the depth with a combination of gray-scale value and line thickness, where the darkness decreases with depth while the line thickness increases with depth.
