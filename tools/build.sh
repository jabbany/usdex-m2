#!/bin/sh
# Regenerate the library, schematic and PCB from tools/msdx/*.py, then verify.
# Needs KiCad 7 (kicad-cli and the pcbnew Python module) plus the standard
# KiCad symbol and footprint libraries.
set -e
cd "$(dirname "$0")/.."
mkdir -p build
python3 tools/gen_lib.py
python3 tools/gen_sch.py
kicad-cli sch export netlist -o build/msdx_m2_2230.net hardware/msdx_m2_2230.kicad_sch
python3 tools/gen_pcb.py build/msdx_m2_2230.net
python3 tools/verify.py
