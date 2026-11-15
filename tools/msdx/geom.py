"""Geometry constants shared by the footprint, schematic and PCB generators.

BOARD FRAME (used everywhere in this project, including DESIGN.md)
    Top view, gold fingers at the bottom of the screen.
    X: across the module, 0 on the centreline, +X toward M.2 pin 1 (right).
    Y: along the module, 0 at the mounting-notch edge, 30 at the finger edge.
    KiCad page coordinates = board coordinates + (OX, OY).

All dimensions are millimetres.
"""
import math

OX, OY = 100.0, 100.0


def K(x, y):
    """Board frame -> KiCad page coordinates."""
    return (OX + x, OY + y)


# --------------------------------------------------------------------------
# M.2 module, type 2230, Key M  (PCI Express M.2 Specification, module
# outline and card-edge figures; values cross-checked against the working
# M1cha/sdexpress_pcbs 2280-key-M footprint)
# --------------------------------------------------------------------------
BOARD_W = 22.0
BOARD_L = 30.0
BOARD_T = 0.8

M2_TONGUE_W = 19.85          # width of the card-edge tongue
M2_TONGUE_L = 4.0            # length of the narrowed tongue
M2_TONGUE_FILLET = 0.6       # inside radius where the tongue meets the shoulder
M2_PITCH = 0.5               # pin pitch per side; top and bottom rows offset 0.25
M2_FINGER_W = 0.35
M2_FINGER_SETBACK = 0.45     # bare laminate between board edge and finger (spec: 0.55 max)
M2_FINGER_TOP_END = 2.0      # top-side finger ends this far from the edge
M2_FINGER_BOT_END = 2.5      # bottom-side finger ends this far from the edge
M2_KEY_M_PINS = range(59, 67)  # positions removed by the Key M notch
M2_KEY_X = -6.125            # notch centreline (spec dimension 6.125 from centre)
M2_KEY_W = 1.2
M2_KEY_DEPTH = 3.5
M2_MOUNT_R = 1.75            # half-moon mounting notch (hole dia 3.5)
M2_MOUNT_PAD_R_TOP = 2.75    # GND pad dia 5.5 on top
M2_MOUNT_PAD_R_BOT = 3.0     # GND pad dia 6.0 on bottom
M2_COMPONENT_KEEPOUT = 4.0   # no top-side parts closer than this to the finger edge
M2_MAX_HEIGHT_TOP = 1.5      # type S3


def m2_pin_x(n):
    """Board X of M.2 pin n. Odd pins are on the top side, even on the bottom."""
    if n % 2:
        return 9.25 - 0.25 * (n - 1)
    return 9.0 - 0.25 * (n - 2)


def m2_pins():
    return [n for n in range(1, 76) if n not in M2_KEY_M_PINS]


M2_TOP_FINGER_Y = BOARD_L - M2_FINGER_TOP_END    # inner end of top fingers (board Y)
M2_BOT_FINGER_Y = BOARD_L - M2_FINGER_BOT_END    # inner end of bottom fingers


# --------------------------------------------------------------------------
# Amphenol 10102166A812A microSD Express socket (push-pull, 3-in-1)
#
# Footprint frame: origin at the centre of the land pattern, row 1 (legacy
# contacts 1-8 + DET, closed end) at y = -7.0, row 2 (Express contacts 9-17,
# card mouth) at y = +7.0, card inserted from +y toward -y.
#
# Pad positions agree between two independently used community footprints
# (vapetrov/microSD_express_Pi and M1cha/sdexpress_pcbs) and with the solder
# tails measured in Amphenol's STEP model. Everything below "measured from
# STEP" comes from slicing that model; see DESIGN.md section 6.
# --------------------------------------------------------------------------
SKT_ROW_Y = 7.0
SKT_PAD = (0.7, 1.2)
SKT_ROW1 = {  # pad name -> x
    "1": 3.76, "2": 2.66, "3": 1.56, "4": 0.46, "5": -0.64,
    "6": -1.74, "7": -2.84, "8": -3.94, "DET": -5.04,
}
SKT_ROW2 = {
    "9": 3.72, "17": 2.57, "10": 1.66, "11": 0.75, "12": -0.16,
    "13": -1.07, "14": -1.98, "15": -2.89, "16": -3.80,
}
SKT_SHIELD_X = 6.85
SKT_SHIELD_Y = (-6.15, 1.05, 6.55)
SKT_SHIELD_PAD = (1.1, 2.1)

# measured from STEP (model y -> footprint y = 7.6 - y_model)
SKT_STEP_Y_OFFSET = 7.6
SKT_BODY = (-6.75, -7.05, 6.75, 7.6)          # x0, y0, x1, y1 of the shell
SKT_HEIGHT = 1.5                              # model; Amphenol states 1.55
SKT_CARD = (-4.94, -5.0, 6.06, 10.0)          # inserted card outline
SKT_CARD_UNDERSIDE_Z = 0.55                   # card bottom above the PCB
SKT_FLOOR_Z = 0.25                            # housing floor starts here; air below
# Free ends of the nine row-2 contact beams come down to the PCB surface here
# when a card is inserted. No copper, no vias, no pour on the top layer.
SKT_TIP_ZONE = (-4.16, 1.9, 3.71, 3.5)
SKT_TIP_KEEPOUT = (-4.45, 1.6, 4.0, 3.8)


# --------------------------------------------------------------------------
# Socket placement on the board (rotated so the card mouth faces +X)
# --------------------------------------------------------------------------
SKT_POS = (0.7, 14.5)
SKT_ROT = 90


def rot(x, y, deg):
    """KiCad footprint rotation (counter-clockwise on screen, Y down)."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (x * c + y * s, -x * s + y * c)


def place(pos, deg, x, y):
    dx, dy = rot(x, y, deg)
    return (round(pos[0] + dx, 6), round(pos[1] + dy, 6))


def skt_pad(name):
    """Board-frame centre of a socket pad."""
    if name in SKT_ROW1:
        return place(SKT_POS, SKT_ROT, SKT_ROW1[name], -SKT_ROW_Y)
    return place(SKT_POS, SKT_ROT, SKT_ROW2[name], SKT_ROW_Y)


def skt_shield_pads():
    out = []
    for sx in (-SKT_SHIELD_X, SKT_SHIELD_X):
        for sy in SKT_SHIELD_Y:
            out.append(place(SKT_POS, SKT_ROT, sx, sy))
    return out


def skt_box(box):
    """Board-frame bounding box (x0, y0, x1, y1) of a footprint-frame box."""
    pts = [place(SKT_POS, SKT_ROT, x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


# --------------------------------------------------------------------------
# Finger notch under the card tail (optional; see DESIGN.md)
# --------------------------------------------------------------------------
NOTCH_DEPTH = 1.1
NOTCH_W = 7.0
NOTCH_R = 0.5


# --------------------------------------------------------------------------
# Routing geometry (placeholders until taken from the fab's calculator)
# --------------------------------------------------------------------------
DP_W = 0.16      # 85 ohm pair on L1 over L2, 0.1 mm 3313 prepreg: trace width
DP_GAP = 0.15    # edge-to-edge gap
DP_PITCH = DP_W + DP_GAP
SIG_W = 0.15
PWR_W = 0.5
VIA = (0.5, 0.3)        # diameter, drill
VIA_SMALL = (0.45, 0.3)


# --------------------------------------------------------------------------
# Board outline (Edge.Cuts), board frame, clockwise from the top-left corner.
# Primitives: ("line", p0, p1) and ("arc", start, mid, end).
# --------------------------------------------------------------------------
def card_centre_y():
    """Board Y of the inserted card's centreline."""
    cx = (SKT_CARD[0] + SKT_CARD[2]) / 2
    return place(SKT_POS, SKT_ROT, cx, 0)[1]


def notch_span():
    c = card_centre_y()
    return (round(c - NOTCH_W / 2, 3), round(c + NOTCH_W / 2, 3))


def outline(notch=True):
    hw = BOARD_W / 2
    tw = M2_TONGUE_W / 2
    f = M2_TONGUE_FILLET
    k = 1 / math.sqrt(2)
    ys = BOARD_L - M2_TONGUE_L            # shoulder
    kr = M2_KEY_W / 2
    ky = BOARD_L - M2_KEY_DEPTH + kr      # centre of the key's end radius
    mr = M2_MOUNT_R
    prims = [
        ("line", (-hw, 0), (-mr, 0)),
        ("arc", (-mr, 0), (0, mr), (mr, 0)),
        ("line", (mr, 0), (hw, 0)),
    ]
    if notch:
        y0, y1 = notch_span()
        xn = hw - NOTCH_DEPTH
        r = NOTCH_R
        prims += [
            ("line", (hw, 0), (hw, y0)),
            ("line", (hw, y0), (xn + r, y0)),
            ("arc", (xn + r, y0), (xn + r - r * k, y0 + r - r * k), (xn, y0 + r)),
            ("line", (xn, y0 + r), (xn, y1 - r)),
            ("arc", (xn, y1 - r), (xn + r - r * k, y1 - r + r * k), (xn + r, y1)),
            ("line", (xn + r, y1), (hw, y1)),
            ("line", (hw, y1), (hw, ys)),
        ]
    else:
        prims.append(("line", (hw, 0), (hw, ys)))
    prims += [
        ("line", (hw, ys), (tw + f, ys)),
        ("arc", (tw + f, ys), (tw + f - f * k, ys + f - f * k), (tw, ys + f)),
        ("line", (tw, ys + f), (tw, BOARD_L)),
        ("line", (tw, BOARD_L), (M2_KEY_X + kr, BOARD_L)),
        ("line", (M2_KEY_X + kr, BOARD_L), (M2_KEY_X + kr, ky)),
        ("arc", (M2_KEY_X + kr, ky), (M2_KEY_X, ky - kr), (M2_KEY_X - kr, ky)),
        ("line", (M2_KEY_X - kr, ky), (M2_KEY_X - kr, BOARD_L)),
        ("line", (M2_KEY_X - kr, BOARD_L), (-tw, BOARD_L)),
        ("line", (-tw, BOARD_L), (-tw, ys + f)),
        ("arc", (-tw, ys + f), (-tw - f + f * k, ys + f - f * k), (-tw - f, ys)),
        ("line", (-tw - f, ys), (-hw, ys)),
        ("line", (-hw, ys), (-hw, 0)),
    ]
    return [(p[0],) + tuple((round(x, 4), round(y, 4)) for x, y in p[1:]) for p in prims]


def outline_polygon(notch=True, step=0.05):
    """Outline as a closed point list (arcs flattened) for geometric checks."""
    pts = []
    for p in outline(notch):
        if p[0] == "line":
            pts.append(p[1])
        else:
            (x0, y0), (xm, ym), (x1, y1) = p[1:]
            # circle through three points
            d = 2 * (x0 * (ym - y1) + xm * (y1 - y0) + x1 * (y0 - ym))
            ux = ((x0**2 + y0**2) * (ym - y1) + (xm**2 + ym**2) * (y1 - y0) + (x1**2 + y1**2) * (y0 - ym)) / d
            uy = ((x0**2 + y0**2) * (x1 - xm) + (xm**2 + ym**2) * (x0 - x1) + (x1**2 + y1**2) * (xm - x0)) / d
            r = math.hypot(x0 - ux, y0 - uy)
            a0 = math.atan2(y0 - uy, x0 - ux)
            am = math.atan2(ym - uy, xm - ux)
            a1 = math.atan2(y1 - uy, x1 - ux)
            # choose the sweep direction that passes through the mid point
            def norm(a):
                return a % (2 * math.pi)
            ccw = norm(am - a0) < norm(a1 - a0)
            sweep = norm(a1 - a0) if ccw else -norm(a0 - a1)
            n = max(4, int(abs(sweep) * r / step))
            for i in range(n):
                a = a0 + sweep * i / n
                pts.append((ux + r * math.cos(a), uy + r * math.sin(a)))
    return pts
