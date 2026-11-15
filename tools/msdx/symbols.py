"""Schematic symbols: the two project-specific ones are generated here, the
generic ones (R, C, L, regulator, power flags) are copied out of the KiCad
standard libraries so the schematic can embed them.
"""
import os

from . import design as d
from . import geom as g
from .sexp import dump, find, first, parse_file, q, unq

KICAD_SYMBOL_DIR = os.environ.get("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")

_FONT = "(effects (font (size 1.27 1.27)))"
_HIDE = "(effects (font (size 1.27 1.27)) hide)"


def _pin(number, name, x, y, ang, etype="passive", length=2.54):
    return (f'(pin {etype} line (at {x:g} {y:g} {ang}) (length {length:g}) '
            f'(name {q(name)} {_FONT}) (number {q(number)} {_FONT}))')


def _symbol(name, ref, footprint, datasheet, descr, keywords, half_w, half_h, pins, lib=None):
    """pins: list of (number, name, x, y, angle)."""
    full = f"{lib}:{name}" if lib else name
    body = [
        f'(symbol {q(full)} (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
        f'  (property "Reference" {q(ref)} (at {-half_w:g} {half_h + 1.27:g} 0) '
        f'(effects (font (size 1.27 1.27)) (justify left)))',
        f'  (property "Value" {q(name)} (at {-half_w:g} {-half_h - 1.27:g} 0) '
        f'(effects (font (size 1.27 1.27)) (justify left)))',
        f'  (property "Footprint" {q(footprint)} (at 0 0 0) {_HIDE})',
        f'  (property "Datasheet" {q(datasheet)} (at 0 0 0) {_HIDE})',
        f'  (property "ki_keywords" {q(keywords)} (at 0 0 0) {_HIDE})',
        f'  (property "ki_description" {q(descr)} (at 0 0 0) {_HIDE})',
        f'  (symbol {q(name + "_0_1")}',
        f'    (rectangle (start {-half_w:g} {half_h:g}) (end {half_w:g} {-half_h:g}) '
        f'(stroke (width 0.254) (type default)) (fill (type background)))',
        '  )',
        f'  (symbol {q(name + "_1_1")}',
    ]
    for p in pins:
        body.append("    " + _pin(*p))
    body += ["  )", ")"]
    return "\n".join(body)


def m2_edge_symbol(lib=None):
    odd = [n for n in g.m2_pins() if n % 2]
    even = [n for n in g.m2_pins() if not n % 2]
    rows = max(len(odd), len(even) + 1)
    half_h = rows * 2.54 / 2 + 1.27
    half_w = 17.78
    top = (rows - 1) * 2.54 / 2
    pins = []
    for i, n in enumerate(odd):
        pins.append((str(n), d.M2_PIN_NAMES[n], -half_w - 2.54, top - 2.54 * i, 0))
    for i, n in enumerate(even):
        pins.append((str(n), d.M2_PIN_NAMES[n], half_w + 2.54, top - 2.54 * i, 180))
    pins.append(("MP", "MOUNT_GND", half_w + 2.54, top - 2.54 * len(even), 180))
    return _symbol(
        "M2_KeyM_2230_Edge", "J", "msdx:M2_2230_KeyM_Edge",
        "https://pcisig.com/specifications",
        "M.2 socket 3 (Key M) module card edge, type 2230. Odd pins top side, even pins "
        "bottom side; names from the host's point of view (PET = host transmit).",
        "M.2 NGFF Key M card edge PCIe NVMe", half_w, half_h, pins, lib)


def socket_symbol(lib=None):
    left = ["1", "2", "3", "4", "5", "6", "7", "8", "DET"]
    right = ["9", "17", "10", "11", "12", "13", "14", "15", "16", "SH"]
    rows = max(len(left), len(right))
    half_h = rows * 2.54 / 2 + 1.27
    half_w = 15.24
    top = (rows - 1) * 2.54 / 2
    pins = [(n, d.SKT_PIN_NAMES[n], -half_w - 2.54, top - 2.54 * i, 0) for i, n in enumerate(left)]
    pins += [(n, d.SKT_PIN_NAMES[n], half_w + 2.54, top - 2.54 * i, 180) for i, n in enumerate(right)]
    return _symbol(
        "microSD_Express_Socket", "J", "msdx:Amphenol_10102166A812A",
        "https://www.amphenol-cs.com/product/10102166a812a.html",
        "microSD Express (SD 7.1) card socket; pin names give SD mode / PCIe mode function. "
        "Tx/Rx are named from the host: Tx = card input, Rx = card output.",
        "microSD Express SD7.1 PCIe card socket", half_w, half_h, pins, lib)


def project_library():
    return ("(kicad_symbol_lib (version 20220914) (generator msdx_gen)\n"
            + _indent(m2_edge_symbol()) + "\n" + _indent(socket_symbol()) + "\n)\n")


def _indent(text, n=2):
    return "\n".join(" " * n + line for line in text.split("\n"))


# --------------------------------------------------------------------------
# Standard-library symbols
# --------------------------------------------------------------------------
_cache = {}


def _lib(libname):
    if libname not in _cache:
        _cache[libname] = parse_file(os.path.join(KICAD_SYMBOL_DIR, libname + ".kicad_sym"))
    return _cache[libname]


def std_symbol_tree(lib_id):
    """Parsed (symbol ...) node of a standard-library symbol, renamed to its
    full lib_id as an embedded schematic symbol must be."""
    libname, name = lib_id.split(":")
    for s in find(_lib(libname), "symbol"):
        if unq(s[1]) == name:
            if first(s, "extends"):
                raise ValueError(f"{lib_id} is a derived symbol; flatten it first")
            node = list(s)
            node[1] = q(lib_id)
            return node
    raise KeyError(lib_id)


def embedded_symbol(lib_id):
    """Text of the symbol definition to place in a schematic's lib_symbols."""
    if lib_id == "msdx:M2_KeyM_2230_Edge":
        return m2_edge_symbol("msdx")
    if lib_id == "msdx:microSD_Express_Socket":
        return socket_symbol("msdx")
    return dump(std_symbol_tree(lib_id))


def symbol_pins(lib_id):
    """pin number -> (x, y, angle, name) in symbol coordinates (Y up)."""
    from .sexp import parse
    tree = parse(embedded_symbol(lib_id))
    out = {}
    for sub in find(tree, "symbol"):
        for p in find(sub, "pin"):
            at = first(p, "at")
            out[unq(first(p, "number")[1])] = (
                float(at[1]), float(at[2]), int(float(at[3])), unq(first(p, "name")[1]))
    return out
