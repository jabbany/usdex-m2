"""Copper layout as plain data: tracks, vias and zones in the board frame.

No KiCad imports here, so the routing can be inspected, measured and tested
with nothing but Python. gen_pcb.py turns the result into a .kicad_pcb.

Layer names: "F.Cu" (L1), "In1.Cu" (L2), "In2.Cu" (L3), "B.Cu" (L4).
"""
import math

from . import design as d
from . import geom as g

L1, L2, L3, L4 = "F.Cu", "In1.Cu", "In2.Cu", "B.Cu"
GND, V33, V18 = d.GND, d.V33, d.V18

H = g.DP_PITCH / 2          # half pitch of a coupled pair
W = g.DP_W


# --------------------------------------------------------------------------
# polyline helpers (screen frame: X right, Y down)
# --------------------------------------------------------------------------
def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n)


def _left(dv):
    """Unit normal pointing to the left of travel as seen on screen."""
    return (dv[1], -dv[0])


def offset_path(pts, dist):
    """Parallel polyline `dist` to the left of travel (negative = right),
    with mitred corners so a pair stays evenly spaced through bends."""
    out = []
    for i, p in enumerate(pts):
        if i == 0:
            n = _left(_unit(pts[0], pts[1]))
            out.append((p[0] + n[0] * dist, p[1] + n[1] * dist))
        elif i == len(pts) - 1:
            n = _left(_unit(pts[-2], pts[-1]))
            out.append((p[0] + n[0] * dist, p[1] + n[1] * dist))
        else:
            n1 = _left(_unit(pts[i - 1], p))
            n2 = _left(_unit(p, pts[i + 1]))
            mx, my = n1[0] + n2[0], n1[1] + n2[1]
            ml = math.hypot(mx, my)
            mx, my = mx / ml, my / ml
            k = dist / (mx * n1[0] + my * n1[1])
            out.append((p[0] + mx * k, p[1] + my * k))
    return [(round(x, 4), round(y, 4)) for x, y in out]


def length(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:]))


BUMP_GAIN = 2 * (math.sqrt(2) - 1)   # extra length per unit of bump amplitude


def add_bumps(pts, seg, extra, side, max_amp=0.32, flat=0.3, lead=0.5):
    """Lengthen a trace by `extra` with trapezoidal bumps on segment `seg`
    (index of its first point). `side` is +1 for left of travel, -1 for right.
    Returns a new point list."""
    if extra <= 0.01:
        return list(pts)
    count = max(1, math.ceil(extra / (BUMP_GAIN * max_amp)))
    amp = extra / (BUMP_GAIN * count)
    a, b = pts[seg], pts[seg + 1]
    dv = _unit(a, b)
    nv = _left(dv)
    nv = (nv[0] * side, nv[1] * side)
    need = lead + count * (2 * amp + flat) + (count - 1) * flat + lead
    if need > math.hypot(b[0] - a[0], b[1] - a[1]):
        raise ValueError(f"segment too short for {count} bumps ({need:.2f} mm needed)")
    new = []
    s = lead
    for _ in range(count):
        p0 = (a[0] + dv[0] * s, a[1] + dv[1] * s)
        p1 = (p0[0] + (dv[0] + nv[0]) * amp, p0[1] + (dv[1] + nv[1]) * amp)
        p2 = (p1[0] + dv[0] * flat, p1[1] + dv[1] * flat)
        p3 = (p2[0] + (dv[0] - nv[0]) * amp, p2[1] + (dv[1] - nv[1]) * amp)
        new += [p0, p1, p2, p3]
        s += 2 * amp + 2 * flat
    out = list(pts[:seg + 1]) + [(round(x, 4), round(y, 4)) for x, y in new] + list(pts[seg + 1:])
    return out


def match(p_pts, n_pts, p_seg, n_seg, p_side, n_side):
    """Equalise two traces of a pair by adding bumps to the shorter one.
    *_seg: (point index of the segment that may take bumps); *_side: which
    way the bumps go (away from the partner trace)."""
    lp, ln = length(p_pts), length(n_pts)
    if lp < ln:
        p_pts = add_bumps(p_pts, p_seg, ln - lp, p_side)
    else:
        n_pts = add_bumps(n_pts, n_seg, lp - ln, n_side)
    return p_pts, n_pts


# --------------------------------------------------------------------------
class Layout:
    def __init__(self):
        self.tracks = []      # (net, layer, width, [(x, y), ...])
        self.vias = []        # (net, (x, y), diameter, drill)
        self.zones = []       # dict(net, layer, pts, name, clearance, ...)
        self.report = {}      # pair name -> dict of lengths

    def track(self, net, pts, width=g.SIG_W, layer=L1):
        self.tracks.append((net, layer, width, [(round(x, 4), round(y, 4)) for x, y in pts]))

    def via(self, net, pos, size=g.VIA):
        self.vias.append((net, (round(pos[0], 4), round(pos[1], 4)), size[0], size[1]))

    def pair_report(self, name, p_pts, n_pts):
        r = self.report.setdefault(name, {})
        r["p"] = round(length(p_pts), 3)
        r["n"] = round(length(n_pts), 3)
        r["skew"] = round(abs(r["p"] - r["n"]), 3)


def pad(ref, name):
    """Board-frame pad centre for the parts the routes refer to."""
    p = d.BY_REF[ref]
    if ref == "J1":
        n = int(name)
        y = g.BOARD_L - (g.M2_FINGER_SETBACK + ((g.M2_FINGER_TOP_END if n % 2 else g.M2_FINGER_BOT_END)
                                               - g.M2_FINGER_SETBACK) / 2)
        return (g.m2_pin_x(n), y)
    if ref == "J2":
        return g.skt_pad(name)
    fp = p["fp"].split(":")[1]
    if fp.startswith("R_0402"):
        dx = 0.51
    elif fp.startswith("C_0402"):
        dx = 0.48
    elif fp.startswith("C_0603"):
        dx = 0.775
    elif fp.startswith("L_Murata"):
        dx = 0.725
    elif fp.startswith("TestPad"):
        return p["pos"]
    elif fp == "SOT-23-5":
        xy = {"1": (-1.1375, -0.95), "2": (-1.1375, 0), "3": (-1.1375, 0.95),
              "4": (1.1375, 0.95), "5": (1.1375, -0.95)}[name]
        return g.place(p["pos"], p["rot"], *xy)
    else:
        raise KeyError(fp)
    return g.place(p["pos"], p["rot"], -dx if name == "1" else dx, 0)


def finger_entry(pin, lane_x, y_lane):
    """Finger pad centre -> straight up -> 45 degree jog onto the lane."""
    x, y = pad("J1", pin)
    dx = abs(lane_x - x)
    return [(x, y), (x, y_lane + dx), (lane_x, y_lane)]


# --------------------------------------------------------------------------
def build():
    lo = Layout()
    T, V = lo.track, lo.via
    top_f = g.M2_TOP_FINGER_Y      # 28.0
    bot_f = g.M2_BOT_FINGER_Y      # 27.5
    y_ent = 27.6                   # where finger stubs have converged onto the lanes

    # ------------------------------------------------------------------ TX
    # host PETp0/PETn0 (pins 49/47) -> card Tx+/Tx- (socket pads 11/12).
    # Enters under the socket between the two lower-right shield tabs, east of
    # the contact-tip zone, and reaches the pads from the inside. Polarity
    # is preserved.
    tx_c = [(-2.5, y_ent), (-2.5, 24.5), (-1.9, 23.9), (4.555, 23.9), (5.155, 23.3),
            (5.155, 14.805), (5.755, 14.205), (6.2, 14.205)]
    p11, p12 = pad("J2", "11"), pad("J2", "12")
    tx_p = finger_entry(49, -2.5 - H, y_ent)[:-1] + offset_path(tx_c, H) + \
        [(6.2 + (14.205 - H - p11[1]), p11[1]), p11]
    tx_n = finger_entry(47, -2.5 + H, y_ent)[:-1] + offset_path(tx_c, -H) + \
        [(6.2 + (p12[1] - 14.205 - H), p12[1]), p12]
    # compensation bumps on the long vertical run under the socket
    tx_p, tx_n = match(tx_p, tx_n, _seg(tx_p, 5.155 - H, 20), _seg(tx_n, 5.155 + H, 20), +1, -1)
    T("PCIE_TX_P", tx_p, W)
    T("PCIE_TX_N", tx_n, W)
    lo.pair_report("TX", tx_p, tx_n)

    # ------------------------------------------------------------------ RX
    # card Rx+/Rx- (pads 15/14) -> C4/C5 -> host PERp0/PERn0 (pins 43/41).
    # Leaves the socket at the card mouth, runs down the right-hand margin
    # and along the bottom. Polarity is preserved.
    rx_c = [(-1.0, y_ent), (-1.0, 25.9), (-0.4, 25.3), (8.7, 25.3), (9.3, 24.7), (9.3, 24.5)]
    c4a, c4b = pad("C4", "1"), pad("C4", "2")
    c5a, c5b = pad("C5", "1"), pad("C5", "2")
    rx_p = finger_entry(43, -1.0 - H, y_ent)[:-1] + offset_path(rx_c, H) + \
        [(c4a[0], 24.5 - (9.3 - H - c4a[0])), c4a]
    rx_n = finger_entry(41, -1.0 + H, y_ent)[:-1] + offset_path(rx_c, -H) + \
        [(c5a[0], 24.5 - (c5a[0] - 9.3 - H)), c5a]
    rx_p, rx_n = match(rx_p, rx_n, _seg(rx_p, None, 5.0, y=25.3 - H), _seg(rx_n, None, 5.0, y=25.3 + H), +1, -1)
    T("PCIE_RX_P", rx_p, W)
    T("PCIE_RX_N", rx_n, W)
    lo.pair_report("RX", rx_p, rx_n)

    p15, p14 = pad("J2", "15"), pad("J2", "14")
    yc = (p15[1] + p14[1]) / 2
    y_join = 21.955
    rxc_c = [(9.3, y_join), (9.3, yc + 0.6), (8.7, yc), (8.6, yc)]
    rxc_p = [c4b, (c4b[0], y_join + (9.3 - H - c4b[0]))] + offset_path(rxc_c, H) + \
        [(8.6 - (p15[1] - yc - H), p15[1]), p15]
    rxc_n = [c5b, (c5b[0], y_join + (c5b[0] - 9.3 - H))] + offset_path(rxc_c, -H) + \
        [(8.6 - (yc - H - p14[1]), p14[1]), p14]
    rxc_p, rxc_n = match(rxc_p, rxc_n, _seg(rxc_p, 9.3 - H, 20), _seg(rxc_n, 9.3 + H, 20), +1, -1)
    T("PCIE_RX_C_P", rxc_p, W)
    T("PCIE_RX_C_N", rxc_n, W)
    lo.pair_report("RX_C", rxc_p, rxc_n)

    # -------------------------------------------------------------- REFCLK
    # pins 55/53 -> socket pads 7/8, up the left margin so the pair reaches
    # the row-1 pads from outside the socket with its polarity intact.
    p7, p8 = pad("J2", "7"), pad("J2", "8")
    yk = (p7[1] + p8[1]) / 2
    ck_c = [(-4.0, y_ent), (-4.0, 25.755), (-4.6, 25.155), (-7.7, 25.155), (-8.3, 24.555),
            (-8.3, yk + 0.6), (-7.7, yk), (-7.6, yk)]
    ck_p = finger_entry(55, -4.0 - H, y_ent)[:-1] + offset_path(ck_c, H) + \
        [(-7.6 + (yk - H - p7[1]), p7[1]), p7]
    ck_n = finger_entry(53, -4.0 + H, y_ent)[:-1] + offset_path(ck_c, -H) + \
        [(-7.6 + (p8[1] - yk - H), p8[1]), p8]
    ck_p, ck_n = match(ck_p, ck_n, _seg(ck_p, -8.3 - H, 22), _seg(ck_n, -8.3 + H, 22), +1, -1)
    T("PCIE_REFCLK_P", ck_p, W)
    T("PCIE_REFCLK_N", ck_n, W)
    lo.pair_report("REFCLK", ck_p, ck_n)

    # ------------------------------------------------- sideband (L4 and L1)
    # PERST#/CLKREQ# leave bottom-side fingers 50/52, run up the middle of
    # L4, then west above socket row 1 and down the far-left edge to the
    # series resistors.
    r1a, r2a = pad("R1", "1"), pad("R2", "1")
    vx = -9.75
    f50, f52 = pad("J1", "50"), pad("J1", "52")
    T("PCIE_PERST_N", [f50, (f50[0], 8.9), (f50[0] - 0.3, 8.6), (-10.0, 8.6), (-10.3, 8.9),
                       (-10.3, r1a[1] - 0.55), (vx, r1a[1])], layer=L4)
    T("PCIE_CLKREQ_N", [f52, (f52[0], 9.2), (f52[0] - 0.3, 8.9), (vx + 0.3, 8.9), (vx, 9.2),
                        (vx, r2a[1])], layer=L4)
    V("PCIE_PERST_N", (vx, r1a[1]))
    V("PCIE_CLKREQ_N", (vx, r2a[1]))
    T("PCIE_PERST_N", [(vx, r1a[1]), r1a])
    T("PCIE_CLKREQ_N", [(vx, r2a[1]), r2a])
    T("PCIE_CLKREQ_N", [r2a, pad("R3", "1")])
    T("SD_PERST_N", [pad("R1", "2"), pad("J2", "2")])
    T("SD_CLKREQ_N", [pad("R2", "2"), pad("J2", "1")])
    T("SD_CMD", [pad("R4", "2"), pad("J2", "3")])
    T("SD_CLK", [pad("R5", "2"), pad("J2", "5")])

    # R9: M.2 pin 73 to ground
    f73, r9a, r9b = pad("J1", "73"), pad("R9", "1"), pad("R9", "2")
    T("M2_PIN73", [f73, (f73[0], 26.5), (r9a[0], 26.5 - (f73[0] - r9a[0])), r9a])
    T(GND, [r9b, (r9b[0], 23.5)], 0.3)
    V(GND, (r9b[0], 23.5))

    # -------------------------------------------------------------- 3.3 V
    # L4 is a 3.3 V pour fed by the nine bottom-side fingers; short stubs take
    # each finger up into it (the pour itself stays out of the finger area).
    for pin in (2, 4, 12, 14, 16, 18, 70, 72, 74):
        x, y = pad("J1", pin)
        T(V33, [(x, y), (x, bot_f - 0.45)], 0.3, L4)
    T(V33, [(g.m2_pin_x(74), bot_f - 0.3), (g.m2_pin_x(70), bot_f - 0.3)], 0.3, L4)
    T(V33, [(g.m2_pin_x(18), bot_f - 0.3), (g.m2_pin_x(12), bot_f - 0.3)], 0.3, L4)
    T(V33, [(g.m2_pin_x(4), bot_f - 0.3), (g.m2_pin_x(2), bot_f - 0.3)], 0.3, L4)

    # VDD1 at socket pin 4: C3, then two vias under the socket floor
    c3b, j4 = pad("C3", "2"), pad("J2", "4")
    T(V33, [c3b, j4, (-4.65, j4[1])], 0.4)
    V(V33, (-5.25, j4[1]))
    V(V33, (-4.65, j4[1]))
    # pull-ups
    r4a = pad("R4", "1")
    T(V33, [r4a, (vx, r4a[1])])
    V(V33, (vx, r4a[1]))
    r3b = pad("R3", "2")
    T(V33, [r3b, (-6.85, r3b[1])])
    V(V33, (-6.85, r3b[1]))
    # bulk capacitors and test pad
    c1b, c2b, tp1 = pad("C1", "2"), pad("C2", "2"), pad("TP1", "1")
    T(V33, [c1b, (-7.3, c1b[1]), (-7.3, c2b[1]), c2b], 0.4)
    T(V33, [(-7.3, tp1[1]), tp1], 0.4)
    # The sideband traces on L4 fence off the left part of the 3.3 V pour
    # (it is still fed by fingers 70-74); this top-layer link ties the two
    # parts together so the net is one piece.
    T(V33, [(-7.3, c2b[1]), (-7.3, 8.8), (-6.85, 9.25), (-6.85, r3b[1])], 0.4)
    V(V33, (-7.3, c1b[1]))
    V(V33, (-7.3, c2b[1]))
    # buck input
    u4, c7a = pad("U1", "4"), pad("C7", "1")
    T(V33, [u4, (c7a[0], u4[1]), c7a], 0.5)
    V(V33, (6.65, u4[1]))
    T(V33, [u4, (5.0, u4[1])], 0.4)
    V(V33, (5.0, u4[1]))
    # EN pull-up
    r6a = pad("R6", "1")
    T(V33, [r6a, (0.9, r6a[1])])
    V(V33, (0.9, r6a[1]))

    # ---------------------------------------------------------------- buck
    u1, u2, u3, u5 = pad("U1", "1"), pad("U1", "2"), pad("U1", "3"), pad("U1", "5")
    l1a, l1b = pad("L1", "1"), pad("L1", "2")
    T("BUCK_SW", [u3, (l1a[0], u3[1]), l1a], 0.5)
    # feedback node: U1.5 -> R8.2 -> R7.1
    r8a, r8b, r7a, r7b = pad("R8", "1"), pad("R8", "2"), pad("R7", "1"), pad("R7", "2")
    T("BUCK_FB", [u5, (u5[0], 1.85), (u5[0] + 0.55, 1.3), (r8b[0], 1.3), r8b, r7a])
    # enable node
    c6b, r6b = pad("C6", "2"), pad("R6", "2")
    T("BUCK_EN", [u1, (c6b[0], u1[1]), c6b, r6b])
    # output: inductor -> C8 -> trunk down the right margin -> socket pin 9
    c8a, c9b, c10b, tp2, j9 = pad("C8", "1"), pad("C9", "2"), pad("C10", "2"), pad("TP2", "1"), pad("J2", "9")
    T(V18, [l1b, (l1b[0], 4.9), (l1b[0] + 0.475, c8a[1]), c8a], g.PWR_W)
    T(V18, [c8a, (c8a[0], 8.7), (9.3, 9.4), (9.3, j9[1] - 0.3), (9.0, j9[1]), j9], g.PWR_W)
    T(V18, [c9b, (c8a[0], c9b[1])], 0.4)
    T(V18, [c10b, (c8a[0], c10b[1])], 0.4)
    # output sense for the feedback divider, on L4 away from the switch node
    T(V18, [r7b, (7.85, r7b[1]), (tp2[0] - 0.4, r7b[1]), tp2])
    V(V18, (7.85, r7b[1]), g.VIA_SMALL)
    V(V18, (9.35, c9b[1]), g.VIA_SMALL)
    T(V18, [(7.85, r7b[1]), (8.3, r7b[1] + 0.45), (8.3, 5.55), (9.05, c9b[1]), (9.35, c9b[1])], layer=L4)

    # ---------------------------------------------------------------- GND
    # regulator ground: under the body and below the pin
    T(GND, [u2, (u2[0], 3.4)], 0.4)
    V(GND, (u2[0], 3.4))
    T(GND, [u2, (u2[0], 5.85)], 0.4)
    V(GND, (u2[0], 5.85))
    c7b, c8b, c9a, c10a = pad("C7", "2"), pad("C8", "2"), pad("C9", "1"), pad("C10", "1")
    T(GND, [c7b, (9.7, c7b[1]), (c8b[0], c7b[1] + 0.3), c8b], 0.4)
    V(GND, (c8b[0], 2.8))
    T(GND, [c7b, (c7b[0], 1.3)], 0.4)
    V(GND, (c7b[0], 1.3))
    T(GND, [c9a, (6.15, c9a[1])], 0.4)
    V(GND, (6.15, c9a[1]))
    T(GND, [c10a, (c10a[0], 8.5)], 0.3)
    V(GND, (c10a[0], 8.5))
    T(GND, [r8a, (3.4, r8a[1])])
    V(GND, (3.4, r8a[1]))
    c6a = pad("C6", "1")
    T(GND, [c6a, (0.95, c6a[1])])
    V(GND, (0.95, c6a[1]))
    # left-margin parts
    for ref in ("C3", "R5"):
        a = pad(ref, "1")
        T(GND, [a, (vx, a[1])])
        V(GND, (vx, a[1]))
    c1a, c2a = pad("C1", "1"), pad("C2", "1")
    T(GND, [c1a, (c1a[0], 2.4)], 0.4)
    V(GND, (c1a[0], 2.4))
    T(GND, [c2a, (c2a[0], 6.9)], 0.4)
    V(GND, (c2a[0], 6.9))
    # socket ground pads: vias just inside the footprint, under the floor
    j6 = pad("J2", "6")
    T(GND, [j6, (-5.25, j6[1])], 0.3)
    V(GND, (-5.25, j6[1]))
    for name in ("10", "13", "16"):
        a = pad("J2", name)
        T(GND, [a, (6.5, a[1])], 0.3)
        V(GND, (6.5, a[1]))
    # shield tabs
    for (x, y) in g.skt_shield_pads():
        if y < g.SKT_POS[1] and x > 5:
            # upper-right tab: C9's ground pad sits right above it, share its via
            T(GND, [(x, y), (x, c9a[1] + 0.3), c9a], 0.4)
            continue
        vy = y - 1.1 if y < g.SKT_POS[1] else y + 1.25
        T(GND, [(x, y), (x, vy)], 0.4)
        V(GND, (x, vy))
    # M.2 ground fingers: stub up into the L1 pour, vias where L4 allows
    for pin in (1, 3, 9, 15, 21, 27, 33, 39, 45, 51, 57, 71, 75):
        x, y = pad("J1", pin)
        T(GND, [(x, y), (x, top_f - 0.6)], 0.2)
    for pin in (39, 45, 57):                      # return vias beside the pairs
        x = g.m2_pin_x(pin)
        T(GND, [(x, top_f - 0.6), (x, 27.1)], 0.2)
        V(GND, (x, 27.1), g.VIA_SMALL)
    T(GND, [(g.m2_pin_x(51), top_f - 0.6), (g.m2_pin_x(51), 26.3)], 0.2)
    T(GND, [(g.m2_pin_x(75), top_f - 0.6), (g.m2_pin_x(75), 27.0), (-9.35, 26.6)], 0.2)
    V(GND, (-9.35, 26.6), g.VIA_SMALL)
    T(GND, [(g.m2_pin_x(71), top_f - 0.6), (g.m2_pin_x(71), 26.4)], 0.2)
    V(GND, (g.m2_pin_x(71), 26.4), g.VIA_SMALL)
    # mounting pad: tie the top and bottom half-rings to the planes
    V(GND, (1.7, 1.7))
    V(GND, (-1.7, 1.7))

    # stitching / return vias along the pairs and around the board
    for xy in STITCH:
        V(GND, xy)

    # ---------------------------------------------------------------- zones
    hw = g.BOARD_W / 2
    box = lambda y1: [(-hw, 0), (hw, 0), (hw, y1), (-hw, y1)]
    lo.zones = [
        dict(net=GND, layer=L1, pts=box(top_f - 0.25), name="GND_L1", clearance=0.35, thermal=True, prio=0),
        dict(net=GND, layer=L2, pts=box(top_f - 0.3), name="GND_L2", clearance=0.2, thermal=False, prio=0),
        dict(net=GND, layer=L3, pts=box(bot_f - 0.3), name="GND_L3", clearance=0.2, thermal=False, prio=0),
        dict(net=V33, layer=L4, pts=box(bot_f - 0.25), name="3V3_L4", clearance=0.2, thermal=False, prio=0),
    ]
    return lo


# ground stitching vias (board frame); kept clear of the L4 sideband lanes at
# X = -3.0 / -3.5 and of every pair
STITCH = [
    (-4.4, 24.3),                 # joins finger-51 ground to the planes, beside REFCLK/TX
    (-1.7, 23.0), (0.6, 23.0), (3.4, 23.0),          # north of the TX lane
    (0.8, 26.3), (3.0, 26.3), (5.2, 26.3), (7.4, 26.3),   # south of the RX lane
    (10.3, 21.0), (10.3, 19.0),   # outside the RX pair in the right margin
    (-9.6, 21.5), (-9.6, 19.0), (-9.6, 16.8),        # outside the REFCLK lane
    (-6.9, 23.6),                 # inside the REFCLK loop
    (-2.0, 4.8), (-4.5, 2.2), (-10.2, 0.8),
    (-0.8, 12.0), (-0.8, 17.0), (0.8, 9.6), (0.8, 19.6),   # under the socket floor
]


def _seg(pts, x=None, min_len=0, y=None):
    """Index of the longest segment lying on the given X (or Y) lane."""
    best, best_len = None, 0
    for i, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        if x is not None and (abs(a[0] - x) > 1e-3 or abs(b[0] - x) > 1e-3):
            continue
        if y is not None and (abs(a[1] - y) > 1e-3 or abs(b[1] - y) > 1e-3):
            continue
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        if ln > best_len:
            best, best_len = i, ln
    if best is None:
        raise ValueError("no segment on that lane")
    return best
