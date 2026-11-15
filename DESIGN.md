# microSD Express to M.2 2230 (Key M) adapter: design notes

Revision A0, 2026-11-14. This file is the working reference for the design. It
records what the board is, why each choice was made, what has been checked and
how, and what is still open. Read it before changing anything, and update it in
the same commit as the change.

**Status: not built.** The schematic and layout exist, they agree with each
other, and the layout passes KiCad's DRC. Nothing here has been fabricated or
measured. Section 9 lists what must be done before ordering boards.

Contents

1. What the board does
2. Repository layout and build
3. Conventions (board frame, net names, reference designators)
4. Electrical design
5. Parts and footprints
6. PCB: outline, stackup, placement, routing
7. Verification: what is checked and what is not
8. Differences from the first design document
9. Open issues and the list to clear before ordering
10. Working on the design
11. Sources

---

## 1. What the board does

A microSD Express card is an NVMe SSD with a one-lane PCIe Gen3 interface on
its second row of contacts. An M.2 Key M slot offers the same lane, a 100 MHz
reference clock, PERST#, CLKREQ# and 3.3 V. The adapter wires one to the other
and adds the three things the slot does not provide:

- a 1.8 V supply for the card's VDD2 pin, brought up after 3.3 V;
- two AC-coupling capacitors on the card's transmit pair (the card has none);
- defined levels on the two legacy SD pins (CMD, CLK) that must not float.

There is no bridge chip and no firmware. The host sees an NVMe device.

```
 M.2 Key M edge (J1)                                   microSD Express socket (J2)
 PETp0/PETn0  49/47 ───────────────────────────────────── 11/12  Tx+/Tx-  (card receiver)
 PERp0/PERn0  43/41 ──────────────── C4/C5 220 nF ─────── 15/14  Rx+/Rx-  (card transmitter)
 REFCLKp/n    55/53 ─────────────────────────────────────  7/8   REFCLK+/-
 PERST#       50    ──────────────── R1 0R ──────────────  2     PERST#
 CLKREQ#      52    ──────────────── R2 0R ──────────────  1     CLKREQ#   (R3 10k pull-up, not fitted)
 3.3 V  2,4,12,14,16,18,70,72,74 ─┬──────────────────────  4     VDD1
                                  ├─ R4 47k ─────────────  3     CMD
                                  └─ U1 buck, 1.8 V ─────  9     VDD2      (EN delayed by R6/C6)
 GND                              ── R5 0R ──────────────  5     CLK
 pin 73 (GND / VIO_CFG) ── R9 0R ── GND                    17, DET: not connected
```

Constraints the design was built around:

- M.2 type 2230-S3: 22 x 30 mm, 0.8 mm thick, parts on the top side only, top
  height 1.5 mm. The bottom side carries copper and silkscreen only.
- The inserted card stays inside the 22 mm width.
- PCIe Gen3 (8 GT/s), 85 ohm differential pairs, no vias in the pairs.
- A four-layer board that a prototype fab can make, with parts that can be
  hand-soldered (no BGA, nothing smaller than 0402).

Not supported, on purpose: legacy SD/UHS cards (a PCIe-only host cannot talk to
them; they are not damaged, they just do not appear), hot-plug, more than one
lane, PCIe Gen4.

## 2. Repository layout and build

```
hardware/                      the KiCad project (open msdx_m2_2230.kicad_pro)
  msdx_m2_2230.kicad_sch       schematic, one A3 sheet
  msdx_m2_2230.kicad_pcb       board, 4 layers, routed, zones filled
  msdx_m2_2230.kicad_pro       net classes, design rules, DRC severities
  msdx_m2_2230.kicad_dru       custom rules (pair skew)
  sym-lib-table, fp-lib-table  point at lib/ through ${KIPRJMOD}
  lib/msdx.kicad_sym           project symbols: M.2 edge, socket
  lib/msdx.pretty/             project footprints: M.2 edge, socket, test pad
  lib/3d/                      put Amphenol's STEP model here (not included)
tools/
  msdx/design.py               parts, nets, placements: the source of truth
  msdx/geom.py                 every dimension: M.2 edge, socket, outline, trace widths
  msdx/layout.py               tracks, vias, zones, length matching
  msdx/symbols.py, sexp.py, netlist.py   helpers
  gen_lib.py, gen_sch.py, gen_pcb.py     write the files in hardware/
  verify.py                    checks schematic and board against design.py, runs DRC
  gen_bom.py                   writes docs/bom.csv
  build.sh                     gen_lib -> gen_sch -> netlist -> gen_pcb -> verify
  export_docs.sh               schematic PDF, layer images, BOM into docs/
  export_fab.sh                Gerbers, drill, placement into build/fab/
docs/                          generated reading copies and reports (committed)
build/                         scratch output (ignored by git)
```

The KiCad files in `hardware/` are generated from the Python in `tools/`. They
are ordinary KiCad files and can be opened, inspected and edited in KiCad, but
`tools/build.sh` overwrites the schematic, board, project file and library. See
section 10 for the two ways to work with that.

Requirements: KiCad 7 with `kicad-cli` and the `pcbnew` Python module, plus
KiCad's standard symbol and footprint libraries. Developed and tested with
KiCad 7.0.11 on Ubuntu 24.04 (`apt install kicad`) and with nothing else. The
library paths default to `/usr/share/kicad/symbols` and
`/usr/share/kicad/footprints`; set `KICAD7_SYMBOL_DIR` and
`KICAD7_FOOTPRINT_DIR` if yours differ. `export_docs.sh` also uses the Python
package `cairosvg` for PNG previews and skips them if it is missing.

```
sh tools/build.sh         # regenerate everything, then verify; prints PASS or the failures
sh tools/export_docs.sh   # refresh docs/schematic.pdf, docs/img/*.png, docs/bom.csv
sh tools/export_fab.sh    # Gerbers etc. into build/fab/ (read section 9 first)
```

The build is reproducible: running it twice gives byte-identical files, so a
`git diff` after a change shows only what the change did. The one exception is
`docs/schematic.pdf`, which carries its creation time and so differs after
every `export_docs.sh`.

The files are in KiCad 7 format. KiCad 8 and 9 open them and convert them on
save; after that KiCad 7 can no longer read them, and the generators have not
been run against the newer `pcbnew` API.

## 3. Conventions

**Board frame.** Every coordinate in this file, in `tools/` and in the comments
on the board uses one frame:

- top view, gold fingers at the bottom of the screen;
- X across the module, 0 on the centreline, +X toward M.2 pin 1 (the right);
- Y along the module, 0 at the edge with the mounting notch, 30 at the finger edge;
- millimetres.

KiCad page coordinates are board coordinates plus (100, 100). The board's
auxiliary origin is at the centre of the finger edge.

**Layers.** L1 = F.Cu (top), L2 = In1.Cu, L3 = In2.Cu, L4 = B.Cu (bottom).

**Net names.** `PCIE_*` nets are named from the host's side, as the M.2
specification does: `PCIE_TX` is driven by the host, `PCIE_RX` is received by
the host. `PCIE_RX_C_*` is the piece of the receive pair between the socket and
the AC capacitors. `SD_*` nets are on the card side of a series part. `_P`/`_N`
suffixes let KiCad treat the nets as differential pairs.

**Socket pad names.** The SD specification also names the card's lane from the
host's side: pads 11/12 "PCIe Tx" are the card's receiver, pads 14/15 "PCIe Rx"
are its transmitter.

## 4. Electrical design

### 4.1 Card contacts (SD 7.1 microSD, PCIe mode)

| Pad | PCIe mode | Net on the adapter | Connection |
|---|---|---|---|
| 1 | CLKREQ# (open drain) | SD_CLKREQ_N | R2 0R to M.2 pin 52; R3 10k to 3.3 V not fitted |
| 2 | PERST# | SD_PERST_N | R1 0R to M.2 pin 50 |
| 3 | CMD, unused, must not float | SD_CMD | R4 47k to 3.3 V |
| 4 | VDD1 3.3 V | +3V3 | M.2 3.3 V; C2 10 uF, C3 100 nF |
| 5 | CLK, unused, must not float | SD_CLK | R5 0R to GND |
| 6, 10, 13, 16 | VSS | GND | |
| 7 / 8 | REFCLK+ / REFCLK- | PCIE_REFCLK_P / _N | M.2 pins 55 / 53, direct |
| 9 | VDD2 1.8 V | +1V8 | buck output; C10 100 nF |
| 11 / 12 | Tx+ / Tx- (card receiver) | PCIE_TX_P / _N | M.2 pins 49 / 47, direct |
| 14 / 15 | Rx- / Rx+ (card transmitter) | PCIE_RX_C_N / _P | C5 / C4 220 nF, then M.2 pins 41 / 43 |
| 17 | VDD3 1.2 V, optional | none | not connected |
| DET | card-detect switch | none | not connected |
| shell | six solder tabs | GND | |

### 4.2 M.2 Key M pins

| Pins | Signal | Side | Use |
|---|---|---|---|
| 41 / 43 | PERn0 / PERp0 | top | PCIE_RX_N / _P |
| 47 / 49 | PETn0 / PETp0 | top | PCIE_TX_N / _P |
| 53 / 55 | REFCLKn / REFCLKp | top | PCIE_REFCLK_N / _P |
| 50 | PERST# | bottom | PCIE_PERST_N |
| 52 | CLKREQ# | bottom | PCIE_CLKREQ_N |
| 2, 4, 12, 14, 16, 18, 70, 72, 74 | 3.3 V | bottom | +3V3 |
| 1, 3, 9, 15, 21, 27, 33, 39, 45, 51, 57, 71, 75 | GND | top | GND |
| 73 | GND, or VIO_CFG on M.2 rev 4 hosts | top | R9 0R to GND: declares a 3.3 V-sideband module, as every older SSD does |
| 69 | PEDET | top | open (open means PCIe; SATA modules ground it) |
| all others | lanes 1-3, PWRDIS, PLN#, LED1#, VIO_1.8V, USB, DEVSLP, SMBus, PEWAKE#, MFG, SUSCLK | | finger pad only, no copper attached |

Positions 59 to 66 do not exist; the Key M slot takes their place.

The full pin-to-net assignment is `M2_NETS` and `SKT_NETS` in
`tools/msdx/design.py`. There are 21 nets and 38 intentionally unconnected pins
(36 on J1, 2 on J2).

### 4.3 The PCIe lane

- **Host to card** (`PCIE_TX`): a bare pair. The host has the AC capacitors on
  its transmitter, as PCIe requires; a second pair of capacitors here would
  only raise the high-pass corner.
- **Card to host** (`PCIE_RX_C` then `PCIE_RX`): C4 and C5, 220 nF, 0402, X7R.
  The SD Association's host guideline says the card has no capacitors on its
  transmitter and asks for 176 to 265 nF within 12.5 mm of the socket. The
  board has 7.6 mm of trace between the socket pads and the capacitors.
- **REFCLK**: DC-coupled, no termination on the adapter (the host
  source-terminates HCSL).
- **Polarity is preserved on all three pairs.** How the layout achieves that
  is in section 6.4.

### 4.4 Sideband and the legacy SD pins

- PERST# and CLKREQ# pass through 0R links R1 and R2. The links exist so that
  series resistance or a level translator can be fitted without a new board.
- R3 (10k from CLKREQ# to 3.3 V) is not fitted. M.2 hosts pull CLKREQ# up. Fit
  it for a host that does not.
- CMD is pulled up through R4 (47k) and CLK is tied to ground through R5 (0R).
  The SD 7.x pin table says these pins shall not be left open in PCIe mode.
  CLK matters most: the card chooses SD mode on the first clock edge it sees
  and PCIe mode when VDD2 appears with no clock, so a glitch coupled onto a
  floating CLK could leave the card in SD mode where the host never finds it.
  Both reference designs leave these pins open and work; this is margin.
- No level translation. On a 3.3 V-sideband host the card's pads 1 and 2 see
  3.3 V logic; on a 1.8 V-sideband host they see 1.8 V logic. The pads are the
  card's DAT2/DAT3 contacts, rated to VDD1 + 0.3 V because every SD card starts
  at 3.3 V signalling, so neither level can damage the card, and both exceed
  the 1.8 V-logic input-high threshold. Both reference designs run at 3.3 V.
  What the public documents do not give is the level section 8.2.4 of the SD
  Express specification assigns to these pins. See section 9.

### 4.5 Power

VDD1 is the M.2 3.3 V rail, passed through. VDD2 comes from U1, a TI TLV62568
(1 A synchronous buck, 1.5 MHz, SOT-23-5, 0.6 V reference):

| Part | Value | Role |
|---|---|---|
| L1 | 2.2 uH, 2016 size, Isat >= 1.5 A | from the datasheet's 1.8 V application |
| C7 | 4.7 uF 0603 | input, at the VIN pin |
| C8, C9 | 10 uF 0603, 4.7 uF 0402 | output |
| C10 | 100 nF 0402 | at the VDD2 trunk next to socket pad 9 |
| R7, R8 | 200k, 100k, 1 % | Vout = 0.6 V x (1 + 200/100) = 1.80 V |
| R6, C6 | 100k to 3.3 V, 220 nF to GND | enable delay: tau = 22 ms, EN crosses about 1 V roughly 8 ms after 3.3 V is up |
| C1, C2, C3 | 10 uF, 10 uF, 100 nF | 3.3 V bulk and VDD1 decoupling at socket pad 4 |

Why a buck and not the LDO one reference uses: at the card's sustained 0.4 A an
LDO dissipates (3.3 - 1.8) x 0.4 = 0.6 W beside a card that throttles when it
gets hot, and a SOT-223 is taller than the S3 height limit. The buck loses
under 0.1 W.

Card limits from the SD Association guideline: VDD1 2.7 to 3.6 V and VDD2 1.70
to 1.95 V, each 400 mA sustained and 600 mA peak, 1.8 W for the card.

Sequence: 3.3 V arrives, VDD1 is up at once, EN rises about 8 ms later and VDD2
follows; the host holds PERST# low for at least 100 ms after power is good, so
the card sees VDD1, then VDD2, then PERST# release.

C9 is 4.7 uF in 0402 instead of a second 10 uF in 0603 because that is what
fits between L1 and the socket's shield tab without overlapping courtyards.
The effective output capacitance after DC bias has not been calculated against
the TLV62568 stability requirement. See section 9.

## 5. Parts and footprints

Bill of materials: `docs/bom.csv`, generated from `design.py`.

| Ref | Part | Footprint | Where the footprint comes from |
|---|---|---|---|
| J1 | M.2 Key M edge, 67 gold fingers + mounting pads | `msdx:M2_2230_KeyM_Edge` | generated, section 5.1 |
| J2 | Amphenol 10102166A812A | `msdx:Amphenol_10102166A812A` | generated, section 5.2 |
| U1 | TI TLV62568DBVR | `Package_TO_SOT_SMD:SOT-23-5` | KiCad library |
| L1 | 2.2 uH 2016, e.g. Murata DFE201612E-2R2M | `Inductor_SMD:L_Murata_DFE201610P` | KiCad library, section 5.3 |
| C1, C2, C7, C8 | 0603 capacitors | `Capacitor_SMD:C_0603_1608Metric` | KiCad library |
| C3 to C6, C9, C10 | 0402 capacitors | `Capacitor_SMD:C_0402_1005Metric` | KiCad library |
| R1 to R9 | 0402 resistors | `Resistor_SMD:R_0402_1005Metric` | KiCad library |
| TP1, TP2 | bare copper pads, 3V3 and 1V8 | `msdx:TestPad_D0.8mm` | generated: 0.8 mm round pad |

Heights against the 1.5 mm limit: socket 1.55 mm per Amphenol (1.50 in their
3D model), SOT-23-5 up to 1.45, inductor 1.2, 0603 capacitors up to about 0.95,
0402 parts about 0.55. The socket is nominally 0.05 mm over. See section 9.

The library footprints are copied into the board file by KiCad as usual. The
board uses KiCad's nominal-density land patterns; nothing was shrunk.

### 5.1 J1, the M.2 card edge

Dimensions are in `geom.py` (`M2_*`) and come from the PCI Express M.2
specification's module drawings as reproduced in connector vendors' drawings,
cross-checked against the Key M edge footprint in M1cha/sdexpress_pcbs, which
is on a board that works.

| Feature | Value |
|---|---|
| Board | 22.0 x 30.0 mm, 0.8 mm thick |
| Tongue | 19.85 mm wide, 4.0 mm long, 0.6 mm inside radius at the shoulders |
| Pin pitch | 0.5 mm on each side, the two sides offset by 0.25 mm |
| Pin X | odd pin n (top): 9.25 - 0.25 (n - 1); even pin n (bottom): 9.0 - 0.25 (n - 2) |
| Fingers | 0.35 mm wide; top fingers end 2.0 mm from the edge, bottom 2.5 mm; they start 0.45 mm from the edge (the specification allows up to 0.55) |
| Key M | positions 59 to 66 removed; slot 1.2 mm wide, 3.5 mm deep, centred at X = -6.125 |
| Mounting notch | half circle, R 1.75, centred on the far edge at X = 0 |
| Mounting pads | half rings to 5.5 mm diameter on top and 6.0 mm on the bottom, clipped 0.4 mm inside the board edge, net GND, pad name MP |
| Component keep-out | no top-side parts within 4.0 mm of the finger edge (drawn as the footprint's courtyard) |

The fingers are SMD pads of type "connect" (no paste), with solder-mask
openings. The footprint has no outline of its own on Edge.Cuts; the board
outline is drawn by `gen_pcb.py` from `geom.outline()`, and the footprint
carries a copy on Dwgs.User for reference.

Not in the footprint: the 20 degree edge chamfer (a fabrication option; the
board's stackup is flagged "edge connector: bevelled") and hard-gold plating
(also a fabrication option).

### 5.2 J2, the socket

The footprint was derived from three sources that agree: the footprints in the
two reference repositories, which were drawn independently and are on working
boards, and the solder tails in Amphenol's STEP model. Amphenol's dimensioned
drawing could not be read during the design work, so the recommended land
pattern in the drawing has **not** been compared directly. See section 9.

Footprint frame: origin at the centre of the land pattern; card inserted from
+y toward -y.

| Feature | Footprint coordinates (mm) |
|---|---|
| Row 1 (closed end), y = -7.0, 1.1 mm pitch | pads 1 to 8 at x = 3.76, 2.66, 1.56, 0.46, -0.64, -1.74, -2.84, -3.94; DET at -5.04 |
| Row 2 (card mouth), y = +7.0, 0.91 mm pitch | 9 at x = 3.72, 17 at 2.57, then 10 to 16 at 1.66, 0.75, -0.16, -1.07, -1.98, -2.89, -3.80 |
| Signal pads | 0.7 x 1.2 mm |
| Shield tabs | six pads 1.1 x 2.1 mm at x = +-6.85, y = -6.15, 1.05, 6.55; pad name SH |
| Shell | x -6.75 to 6.75, y -7.05 to 7.6 |
| Inserted card | x -4.94 to 6.06, y -5.0 to 10.0; its underside is 0.55 mm above the board |
| Contact-tip keep-out | x -4.45 to 4.0, y 1.6 to 3.8, top copper |

Findings from slicing the STEP model at several heights, which shaped the
layout:

- The plastic floor of the socket starts about 0.25 mm above the board. Tracks
  and vias under the body are clear of it.
- **The free ends of the nine row-2 contact springs come down to the board
  surface** in a strip at x -4.16 to 3.71, y 1.9 to 3.5. Copper there could be
  touched by a contact. The footprint carries a keep-out zone (no tracks, no
  vias, no pour on F.Cu) over that strip plus margin, so any board that uses
  the footprint inherits it. This is a reading of a 3D model, not of a
  drawing; check it on a real part.
- The courtyard is extended over the card's tail, so DRC objects to a part
  placed where the card slides.

The 3D model is not included because it is Amphenol's. Download
`10102166A812A.step` from the product page and put it in `hardware/lib/3d/`;
the footprint already points there, with the offset the model needs
(y = -7.6 mm).

### 5.3 L1

KiCad has no footprint named for the 1.2 mm-high DFE201612E. The board uses the
library's `L_Murata_DFE201610P` pattern, which is the land pattern for the same
2.0 x 1.6 mm body in its 1.0 mm-high version. Compare it with the datasheet of
the inductor you actually buy.

## 6. PCB

Images: `docs/img/top.png` (top copper and parts), `L1_top.png`, `L2_gnd.png`,
`L3_gnd.png`, `L4_bot.png`, `assembly.png`, `bottom_silk.png`.

### 6.1 Outline

`geom.outline()`: the 22 x 30 mm M.2 outline with the tongue, the Key M slot
and the mounting notch, plus one addition: a notch 7.0 mm long and 1.1 mm deep
in the right-hand edge (Y 10.44 to 17.44), centred on the card, with 0.5 mm
inside radii. The card's tail lies over it, so a fingernail can get under the
card to pull it out. `geom.outline(notch=False)` gives the plain outline.

### 6.2 Stackup

| Layer | Use | Entered in the board file |
|---|---|---|
| L1 | all parts, the three differential pairs, power trunks, GND pour | 35 um copper |
| | prepreg | 0.0994 mm, type 3313, er 4.1 |
| L2 | GND plane, the reference for everything on L1 | 15.2 um |
| | core | 0.4708 mm |
| L3 | GND plane, the reference for L4 | 15.2 um |
| | prepreg | 0.0994 mm, 3313 |
| L4 | 3.3 V pour, PERST#, CLKREQ#, the 1.8 V sense trace; no parts | 35 um |

Total 0.80 mm with solder mask. The numbers are meant to match JLCPCB's
JLC04081H-3313 stackup and must be confirmed against the fabricator's current
table.

**The pair geometry is a placeholder.** 0.16 mm traces with a 0.15 mm gap were
chosen for 85 ohm differential on this stackup. A hand calculation with the
IPC-2141 microstrip formulas gives about 85 ohm, but those formulas are known
to be off by 10 % or more for thin dielectrics. Take the width and gap from the
fabricator's impedance calculator, put them in `geom.DP_W` and `geom.DP_GAP`,
rebuild, and order with impedance control. The reference 6-layer board used
0.205/0.203 mm on a different prepreg.

### 6.3 Placement

Parts and their positions are the `PARTS` list in `design.py`. Everything is on
the top side.

| Item | Board coordinates |
|---|---|
| Socket J2 | origin (0.7, 14.5), rotated 90 degrees so the card mouth faces +X |
| Socket shell | X -6.35 to 8.3, Y 7.75 to 21.25 |
| Row 1 pads (1 to 8, DET) | X = -6.3; pad 1 at Y 10.74, pad 8 at 18.44, DET at 19.54 |
| Row 2 pads (9, 17, 10 to 16) | X = 7.7; pad 9 at Y 10.78, pad 16 at 18.30 |
| Shield tabs | X = -5.45, 1.75, 7.25 at Y = 7.65 and 21.35 |
| Inserted card | X -4.3 to 10.7, Y 8.44 to 19.44; the tail ends 0.3 mm inside the board edge |
| Contact-tip keep-out | X 2.3 to 4.5, Y 10.5 to 18.95 |
| Buck (U1, L1, C7 to C10, R6 to R8, C6) | top-right corner, between the mounting notch, the right edge and the socket |
| 3.3 V bulk (C1, C2), TP1 | top-left |
| Row-1 passives (R1 to R5, C3) | left margin at X = -8.2, each level with its socket pad |
| AC capacitors C4, C5 | (8.8, 23.2) and (9.8, 23.2), vertical, in the right margin below the card |
| R9 | (-9.4, 24.9) |

**Why the card goes in from the side.** Lengthwise insertion from the far end
runs into the mounting screw: the screw head and standoff take a 6 mm circle on
the centre of that edge, the card is 11 mm wide, and moving the socket sideways
far enough to pass the screw puts its body off the board. Across the board, the
socket's 14.65 mm body and the card's 2.4 mm tail fit inside the 22 mm width.
The cost is that the card is inserted and removed from the pin-1 side of the
module, which needs about 15 mm of free space there, or the module has to come
out of the slot to change the card.

### 6.4 Routing

All of it is in `tools/msdx/layout.py`, as lists of points in the board frame.

**The rule that sets the topology.** At the M.2 edge the positive finger of
each pair is the one further toward -X (pins 49, 43 and 55), so for a pair
travelling away from the fingers the positive trace is always on the left of
the direction of travel. A pair that reaches a pad column travelling in +X
therefore lands its positive trace on the pad with the smaller Y, and a pair
travelling in -X lands it on the pad with the larger Y. The socket's pad order
then decides the approach direction for each pair, if polarity is to be kept
and no pair is to cross another:

| Pair | Socket pads, smaller Y first | Must arrive travelling | So it is routed |
|---|---|---|---|
| TX | 11 Tx+ (13.75), 12 Tx- (14.66) | +X | from inside the socket footprint |
| RX | 14 Rx- (16.48), 15 Rx+ (17.39) | -X | from the card-mouth side, down the right margin |
| REFCLK | 7 + (17.34), 8 - (18.44) | +X | from the left margin, outside the socket |

The paths:

- **TX** (24.1 mm): from fingers 49/47 up to Y = 23.9, east below the socket,
  north at X = 5.155 between the two lower-right shield tabs (X 1.75 and 7.25)
  and east of the contact-tip keep-out (which ends at X = 4.5), then east into
  pads 11/12. The last 9 mm run under the socket floor.
- **RX** (7.6 mm socket to capacitors, 14.9 mm capacitors to fingers): out of
  pads 15/14 toward the mouth, south down the right margin on a lane at
  X = 9.3, through C4/C5, west along Y = 25.3, into fingers 43/41.
- **REFCLK** (16.6 mm): from fingers 55/53 west along Y = 25.155, north up the
  left margin at X = -8.3, east into pads 7/8.
- All three are on L1 only, with no vias, over unbroken L2 ground. Bends are
  45 degrees. Each pair is length-matched with small trapezoidal bumps on the
  shorter trace (`layout.match`); the skew is 0.000 mm on every segment as
  drawn. The custom rules allow 0.15 mm.
- **PERST#, CLKREQ#** leave bottom-side fingers 50/52 on L4, run north at
  X = -3.0 and -3.5, turn west at Y = 8.6 and 8.9 (above socket row 1), go
  down the far-left edge and come up through vias to R1 and R2.
- **3.3 V**: L4 is a 3.3 V pour fed by the nine bottom-side fingers. The two
  sideband traces cut that pour into a left part (fed by fingers 70, 72, 74)
  and a right part (fed by the other six). A 0.4 mm track on L1 near C2 and R3
  joins the two parts so the net is one piece.
- **1.8 V**: L1 only, 0.5 mm, from L1/C8 down the right margin to socket pad 9.
  The feedback divider senses the output through a separate trace on L4 from a
  via near C9, away from the switch node. TP2 is on that sense line.
- **Ground**: pours on L1 (0.35 mm clearance to everything else, thermal
  reliefs), solid planes on L2 and L3. Vias at the regulator, at each
  capacitor's ground pad, at five of the six shield tabs (the sixth shares
  C9's), beside ground fingers 39, 45 and 57, and stitching vias along the
  three pairs, around the board and under the socket floor (`STITCH` in
  `layout.py`). 63 vias in all, 0.5/0.3 mm and 0.45/0.3 mm.
- **Finger area**: the pours and planes stop 2.25 to 2.8 mm short of the finger
  edge, so there is no inner-layer copper under the fingers. Short stubs take
  each power and ground finger into its pour.

### 6.5 Design rules

In `msdx_m2_2230.kicad_pro` and `.kicad_dru`, written by `gen_pcb.py`:

| Rule | Value |
|---|---|
| Minimum clearance / track width | 0.127 mm |
| Default net class | 0.15 mm track, 0.15 mm clearance, via 0.5/0.3 mm |
| `PCIe_85R` class (the eight pair nets) | 0.16 mm track, 0.15 mm gap |
| `Power` class (+3V3, +1V8, BUCK_SW) | 0.4 mm track |
| Copper to board edge | 0.3 mm |
| Minimum via | 0.45 mm pad, 0.3 mm hole |
| Hole clearance | 0.2 mm |
| Intra-pair skew, each of TX, RX, RX_C, REFCLK | 0.15 mm maximum |

These are within JLCPCB's published 4-layer capabilities as understood when
the rules were written; check them against the fabricator you use.

## 7. Verification

`tools/verify.py` runs at the end of every build and writes
`docs/verification.txt` and `docs/drc_report.txt`. The current result is PASS.

Checked:

1. **Schematic against `design.py`.** The netlist KiCad exports from the
   schematic has the same 25 parts, the same 21 nets with the same pins on
   each, the same 38 open pins and the same footprint assignments.
2. **Board against `design.py`.** Every one of the 140 pads carries the net
   `design.py` gives it; every part is where `design.py` puts it, on the top
   side.
3. **Geometry**, measured on the board file with limits written into
   `verify.py` as literals: finger positions and sides for 14 pins against the
   M.2 formula, 67 fingers, none in the key, outline 22 x 30 mm, card inside
   the board width, no top-layer track or via in the contact-tip keep-out,
   pair skew at most 0.15 mm, pairs on L1 only at the pair width with no vias,
   AC capacitors within 12.5 mm of the socket pads.
4. **KiCad DRC** through `pcbnew.WriteDRCReport`, with the project's rules:
   0 violations, 0 unconnected pads, 0 footprint errors. This covers
   clearances, edge clearance, courtyard overlaps, the keep-out zone, the skew
   rules and connectivity.

Not checked:

- **KiCad ERC has not been run.** `kicad-cli` in KiCad 7 has no ERC command.
  Check 1 covers connectivity; it does not cover pin-type conflicts or missing
  power flags. Run ERC once in the schematic editor.
- **Impedance.** No field solver was used (section 6.2).
- **The socket land pattern against Amphenol's drawing** (section 5.2).
- **Anything electrical or mechanical on a real board.**
- The generators have been run only with KiCad 7.0.11.

Checks 1 and 2 compare the files with the Python description they were
generated from, so they catch generator bugs and stale files, not design
errors. A wrong pin assignment in `design.py` passes all four checks. The pin
tables in section 4 are the place to review the design itself.

## 8. Differences from the first design document

The design document written before the layout (2026-10-06) is superseded by
this file where they differ:

| Topic | First document | This board | Why |
|---|---|---|---|
| RX pair polarity | P and N swapped, relying on the host's polarity inversion | preserved | RX is routed to the card-mouth side of the pads, which lands it the right way round (section 6.4). No pair depends on polarity inversion. |
| TX and RX paths | both pairs enter between the lower shield tabs | TX enters there; RX leaves at the mouth and runs down the right margin | the STEP model showed contact springs touching the board in the middle of the socket; and two pairs entering together cannot both keep polarity without crossing |
| AC capacitors | below the socket at X 3 to 6 | right margin, (8.8, 23.2) and (9.8, 23.2) | they follow the RX path |
| Socket position | X = 1.0 | X = 0.7 | keeps the card tail 0.3 mm inside the edge |
| Edge notch | 7 x 2 mm | 7 x 1.1 mm | leaves room for the 1.8 V trunk and the RX pair beside row 2 |
| 1.8 V to pad 9 | on L4 under the socket | on L1 down the right margin | shorter, and keeps L4 for 3.3 V |
| PERST#, CLKREQ# | vias inside the socket footprint | around the top-left of the socket to R1/R2 in the left margin | keeps vias out from under the contacts |
| C9 | 10 uF 0603 | 4.7 uF 0402 | space |
| Designators | R7a, R7b, R8; TP1 to TP4 | R7, R8 (divider), R9 (pin 73); TP1 = 3V3, TP2 = 1V8 | |
| Test points on VDD3 and DET | yes | none; the pads are left unconnected | no free area that is clear of the card |
| Skew limit | 0.125 mm | 0.15 mm in the rules, 0.000 mm as drawn | |

Unchanged: the circuit, every value except C9, the socket, the regulator, the
stackup, the reasoning for CMD/CLK and for the buck.

## 9. Open issues and the list to clear before ordering

Before ordering:

1. **Set the pair geometry from the fabricator's calculator** (`geom.DP_W`,
   `geom.DP_GAP`), rebuild, confirm DRC still passes, and order with impedance
   control. A wider pair needs more room in two tight places: between the
   fingers and the first bend, and beside the notch corner at about (9.5, 17.5),
   where the RX pair is 0.50 mm from the board edge.
2. **Compare the J2 footprint with Amphenol's drawing**: pad positions and
   sizes, pad numbering (above all 11/12 and 14/15), and whether the contact
   springs do reach the board where the keep-out assumes.
3. **Run ERC** in the KiCad schematic editor.
4. **Confirm the stackup numbers** and the minimum track, gap, via and
   edge-clearance values against the fabricator.
5. **Check the buck's output capacitance** (C8 10 uF + C9 4.7 uF + C10 100 nF,
   derated for 1.8 V bias) against the TLV62568 datasheet's minimum, and the EN
   threshold and soft-start time against the 8 ms estimate. If more
   capacitance is needed, the simplest change is a 22 uF 0603 for C8.
6. **Measure a socket** and check 1.55 mm against the target host's SSD bay.
7. **Read the generated Gerbers** in a viewer: finger pads on both sides with
   mask openings, no inner copper under the fingers, the outline with both
   notches and the key.
8. Choose fabrication options: 0.8 mm, 4 layers, ENIG (hard gold on the
   fingers if offered), 20 degree bevel if offered, outline tolerance +-0.1 mm.

Known weaknesses of rev A0:

- **Sideband level.** Unconfirmed against the SD Express specification
  (section 4.4). R1 and R2 are the place for a fix.
- **TX runs 9 mm under the socket body**, between its floor and the L2 plane.
  The floor is plastic 0.25 mm above the trace, which will lower the pair's
  impedance slightly along that stretch. Not modelled.
- **RX crosses the gap between the card mouth and the capacitors beside the
  card's tail**, 0.55 mm below the card. Same remark.
- **The L4 3.3 V pour is in two parts** joined by one 0.4 mm top-layer track.
  Each part has its own fingers, so the join carries little current, but it is
  a single track. A second join or moving the sideband to L1 would be cleaner.
- **Finger 51 (GND, between TX and REFCLK) has no via of its own.** It joins
  the L1 pour, which reaches the planes through the stitching via at
  (-4.4, 24.3). The L4 sideband traces pass directly beneath where a via would
  go.
- **No ESD protection, no PWRDIS support, no activity LED, no card-detect.**
  DET is unconnected; it could gate the buck's EN.
- **R3 is marked do-not-populate in the schematic only.** KiCad 7's board API
  has no such flag, so on the board R3 has the value "10k DNP" and appears in
  the placement file. Remove it by hand from an assembly order.
- **The schematic is generated** and connects everything through global labels
  rather than drawn wires. It is correct and readable, not pretty.
- **Card access is from the side** (section 6.3).

Bring-up order, when there is a board: continuity of every finger against
section 4; 3.3 V applied with no card, check 1.80 V on TP2 and that it rises a
few milliseconds after TP1; then a card in a USB-to-NVMe M.2 enclosure before a
motherboard slot; then `lspci -vv` (expect 8 GT/s, width x1), `nvme list`, a
clean `dmesg`, and a test with ASPM enabled, which is the only time CLKREQ#
matters.

## 10. Working on the design

There are two ways to work, and they do not mix.

**A. Change the Python, regenerate.** This is how rev A0 was made and it is the
way that suits a coding agent: every part, net, coordinate and track is text,
the build takes two seconds, and `verify.py` says whether the result still
holds together.

1. Edit `tools/msdx/design.py` (parts, nets, placement), `geom.py`
   (dimensions) or `layout.py` (copper).
2. `sh tools/build.sh`. It must end with `RESULT: PASS`. DRC messages are in
   `docs/drc_report.txt`, with KiCad page coordinates; subtract (100, 100) for
   the board frame.
3. `sh tools/export_docs.sh` and look at `docs/img/top.png` and the layer
   images. DRC does not see a route that is legal but silly.
4. Update this file, and commit the Python, `hardware/` and `docs/` together.

Anything edited by hand in KiCad is lost at the next build.

**B. Edit in KiCad.** Open `hardware/msdx_m2_2230.kicad_pro` and work as in any
KiCad project. From the first hand edit, stop running `gen_sch.py` and
`gen_pcb.py` (delete them, or the whole of `build.sh`, to make that hard to do
by accident). `gen_lib.py` can stay as the source of the two footprints.
`verify.py` still runs on a hand-edited board: parts 3 and 4 are independent of
the generators; parts 1 and 2 keep comparing against `design.py`, which is
useful as long as `design.py` is kept in step and should be removed otherwise.

Moving to B is a one-way step. It is the right step once the layout needs
interactive routing, for example after the pair geometry changes enough that
the hand-placed lanes in `layout.py` no longer fit.

### How the generator is organised

- `design.py` holds `PARTS`: reference, value, symbol, footprint, position,
  rotation, and a pad-to-net dictionary for each part. Nets exist only as
  those dictionary values. `nets()` and `unconnected_pins()` derive the rest.
- `gen_sch.py` places each symbol on the sheet and attaches a global label, a
  power symbol or a no-connect flag to every pin according to `design.py`.
  Symbol positions on the sheet are in `build()` in that file.
- `kicad-cli` exports the netlist from the schematic. `gen_pcb.py` reads it
  for the net list and for each symbol's UUID, which goes into the footprint
  as its schematic link. That is what "Update PCB from Schematic" matches on;
  the update has not been tried in the KiCad GUI.
- `layout.py` builds the copper. `pad(ref, name)` returns a pad centre in the
  board frame; `offset_path` makes the two traces of a pair from a centre
  line; `match` adds the length-matching bumps; `Layout.track` and
  `Layout.via` collect the result. Lane positions are literal numbers with
  comments.
- `gen_pcb.py` creates the board through the `pcbnew` API, fills the zones,
  saves, and then rewrites item UUIDs and item order so the output is
  reproducible (`normalise`).

### Recipes

- **New pair width or gap**: `DP_W`, `DP_GAP` in `geom.py`. The pair pitch
  follows. Rebuild and look at the finger fan-out and the two tight places
  named in section 9.
- **Move a part**: change `pos` (and `rot`) in `design.py`. Tracks that end on
  its pads follow, because routes ask `pad()` for coordinates, but bends and
  lanes in between are literal and may need to move too.
- **Add a part**: add it to `PARTS`; give it a place on the sheet in
  `gen_sch.build()`; route it in `layout.py`. If it is missing from the
  schematic, `verify.py` reports a component-set mismatch; if it is unrouted,
  DRC reports unconnected pads.
- **Change a net**: edit the pad dictionaries in `design.py`. Net names in
  `layout.py` are strings and must be changed to match.
- **No edge notch, or a different one**: `NOTCH_*` in `geom.py`, or
  `outline(notch=False)` where `gen_pcb.py` draws the outline.
- **Shift the socket**: `SKT_POS` in `geom.py`. Pad-relative routes follow;
  the TX entry lane (X = 5.155), the right-margin lane (X = 9.3) and the
  left-margin lane (X = -8.3) are literals in `layout.py`.
- **A different socket**: new footprint function in `gen_lib.py`, new `SKT_*`
  block in `geom.py`, and re-derive the approach directions with the rule in
  section 6.4.

### Things that must stay true

- No copper on L1 in the contact-tip keep-out, and no parts under the card.
- No vias in TX, RX or REFCLK, and unbroken L2 under them.
- AC capacitors only on the card-to-host pair, within 12.5 mm of pads 14/15.
- CLK (pad 5) tied low, CMD (pad 3) pulled up; neither floating.
- Nothing on the bottom side but copper, mask and silkscreen.
- No top-side part within 4 mm of the finger edge or taller than 1.5 mm.
- M.2 pin 69 open, pin 73 to ground.
- The inserted card inside the board outline (X <= 11).

`verify.py` enforces most of these. If a change needs one of them relaxed,
change the literal limit in `verify.py` in the same commit and say why here.

## 11. Sources

- SD Association, *SD Express (SD7.x to SD8.0) Host Implementation Guideline*:
  adapter topology, AC-capacitor value and distance, power limits.
  https://www.sdcard.org/cms/wp-content/uploads/2020/11/SD_Express_Design_Guide.pdf
- microSD 7.1 card datasheet reproducing the SD 7.1 pad table, including "shall
  not be kept open" for CMD and CLK. https://www.farnell.com/datasheets/4475774.pdf
- vapetrov/microSD_express_Pi (MIT): flex adapter for the Raspberry Pi 5; socket
  footprint cross-checked. https://github.com/vapetrov/microSD_express_Pi
- M1cha/sdexpress_pcbs (no licence file; nothing copied): M.2 2280 adapter;
  socket and Key M footprints cross-checked. https://github.com/M1cha/sdexpress_pcbs
  and the write-up https://mzimmermann.info/posts/a-microsd-express-card-in-an-m2-slot/
- Amphenol 10102166A812A product page and STEP model.
  https://www.amphenol-cs.com/product/10102166a812a.html
- TI TLV62568 datasheet. https://www.ti.com/lit/gpn/TLV62568
- JLCPCB impedance stackups and capabilities.
  https://jlcpcb.com/quote/pcbOrderFaq/PCB%20Stackup and https://jlcpcb.com/capabilities/
- M.2 connector drawing with the module dimension tables (heights, 2230 outline,
  chamfer). https://static.chipdip.ru/lib/623/DOC041623345.pdf
- PCI Express M.2 Key M devicetree binding discussion, for VIO_CFG and 1.8 V
  sideband. https://lkml.iu.edu/2512.3/02274.html
