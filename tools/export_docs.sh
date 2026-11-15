#!/bin/sh
# Export the reading copies kept in docs/: schematic PDF, one SVG per copper
# layer, an assembly view, and the BOM. PNG previews are made as well when
# the Python package cairosvg is installed (used by README.md).
set -e
cd "$(dirname "$0")/.."
P=hardware/msdx_m2_2230
mkdir -p docs/img build/svg
kicad-cli sch export pdf -o docs/schematic.pdf $P.kicad_sch >/dev/null
svg() { # name, layers
  kicad-cli pcb export svg -o "build/svg/$1.svg" --layers "$2" --page-size-mode 2 \
    --exclude-drawing-sheet $3 $P.kicad_pcb >/dev/null
}
svg top      "F.Cu,F.Mask,F.Fab,Edge.Cuts"
svg L1_top   "F.Cu,Edge.Cuts"   --black-and-white
svg L2_gnd   "In1.Cu,Edge.Cuts" --black-and-white
svg L3_gnd   "In2.Cu,Edge.Cuts" --black-and-white
svg L4_bot   "B.Cu,Edge.Cuts"   --black-and-white
svg assembly "F.Fab,F.Paste,Edge.Cuts" --black-and-white
svg bottom_silk "B.SilkS,B.Mask,Edge.Cuts" "--black-and-white --mirror"
python3 tools/gen_bom.py
python3 - <<'PY' || echo "cairosvg not available: PNG previews not updated"
import cairosvg, glob, os
for f in sorted(glob.glob("build/svg/*.svg")):
    out = "docs/img/" + os.path.basename(f)[:-4] + ".png"
    cairosvg.svg2png(url=f, write_to=out, output_width=1100, background_color="white")
    print("wrote", out)
PY
