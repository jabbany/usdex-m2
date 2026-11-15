#!/usr/bin/env python3
"""Generate hardware/msdx_m2_2230.kicad_sch from tools/msdx/design.py.

The schematic is label-connected: every used pin gets a short wire and a
global label carrying the net name, so the drawing reads like the net table
in DESIGN.md and the net names in the PCB match exactly.

Run from the repository root:  python3 tools/gen_sch.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msdx import design as d  # noqa: E402
from msdx import symbols  # noqa: E402
from msdx.sexp import num as n, q, uid  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "hardware", d.PROJECT + ".kicad_sch")
ROOT_UUID = uid("sch", "root")
G = 1.27  # schematic grid
STUB = 2 * G

FONT = "(effects (font (size 1.27 1.27)))"


def snap(v):
    return round(round(v / G) * G, 4)


class Sheet:
    def __init__(self):
        self.items = []
        self.lib_ids = []
        self.pwr = 0
        self.flg = 0

    # -- primitives ---------------------------------------------------------
    def wire(self, a, b):
        self.items.append(
            f'  (wire (pts (xy {n(a[0])} {n(a[1])}) (xy {n(b[0])} {n(b[1])})) '
            f'(stroke (width 0) (type default)) (uuid {uid("wire", a, b)}))')

    def label(self, net, pos, ang):
        just = "right" if ang in (180, 270) else "left"
        self.items.append(
            f'  (global_label {q(net)} (shape passive) (at {n(pos[0])} {n(pos[1])} {ang}) '
            f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {uid("glabel", net, pos)})\n'
            f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) hide))\n  )')

    def nc(self, pos):
        self.items.append(f'  (no_connect (at {n(pos[0])} {n(pos[1])}) (uuid {uid("nc", pos)}))')

    def text(self, s, pos, size=1.27, bold=False):
        b = " bold" if bold else ""
        self.items.append(
            f'  (text {q(s).replace(chr(10), chr(92) + "n")} (at {n(pos[0])} {n(pos[1])} 0) '
            f'(effects (font (size {n(size)} {n(size)}){b}) (justify left bottom)) (uuid {uid("text", s, pos)}))')

    def frame(self, x0, y0, x1, y1, title):
        self.items.append(
            f'  (rectangle (start {n(x0)} {n(y0)}) (end {n(x1)} {n(y1)}) '
            f'(stroke (width 0) (type dash)) (fill (type none)) (uuid {uid("rect", title)}))')
        self.text(title, (x0 + G, y0 + 3 * G), 1.8, True)

    # -- symbols ------------------------------------------------------------
    def symbol(self, lib_id, ref, value, pos, rot=0, props=None, dnp=False, in_bom=True,
               on_board=True, ref_at=None, val_at=None, hide_ref=False, hide_val=False,
               ref_just="", val_just=""):
        if lib_id not in self.lib_ids:
            self.lib_ids.append(lib_id)
        pins = symbols.symbol_pins(lib_id)
        fang = 90 if rot in (90, 270) else 0
        ref_at = ref_at or (pos[0], pos[1] - 2 * G)
        val_at = val_at or (pos[0], pos[1] + 2 * G)
        lines = [
            f'  (symbol (lib_id {q(lib_id)}) (at {n(pos[0])} {n(pos[1])} {rot}) (unit 1)',
            f'    (in_bom {"yes" if in_bom else "no"}) (on_board {"yes" if on_board else "no"}) '
            f'(dnp {"yes" if dnp else "no"})',
            f'    (uuid {uid("sym", ref)})',
            f'    (property "Reference" {q(ref)} (at {n(ref_at[0])} {n(ref_at[1])} {fang}) '
            f'(effects (font (size 1.27 1.27)){ref_just}{" hide" if hide_ref else ""}))',
            f'    (property "Value" {q(value)} (at {n(val_at[0])} {n(val_at[1])} {fang}) '
            f'(effects (font (size 1.27 1.27)){val_just}{" hide" if hide_val else ""}))',
        ]
        for k, v in (props or {}).items():
            lines.append(f'    (property {q(k)} {q(v)} (at {n(pos[0])} {n(pos[1])} 0) '
                         f'(effects (font (size 1.27 1.27)) hide))')
        for num in pins:
            lines.append(f'    (pin {q(num)} (uuid {uid("pin", ref, num)}))')
        lines.append(f'    (instances (project {q(d.PROJECT)} (path "/{ROOT_UUID}" '
                     f'(reference {q(ref)}) (unit 1))))')
        lines.append("  )")
        self.items.append("\n".join(lines))
        return pins

    def pin_xy(self, pins, num, pos, rot):
        """Sheet position of a pin's connection point and the outward direction."""
        px, py, ang, _ = pins[num]
        a = math.radians(rot)
        x, y = px, -py
        sx = pos[0] + x * math.cos(a) + y * math.sin(a)
        sy = pos[1] - x * math.sin(a) + y * math.cos(a)
        out = math.radians(ang + 180 + rot)
        return (round(sx, 4), round(sy, 4)), (round(math.cos(out)), round(-math.sin(out)))

    def connect(self, pins, num, pos, rot, net, stub=STUB):
        """Wire stub + global label on a pin; no-connect marker if net is None."""
        p, (dx, dy) = self.pin_xy(pins, num, pos, rot)
        if net is None:
            self.nc(p)
            return
        e = (round(p[0] + dx * stub, 4), round(p[1] + dy * stub, 4))
        self.wire(p, e)
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
        self.label(net, e, ang)

    def part(self, ref, pos, rot=0, **kw):
        """Place a part from design.PARTS and connect all of its pins."""
        p = d.BY_REF[ref]
        props = {"Footprint": p["fp"], "Datasheet": "~", "Description": p["desc"]}
        if p["mpn"]:
            props["MPN"] = p["mpn"]
        value = p["value"]
        pins = self.symbol(p["sym"], ref, value, pos, rot, props, dnp=p["dnp"], **kw)
        for num in pins:
            self.connect(pins, num, pos, rot, p["pins"].get(num))
        return pins

    def power(self, net, pos, flag_dx=8 * G):
        """Power symbol + PWR_FLAG + global label tying the three together."""
        self.pwr += 1
        self.flg += 1
        up = net != d.GND
        lib = "power:" + net
        self.symbol(lib, f"#PWR{self.pwr:02d}", net, pos, 0, {"Footprint": "", "Datasheet": ""},
                    in_bom=False, hide_ref=True, val_at=(pos[0], pos[1] + (-5 * G if up else 5 * G)))
        fpos = (pos[0] + flag_dx, pos[1])
        self.symbol("power:PWR_FLAG", f"#FLG{self.flg:02d}", "PWR_FLAG", fpos, 0 if up else 180,
                    {"Footprint": "", "Datasheet": "~"}, in_bom=False, hide_ref=True,
                    val_at=(fpos[0], fpos[1] + (-5 * G if up else 5 * G)))
        a = (pos[0] - 2 * G, pos[1])
        self.wire(a, pos)
        self.wire(pos, fpos)
        self.label(net, a, 180)

    # -- output -------------------------------------------------------------
    def render(self):
        libs = "\n".join("    " + line for lib_id in self.lib_ids
                         for line in symbols.embedded_symbol(lib_id).split("\n"))
        head = (
            f'(kicad_sch (version 20230121) (generator eeschema)\n'
            f'  (uuid {ROOT_UUID})\n'
            f'  (paper "A3")\n'
            f'  (title_block\n'
            f'    (title {q(d.TITLE)})\n'
            f'    (date {q(d.DATE)})\n'
            f'    (rev {q(d.REV)})\n'
            f'    (comment 1 "Generated by tools/gen_sch.py from tools/msdx/design.py")\n'
            f'    (comment 2 "PCIe Gen3 x1 pass-through; card in PCIe/NVMe mode only")\n'
            f'  )\n'
            f'  (lib_symbols\n{libs}\n  )\n')
        tail = '  (sheet_instances (path "/" (page "1")))\n)\n'
        return head + "\n".join(self.items) + "\n" + tail


def row(sh, ref, cx, cy):
    """A two-pin part drawn horizontally: pin 1 on the left, pin 2 on the right."""
    up = 3.0 if ref[0] == "C" else 2.3     # capacitor plates are taller than a resistor body
    sh.part(ref, (snap(cx), snap(cy)), 90,
            ref_at=(snap(cx), snap(cy) - up * G), val_at=(snap(cx), snap(cy) + (up + 0.1) * G))


def build():
    sh = Sheet()
    P = 7 * G   # row pitch for two-pin parts

    # ---- M.2 card edge ----------------------------------------------------
    sh.frame(10 * G, 20 * G, 92 * G, 164 * G, "J1  M.2 Key M card edge (to host)")
    sh.text("Odd pins: top side.  Even pins: bottom side.\n"
            "Signal names are the M.2 spec's (host view):\n"
            "PET = host transmit, PER = host receive.\n"
            "Lanes 1-3, SATA, USB, SMBus: not used.", (12 * G, 34 * G))
    j1 = (snap(51 * G), snap(122 * G))
    sh.part("J1", j1, 0, ref_at=(j1[0], j1[1] - 37 * G), val_at=(j1[0], j1[1] + 37 * G))

    # ---- microSD Express socket ---------------------------------------------
    sh.frame(232 * G, 20 * G, 318 * G, 78 * G, "J2  microSD Express socket (to card)")
    sh.text("Tx/Rx named from the host: pads 11/12 are the card's receiver,\n"
            "pads 14/15 its transmitter. Pad 17 (VDD3, 1.2 V) and DET unused.",
            (234 * G, 30 * G))
    j2 = (snap(275 * G), snap(52 * G))
    sh.part("J2", j2, 0, ref_at=(j2[0], j2[1] - 13 * G), val_at=(j2[0], j2[1] + 13 * G))

    # ---- PCIe lane ------------------------------------------------------------
    sh.frame(98 * G, 20 * G, 226 * G, 62 * G, "PCIe lane 0")
    sh.text("Host-to-card pair (PCIE_TX_P/N) and REFCLK connect J1 to J2 directly.\n"
            "The card has no AC coupling on its transmitter, so the card-to-host pair\n"
            "gets 220 nF here, within 12.5 mm of the socket (SD Express host guideline).\n"
            "Polarity is preserved on all three pairs.", (100 * G, 34 * G))
    row(sh, "C4", 162 * G, 44 * G)
    row(sh, "C5", 162 * G, 44 * G + P)

    # ---- sideband ---------------------------------------------------------------
    sh.frame(98 * G, 66 * G, 226 * G, 132 * G, "Sideband and legacy SD pins")
    sh.text("PERST#/CLKREQ# go straight through 0R links (place for series R or a translator).\n"
            "CMD and CLK must not float in PCIe mode: CMD is pulled up, CLK is held low so no\n"
            "stray edge can switch the card to SD mode. R3 is fitted only if the host has no\n"
            "CLKREQ# pull-up. R9 grounds M.2 pin 73 like every legacy (3.3 V sideband) module.",
            (100 * G, 82 * G))
    for i, ref in enumerate(("R1", "R2", "R3", "R4", "R5", "R9")):
        row(sh, ref, 162 * G, 92 * G + i * P)

    # ---- buck ---------------------------------------------------------------------
    sh.frame(98 * G, 136 * G, 318 * G, 190 * G, "1.8 V supply for VDD2 (TLV62568, 1 A buck)")
    sh.text("Vout = 0.6 V x (1 + R7/R8) = 1.80 V.  R6/C6 delay EN about 8 ms so VDD2 rises after VDD1,\n"
            "which is what puts the card into PCIe mode.  Sustained card load 0.4 A, peak 0.6 A.",
            (100 * G, 148 * G))
    u1 = (snap(162 * G), snap(168 * G))
    sh.part("U1", u1, 0, ref_at=(u1[0], u1[1] - 7.4 * G), val_at=(u1[0], u1[1] - 6 * G))
    for i, ref in enumerate(("L1", "C7", "C8", "C9", "C10")):
        row(sh, ref, 232 * G, 156 * G + i * P)
    for i, ref in enumerate(("R7", "R8", "R6", "C6")):
        row(sh, ref, 290 * G, 156 * G + i * P)

    # ---- power and test points ------------------------------------------------------
    sh.frame(232 * G, 82 * G, 318 * G, 132 * G, "3.3 V decoupling, test pads, power flags")
    for i, ref in enumerate(("C1", "C2", "C3")):
        row(sh, ref, 252 * G, 94 * G + i * P)
    sh.part("TP1", (snap(244 * G), snap(118 * G)), 0, ref_at=(snap(246 * G), snap(115 * G)),
            val_at=(snap(246 * G), snap(116.5 * G)))
    sh.part("TP2", (snap(262 * G), snap(118 * G)), 0, ref_at=(snap(264 * G), snap(115 * G)),
            val_at=(snap(264 * G), snap(116.5 * G)))
    sh.power(d.V33, (snap(288 * G), snap(98 * G)))
    sh.power(d.V18, (snap(288 * G), snap(112 * G)))
    sh.power(d.GND, (snap(288 * G), snap(120 * G)))

    sh.text("Design notes, pin maps and the layout rationale are in DESIGN.md.\n"
            "This sheet is generated: edit tools/msdx/design.py and re-run tools/build.sh,\n"
            "or edit here and stop using the generator (see DESIGN.md, 'Working on the design').",
            (12 * G, 176 * G))
    return sh


def main():
    sh = build()
    with open(OUT, "w") as f:
        f.write(sh.render())
    print("wrote", OUT)


if __name__ == "__main__":
    main()
