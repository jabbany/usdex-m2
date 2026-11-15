# Notes for coding agents

This is a hardware project: a microSD Express to M.2 2230 (Key M) adapter,
as a KiCad 7 project generated from Python.

Read `DESIGN.md` first. It has the pin maps, the coordinate frame, the reasons
behind the layout, what has and has not been verified, and the open issues.
Section 10 explains how to make changes.

## Commands

```
sh tools/build.sh         # regenerate hardware/ from tools/msdx/*.py and verify; must end "RESULT: PASS"
sh tools/export_docs.sh   # refresh docs/schematic.pdf, docs/img/*.png, docs/bom.csv
sh tools/export_fab.sh    # Gerbers, drill, placement into build/fab/
```

Needs KiCad 7 (`kicad-cli` and the `pcbnew` Python module). Tested with
7.0.11 only.

## Rules of the road

- `hardware/*.kicad_sch`, `*.kicad_pcb`, `*.kicad_pro`, `*.kicad_dru` and
  `hardware/lib/` are generated. Change `tools/msdx/design.py` (parts, nets,
  placement), `tools/msdx/geom.py` (dimensions) or `tools/msdx/layout.py`
  (copper), then run the build. Do not edit the generated files by hand
  unless the project has moved to hand-editing (DESIGN.md section 10, mode B).
- All coordinates are in the board frame: top view, fingers at the bottom,
  X = 0 on the centreline with +X toward pin 1, Y = 0 at the mounting-notch
  edge and 30 at the finger edge, millimetres. KiCad page coordinates are
  board coordinates + (100, 100). DRC reports use page coordinates.
- After a layout change, look at the result (`docs/img/top.png`,
  `L1_top.png`, `L4_bot.png`). A passing DRC does not mean the routing is
  sensible.
- Keep the invariants listed at the end of DESIGN.md section 10. If one has to
  change, change the matching limit in `tools/verify.py` in the same commit
  and record why in DESIGN.md.
- Do not claim more than was checked. The board has never been built;
  impedance is uncalculated; ERC has not been run (kicad-cli 7 cannot).
  Update DESIGN.md sections 7 and 9 when that changes.
- Commit the Python, `hardware/` and `docs/` together so they never disagree.
