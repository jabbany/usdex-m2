#!/usr/bin/env python3
"""Check the generated schematic and board against tools/msdx/design.py.

Run from the repository root after tools/build.sh has produced the netlist:

    python3 tools/verify.py            # uses build/msdx_m2_2230.net

Checks
  1. schematic netlist == design.nets(), and only the intended pins are open
  2. every PCB pad carries the net design.py gives it; placements match
  3. geometry that must hold regardless of how the layout code changes
     (M.2 finger positions, card overhang, contact-tip keep-out, AC-cap
     distance, differential-pair skew measured on the board file)
  4. KiCad DRC (pcbnew.WriteDRCReport): violations, unconnected pads,
     footprint errors must all be zero

Writes docs/verification.txt and docs/drc_report.txt. Exit status 1 on failure.
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # noqa: E402

from msdx import design as d  # noqa: E402
from msdx import geom as g  # noqa: E402
from msdx import netlist  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "hardware", d.PROJECT + ".kicad_pcb")
NET = os.path.join(ROOT, "build", d.PROJECT + ".net")
OUT = os.path.join(ROOT, "docs", "verification.txt")
DRC = os.path.join(ROOT, "docs", "drc_report.txt")

# Limits checked here (kept as literals so that a change in geom.py that
# breaks one of them is caught instead of silently followed).
SKEW_MAX = 0.15            # mm, intra-pair, per segment of the lane
ACCAP_MAX = 12.5           # mm, card transmitter pad to AC capacitor (SDA design guide)
M2_PIN_X = {1: 9.25, 2: 9.0, 41: -0.75, 43: -1.25, 47: -2.25, 49: -2.75,
            53: -3.75, 55: -4.25, 50: -3.0, 52: -3.5, 58: -5.0, 67: -7.25,
            74: -9.0, 75: -9.25}
BOARD_HALF_W = 11.0


class Report:
    def __init__(self):
        self.lines = []
        self.failed = 0

    def head(self, s):
        self.lines += ["", s, "-" * len(s)]

    def ok(self, cond, msg, detail=""):
        self.lines.append("  [%s] %s%s" % ("ok" if cond else "FAIL", msg, (": " + detail) if detail else ""))
        if not cond:
            self.failed += 1
        return cond

    def note(self, s):
        self.lines.append("        " + s)


def board_xy(v):
    return (pcbnew.ToMM(v.x) - g.OX, pcbnew.ToMM(v.y) - g.OY)


def check_netlist(r):
    r.head("1. Schematic netlist against design.py")
    if not os.path.exists(NET):
        r.ok(False, "netlist %s not found (run tools/build.sh)" % os.path.relpath(NET, ROOT))
        return
    comps, nets = netlist.read(NET)
    want = d.nets()
    got = {k.lstrip("/"): v for k, v in nets.items() if not k.startswith("unconnected-")}
    r.ok(set(comps) == set(d.BY_REF), "component set (%d parts)" % len(d.BY_REF),
         "" if set(comps) == set(d.BY_REF) else str(set(comps) ^ set(d.BY_REF)))
    r.ok(set(got) == set(want), "net names (%d nets)" % len(want),
         "" if set(got) == set(want) else str(set(got) ^ set(want)))
    bad = [n for n in want if got.get(n) != want[n]]
    r.ok(not bad, "net membership", ", ".join(bad))
    open_got = sorted(node for k, v in nets.items() if k.startswith("unconnected-") for node in v)
    open_want = sorted(d.unconnected_pins())
    r.ok(open_got == open_want, "intentionally open pins (%d)" % len(open_want),
         "" if open_got == open_want else str(set(open_got) ^ set(open_want)))
    bad = [ref for ref, c in comps.items() if c["footprint"] != d.BY_REF[ref]["fp"]]
    r.ok(not bad, "footprint assignments", ", ".join(bad))


def check_board(r, board):
    r.head("2. Board against design.py")
    want = {node: net for net, nodes in d.nets().items() for node in nodes}
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    r.ok(set(fps) == set(d.BY_REF), "footprint set (%d)" % len(fps))
    bad, n = [], 0
    for ref, fp in fps.items():
        for pad in fp.Pads():
            n += 1
            net = pad.GetNetname()
            if net.startswith("unconnected-"):   # KiCad's name for a single-pin net
                net = ""
            exp = want.get((ref, pad.GetNumber()), "")
            if net != exp:
                bad.append("%s.%s=%s (want %s)" % (ref, pad.GetNumber(), net or "-", exp or "-"))
    r.ok(not bad, "pad nets (%d pads)" % n, "; ".join(bad[:8]))
    bad = []
    for ref, fp in fps.items():
        p = d.BY_REF[ref]
        x, y = board_xy(fp.GetPosition())
        rot = fp.GetOrientationDegrees() % 360
        if abs(x - p["pos"][0]) > 1e-3 or abs(y - p["pos"][1]) > 1e-3 or abs(rot - p["rot"] % 360) > 1e-3:
            bad.append(ref)
        if fp.GetLayer() != pcbnew.F_Cu:
            bad.append(ref + " (not on top)")
    r.ok(not bad, "placements and side (all parts on top)", ", ".join(bad))


def net_lengths(board):
    out = {}
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        a, b = t.GetStart(), t.GetEnd()
        out.setdefault(t.GetNetname(), []).append(
            (pcbnew.ToMM(math.hypot(a.x - b.x, a.y - b.y)), pcbnew.ToMM(t.GetWidth()), t.GetLayer()))
    return out


def check_geometry(r, board):
    r.head("3. Geometry")
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    # M.2 fingers
    bad = []
    pads = {}
    for pad in fps["J1"].Pads():
        if pad.GetNumber().isdigit():
            pads[int(pad.GetNumber())] = pad
    for n, x in M2_PIN_X.items():
        px, py = board_xy(pads[n].GetPosition())
        top = pads[n].IsOnLayer(pcbnew.F_Cu)
        if abs(px - x) > 1e-3 or top != bool(n % 2):
            bad.append(str(n))
    r.ok(not bad, "M.2 finger X positions and sides (spot check of %d pins)" % len(M2_PIN_X), ", ".join(bad))
    r.ok(len(pads) == 67, "M.2 finger count", "%d pads (75 positions less 8 in the M key)" % len(pads))
    missing = [n for n in range(59, 67) if n in pads]
    r.ok(not missing, "no pads in the key (59-66)")

    # outline
    bb = board.GetBoardEdgesBoundingBox()
    w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    r.ok(abs(w - 22.0) < 0.06 and abs(h - 30.0) < 0.06, "outline 22 x 30 mm", "%.2f x %.2f" % (w, h))

    # inserted card stays inside the board width
    cx0, cy0, cx1, cy1 = g.skt_box(g.SKT_CARD)
    r.ok(max(abs(cx0), abs(cx1)) <= BOARD_HALF_W, "inserted card inside the 22 mm width",
         "card spans X %.2f .. %.2f" % (min(cx0, cx1), max(cx0, cx1)))

    # no top copper tracks or vias in the contact-tip keep-out
    kx0, ky0, kx1, ky1 = g.skt_box(g.SKT_TIP_KEEPOUT)
    kx0, kx1 = sorted((kx0, kx1))
    ky0, ky1 = sorted((ky0, ky1))
    hits = 0
    for t in board.GetTracks():
        is_via = t.Type() == pcbnew.PCB_VIA_T
        if not is_via and t.GetLayer() != pcbnew.F_Cu:
            continue
        pts = [board_xy(t.GetPosition())] if is_via else [board_xy(t.GetStart()), board_xy(t.GetEnd())]
        if not is_via:
            (ax, ay), (bx, by) = pts
            pts = [(ax + (bx - ax) * i / 20.0, ay + (by - ay) * i / 20.0) for i in range(21)]
        half = pcbnew.ToMM(t.GetWidth()) / 2
        if any(kx0 - half < x < kx1 + half and ky0 - half < y < ky1 + half for x, y in pts):
            hits += 1
    r.ok(hits == 0, "no top-layer tracks or vias under the socket contact tips",
         "keep-out X %.2f..%.2f, Y %.2f..%.2f" % (kx0, kx1, ky0, ky1))

    # differential pairs, measured on the board file
    lens = net_lengths(board)
    for name, (p, n) in d.DIFF_PAIRS.items():
        lp = sum(s[0] for s in lens.get(p, []))
        ln = sum(s[0] for s in lens.get(n, []))
        widths = {round(s[1], 3) for s in lens.get(p, []) + lens.get(n, [])}
        layers = {s[2] for s in lens.get(p, []) + lens.get(n, [])}
        r.ok(abs(lp - ln) <= SKEW_MAX, "%-6s skew <= %.2f mm" % (name, SKEW_MAX),
             "P %.3f  N %.3f  skew %.3f" % (lp, ln, abs(lp - ln)))
        r.ok(widths == {g.DP_W} and layers == {pcbnew.F_Cu},
             "%-6s on L1 only at %.2f mm, no vias" % (name, g.DP_W),
             "" if widths == {g.DP_W} else "widths %s" % sorted(widths))
    vias_on_pairs = [t.GetNetname() for t in board.GetTracks()
                     if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname().startswith("PCIE_")
                     and t.GetNetname() not in ("PCIE_PERST_N", "PCIE_CLKREQ_N")]
    r.ok(not vias_on_pairs, "no vias on any high-speed net", ", ".join(vias_on_pairs))
    rxc = max(sum(s[0] for s in lens.get(n, [])) for n in d.DIFF_PAIRS["RXC"])
    r.ok(rxc <= ACCAP_MAX, "AC capacitors within %.1f mm of the card transmitter pads" % ACCAP_MAX,
         "%.2f mm of trace" % rxc)
    total_tx = sum(s[0] for s in lens.get("PCIE_TX_P", []))
    total_rx = sum(s[0] for s in lens.get("PCIE_RX_P", [])) + sum(s[0] for s in lens.get("PCIE_RX_C_P", []))
    total_ck = sum(s[0] for s in lens.get("PCIE_REFCLK_P", []))
    r.note("lane lengths on the adapter: TX %.1f mm, RX %.1f mm (+ capacitor), REFCLK %.1f mm"
           % (total_tx, total_rx, total_ck))


def check_drc(r, board):
    r.head("4. KiCad DRC (%s)" % pcbnew.GetBuildVersion())
    pcbnew.WriteDRCReport(board, DRC, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(DRC).read()
    # keep the committed report free of the absolute path and timestamp
    txt = re.sub(r"^\*\* Drc report for .*$", "** Drc report for hardware/%s.kicad_pcb **" % d.PROJECT, txt, flags=re.M)
    txt = re.sub(r"^\*\* Created on .*\n", "", txt, flags=re.M)
    open(DRC, "w").write(txt)
    for what in ("DRC violations", "unconnected pads", "Footprint errors"):
        m = re.search(r"\*\* Found (\d+) %s" % what, txt)
        r.ok(bool(m) and int(m.group(1)) == 0, what, m.group(1) if m else "not reported")


def main():
    r = Report()
    r.lines.append("Verification of %s rev %s" % (d.PROJECT, d.REV))
    r.lines.append("Generated by tools/verify.py; do not edit.")
    check_netlist(r)
    board = pcbnew.LoadBoard(PCB)
    check_board(r, board)
    check_geometry(r, board)
    check_drc(r, board)
    r.head("Not covered")
    for s in ("KiCad ERC (kicad-cli 7 has no ERC command; run it in the schematic editor)",
              "controlled impedance: the 0.16/0.15 mm pair geometry is a placeholder, see DESIGN.md",
              "anything electrical: the board has not been built"):
        r.lines.append("  - " + s)
    r.lines.append("")
    r.lines.append("RESULT: %s" % ("PASS" if not r.failed else "%d check(s) FAILED" % r.failed))
    text = "\n".join(r.lines) + "\n"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(text)
    print(text)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
