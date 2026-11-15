#!/usr/bin/env python3
"""Write docs/bom.csv from tools/msdx/design.py (grouped by value and footprint)."""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msdx import design as d  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "bom.csv")


def refkey(r):
    m = re.match(r"([A-Z]+)(\d+)", r)
    return (m.group(1), int(m.group(2)))


def main():
    groups = {}
    for p in d.PARTS:
        if p["ref"] in ("J1",) or p["ref"].startswith("TP"):
            continue                      # PCB features, nothing to buy or place
        key = (p["value"], p["fp"], p["mpn"], p["dnp"])
        groups.setdefault(key, []).append(p)
    rows = []
    for (value, fp, mpn, dnp), parts in groups.items():
        refs = sorted((p["ref"] for p in parts), key=refkey)
        rows.append(dict(refs=refs, value=value, fp=fp.split(":")[1], mpn=mpn,
                         fit="DNP" if dnp else "fit",
                         desc="; ".join(dict.fromkeys(p["desc"] for p in parts))))
    rows.sort(key=lambda r: refkey(r["refs"][0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Refs", "Qty", "Value", "Footprint", "Fit", "MPN (suggested)", "Notes"])
        for r in rows:
            w.writerow([" ".join(r["refs"]), len(r["refs"]), r["value"], r["fp"], r["fit"], r["mpn"], r["desc"]])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
