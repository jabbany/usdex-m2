#!/bin/sh
# Plot Gerbers, drill files and a placement file into build/fab/.
# Read DESIGN.md section "Before ordering" first: the differential-pair
# geometry must be set from your fabricator's stackup before these are used.
set -e
cd "$(dirname "$0")/.."
P=hardware/msdx_m2_2230
O=build/fab
rm -rf $O && mkdir -p $O
kicad-cli pcb export gerbers -o $O/ \
  --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts" \
  --subtract-soldermask $P.kicad_pcb
kicad-cli pcb export drill -o $O/ --format excellon --excellon-separate-th \
  --generate-map --map-format gerberx2 $P.kicad_pcb
kicad-cli pcb export pos -o $O/msdx_m2_2230-pos.csv --format csv --units mm --side front $P.kicad_pcb
ls -1 $O
