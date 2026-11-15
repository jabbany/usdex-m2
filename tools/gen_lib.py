#!/usr/bin/env python3
"""Generate the project library: hardware/lib/msdx.kicad_sym and the two
project-specific footprints in hardware/lib/msdx.pretty.

Run from the repository root:  python3 tools/gen_lib.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msdx import geom as g  # noqa: E402
from msdx import symbols  # noqa: E402
from msdx.sexp import num as n  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "hardware", "lib")
PRETTY = os.path.join(LIB, "msdx.pretty")

FONT = "(effects (font (size 0.8 0.8) (thickness 0.12)))"


def line(x0, y0, x1, y1, layer, w=0.12):
    return (f'  (fp_line (start {n(x0)} {n(y0)}) (end {n(x1)} {n(y1)}) '
            f'(stroke (width {n(w)}) (type solid)) (layer "{layer}"))')


def rect(x0, y0, x1, y1, layer, w=0.1):
    return (f'  (fp_rect (start {n(x0)} {n(y0)}) (end {n(x1)} {n(y1)}) '
            f'(stroke (width {n(w)}) (type solid)) (fill none) (layer "{layer}"))')


def poly(pts, layer, w=0.05, fill="none"):
    p = " ".join(f"(xy {n(x)} {n(y)})" for x, y in pts)
    return (f'  (fp_poly (pts {p}) (stroke (width {n(w)}) (type solid)) '
            f'(fill {fill}) (layer "{layer}"))')


def text(kind, s, x, y, layer, hide=False):
    return (f'  (fp_text {kind} "{s}" (at {n(x)} {n(y)}) (layer "{layer}")'
            f'{" hide" if hide else ""} {FONT})')


def keepout(name, box, layer="F.Cu"):
    x0, y0, x1, y1 = box
    pts = f"(xy {n(x0)} {n(y0)}) (xy {n(x1)} {n(y0)}) (xy {n(x1)} {n(y1)}) (xy {n(x0)} {n(y1)})"
    return (f'  (zone (net 0) (net_name "") (layer "{layer}") (name "{name}") (hatch edge 0.3)\n'
            f'    (connect_pads (clearance 0))\n'
            f'    (min_thickness 0.25) (filled_areas_thickness no)\n'
            f'    (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) '
            f'(copperpour not_allowed) (footprints allowed))\n'
            f'    (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
            f'    (polygon (pts {pts}))\n'
            f'  )')


# --------------------------------------------------------------------------
def socket_footprint():
    pw, pl = g.SKT_PAD
    sw, sl = g.SKT_SHIELD_PAD
    bx0, by0, bx1, by1 = g.SKT_BODY
    cx0, cy0, cx1, cy1 = g.SKT_CARD
    out = [
        '(footprint "Amphenol_10102166A812A" (version 20221018) (generator msdx_gen)',
        '  (layer "F.Cu")',
        '  (descr "Amphenol 10102166A812A microSD Express socket, 3-in-1 (UHS-I / UHS-II / '
        'Express), push-pull, card detect, 1.55 mm. Row 1 (pads 1-8, DET) is the closed end at '
        'y=-7, row 2 (pads 9-17) is the card mouth at y=+7; the card enters from +y. '
        'https://www.amphenol-cs.com/product/10102166a812a.html")',
        '  (tags "microSD Express SD7.1 PCIe socket Amphenol 10102166")',
        '  (attr smd)',
        text("reference", "REF**", 0, -9.0, "F.SilkS"),
        text("value", "Amphenol_10102166A812A", 0, 11.2, "F.Fab"),
        text("user", "${REFERENCE}", 0, -1.5, "F.Fab"),
        text("user", "CARD", 0, 9.0, "F.Fab"),
    ]
    # fabrication layer: shell, inserted card, contact-tip zone
    out.append(rect(bx0, by0, bx1, by1, "F.Fab"))
    out.append(rect(cx0, cy0, cx1, cy1, "F.Fab", 0.05))
    out.append(rect(*g.SKT_TIP_ZONE, "Cmts.User", 0.05))
    out.append('  (fp_text user "contact tips touch PCB" (at 0 2.7) (layer "Cmts.User") '
               '(effects (font (size 0.4 0.4) (thickness 0.06))))')
    # silkscreen: side walls between the shield pads, pin-1 dot, mouth marks
    for sx in (-bx1, bx1):
        ys = sorted(g.SKT_SHIELD_Y)
        for a, b in zip(ys[:-1], ys[1:]):
            out.append(line(sx, a + sl / 2 + 0.3, sx, b - sl / 2 - 0.3, "F.SilkS"))
    out.append(f'  (fp_circle (center {n(g.SKT_ROW1["1"])} -8.25) (end {n(g.SKT_ROW1["1"] + 0.12)} -8.25) '
               f'(stroke (width 0.24) (type solid)) (fill none) (layer "F.SilkS"))')
    out.append(line(-5.6, -by1 + 0.55, -6.2, -by1 + 0.55, "F.SilkS"))
    # courtyard: body and pads, extended over the card tail so nothing is
    # placed where the inserted card overhangs the board
    m = 0.25
    yt = -(g.SKT_ROW_Y + pl / 2 + m)
    yb = g.SKT_ROW_Y + pl / 2 + m
    xs = g.SKT_SHIELD_X + sw / 2 + m
    out.append(poly([(-xs, yt), (xs, yt), (xs, yb), (cx1 + m, yb), (cx1 + m, cy1 + m),
                     (cx0 - m, cy1 + m), (cx0 - m, yb), (-xs, yb)], "F.CrtYd"))
    # pads
    for name, x in g.SKT_ROW1.items():
        out.append(f'  (pad "{name}" smd roundrect (at {n(x)} {n(-g.SKT_ROW_Y)}) (size {n(pw)} {n(pl)}) '
                   f'(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    for name, x in g.SKT_ROW2.items():
        out.append(f'  (pad "{name}" smd roundrect (at {n(x)} {n(g.SKT_ROW_Y)}) (size {n(pw)} {n(pl)}) '
                   f'(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    for sx in (-g.SKT_SHIELD_X, g.SKT_SHIELD_X):
        for sy in g.SKT_SHIELD_Y:
            out.append(f'  (pad "SH" smd roundrect (at {n(sx)} {n(sy)}) (size {n(sw)} {n(sl)}) '
                       f'(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.15))')
    out.append(keepout("J2 contact tips: no copper", g.SKT_TIP_KEEPOUT))
    out.append('  (model "${KIPRJMOD}/lib/3d/10102166A812A.step"\n'
               f'    (offset (xyz 0 {n(-g.SKT_STEP_Y_OFFSET)} 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0))\n'
               '  )')
    out.append(")")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
def ring_poly(r_in, r_out, clip, cx, cy, ax, ay, step=7.5):
    """Half-annulus around (cx, cy) opening toward -y (the board edge), kept
    `clip` away from the edge line y = cy. Points relative to (ax, ay)."""
    pts = []
    a0 = math.degrees(math.asin(clip / r_out))
    a = a0
    while a < 180 - a0:
        pts.append((cx + r_out * math.cos(math.radians(a)), cy + r_out * math.sin(math.radians(a))))
        a += step
    pts.append((cx - r_out * math.cos(math.radians(a0)), cy + clip))
    b0 = math.degrees(math.asin(clip / r_in))
    b = 180 - b0
    pts.append((cx - r_in * math.cos(math.radians(b0)), cy + clip))
    while b > b0:
        pts.append((cx + r_in * math.cos(math.radians(b)), cy + r_in * math.sin(math.radians(b))))
        b -= step
    pts.append((cx + r_in * math.cos(math.radians(b0)), cy + clip))
    return [(x - ax, y - ay) for x, y in pts]


def edge_footprint():
    """Origin: centre of the gold-finger edge. -y points into the board."""
    L = g.BOARD_L
    fw = g.M2_FINGER_W
    sb = g.M2_FINGER_SETBACK
    top_len = g.M2_FINGER_TOP_END - sb
    bot_len = g.M2_FINGER_BOT_END - sb
    out = [
        '(footprint "M2_2230_KeyM_Edge" (version 20221018) (generator msdx_gen)',
        '  (layer "F.Cu")',
        '  (descr "M.2 type 2230 module, socket 3 Key M card edge: gold fingers (odd pins top, '
        'even pins bottom, 0.5 mm pitch per side) and the half-moon mounting-notch ground pads. '
        'Origin at the centre of the finger edge; the board outline is drawn at board level. '
        'Top fingers reach 2.0 mm from the edge, bottom fingers 2.5 mm, per the PCI Express M.2 '
        'specification.")',
        '  (tags "M.2 NGFF Key M 2230 card edge gold finger")',
        '  (attr exclude_from_pos_files exclude_from_bom)',
        text("reference", "REF**", 0, -5.0, "F.Fab"),
        text("value", "M2_2230_KeyM_Edge", 0, -6.2, "F.Fab"),
    ]
    # reference outline on a drawing layer
    for p in g.outline(notch=False):
        if p[0] == "line":
            (x0, y0), (x1, y1) = p[1:]
            out.append(line(x0, y0 - L, x1, y1 - L, "Dwgs.User", 0.05))
        else:
            (x0, y0), (xm, ym), (x1, y1) = p[1:]
            out.append(f'  (fp_arc (start {n(x0)} {n(y0 - L)}) (mid {n(xm)} {n(ym - L)}) '
                       f'(end {n(x1)} {n(y1 - L)}) (stroke (width 0.05) (type solid)) (layer "Dwgs.User"))')
    # courtyards double as the M.2 component keep-outs
    tw = g.M2_TONGUE_W / 2
    out.append(rect(-tw, -g.M2_COMPONENT_KEEPOUT, tw, 0, "F.CrtYd", 0.05))
    r = g.M2_MOUNT_PAD_R_BOT + 0.05
    arc = [(r * math.cos(math.radians(a)), -L + r * math.sin(math.radians(a))) for a in range(0, 181, 10)]
    out.append(poly(arc, "F.CrtYd"))
    # fingers
    for pin in g.m2_pins():
        x = g.m2_pin_x(pin)
        if pin % 2:
            out.append(f'  (pad "{pin}" connect rect (at {n(x)} {n(-(sb + top_len / 2))}) '
                       f'(size {n(fw)} {n(top_len)}) (layers "F.Cu" "F.Mask"))')
        else:
            out.append(f'  (pad "{pin}" connect rect (at {n(x)} {n(-(sb + bot_len / 2))}) '
                       f'(size {n(fw)} {n(bot_len)}) (layers "B.Cu" "B.Mask"))')
    # mounting-notch ground pads (screw seat): half rings kept 0.4 mm inside
    # the board edge and the notch so no copper is cut by the router
    ay = -L + 2.4
    for layer, mask, r_out in (("F.Cu", "F.Mask", g.M2_MOUNT_PAD_R_TOP), ("B.Cu", "B.Mask", g.M2_MOUNT_PAD_R_BOT)):
        pts = ring_poly(g.M2_MOUNT_R + 0.4, r_out, 0.4, 0, -L, 0, ay)
        p = " ".join(f"(xy {n(x)} {n(y)})" for x, y in pts)
        out.append(f'  (pad "MP" smd custom (at 0 {n(ay)}) (size 0.4 0.4) (layers "{layer}" "{mask}")\n'
                   f'    (zone_connect 2) (options (clearance outline) (anchor circle))\n'
                   f'    (primitives (gr_poly (pts {p}) (width 0) (fill yes)))\n'
                   f'  )')
    out.append(")")
    return "\n".join(out) + "\n"


def testpad_footprint():
    return "\n".join([
        '(footprint "TestPad_D0.8mm" (version 20221018) (generator msdx_gen)',
        '  (layer "F.Cu")',
        '  (descr "Bare 0.8 mm test pad with a tight courtyard, for boards with no room for the '
        'standard TestPoint_Pad footprints")',
        '  (tags "test point pad")',
        '  (attr exclude_from_pos_files exclude_from_bom)',
        text("reference", "REF**", 0, -1.0, "F.Fab"),
        text("value", "TestPad_D0.8mm", 0, 1.0, "F.Fab", hide=True),
        '  (fp_circle (center 0 0) (end 0.55 0) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))',
        '  (pad "1" smd circle (at 0 0) (size 0.8 0.8) (layers "F.Cu" "F.Mask"))',
        ")",
    ]) + "\n"


def main():
    os.makedirs(PRETTY, exist_ok=True)
    with open(os.path.join(PRETTY, "TestPad_D0.8mm.kicad_mod"), "w") as f:
        f.write(testpad_footprint())
    with open(os.path.join(LIB, "msdx.kicad_sym"), "w") as f:
        f.write(symbols.project_library())
    with open(os.path.join(PRETTY, "Amphenol_10102166A812A.kicad_mod"), "w") as f:
        f.write(socket_footprint())
    with open(os.path.join(PRETTY, "M2_2230_KeyM_Edge.kicad_mod"), "w") as f:
        f.write(edge_footprint())
    print("wrote", LIB)


if __name__ == "__main__":
    main()
