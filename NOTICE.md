# Third-party material

**No licence has been chosen for this project yet.** Until one is added, the
default is "all rights reserved", which is probably not what you want for a
shared hardware design. Common choices are CERN-OHL-P/W/S v2 for the hardware
and MIT or Apache-2.0 for the scripts in `tools/`.

What this repository contains that came from elsewhere:

- **KiCad libraries.** The schematic embeds symbols from KiCad's standard
  symbol library (`Device`, `Regulator_Switching`, `Connector`, `power`), and
  the board embeds standard footprints (`Resistor_SMD`, `Capacitor_SMD`,
  `Inductor_SMD`, `Package_TO_SOT_SMD`). The KiCad libraries are licensed
  CC-BY-SA 4.0 with an exception that lets them be used in a design without
  the licence extending to the design. https://www.kicad.org/libraries/license/
- **vapetrov/microSD_express_Pi** (MIT, Copyright (c) the repository's
  author). Pad coordinates of the Amphenol socket in `tools/msdx/geom.py` were
  cross-checked against the footprint in that repository. No file was copied.
  https://github.com/vapetrov/microSD_express_Pi
- **M1cha/sdexpress_pcbs** has no licence file. Its footprints were read to
  cross-check dimensions; nothing from it is included.
  https://github.com/M1cha/sdexpress_pcbs
- **Amphenol's STEP model** of the 10102166A812A was measured to derive the
  socket outline, card position and keep-out. The model itself is not
  included; see `hardware/lib/3d/README.md`.

Trademarks: SD, microSD and SD Express are trademarks of SD-3C LLC; M.2 and PCI
Express are trademarks of PCI-SIG. This is an independent hobby design and has
not been through any compliance or logo programme.
