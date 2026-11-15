"""Read a KiCad netlist (kicad-cli sch export netlist) into plain dicts."""
from .sexp import find, first, parse_file, unq


def read(path):
    tree = parse_file(path)
    comps = {}
    for c in find(first(tree, "components"), "comp"):
        ref = unq(first(c, "ref")[1])
        comps[ref] = dict(
            value=unq(first(c, "value")[1]),
            footprint=unq(first(c, "footprint")[1]) if first(c, "footprint") else "",
            tstamp=unq(first(c, "tstamps")[1]),
            sheetpath=unq(first(first(c, "sheetpath"), "tstamps")[1]),
        )
    nets = {}
    for net in find(first(tree, "nets"), "net"):
        name = unq(first(net, "name")[1])
        nets[name] = sorted((unq(first(nd, "ref")[1]), unq(first(nd, "pin")[1])) for nd in find(net, "node"))
    return comps, nets


def pad_nets(nets):
    """(ref, pad) -> net name."""
    return {node: name for name, nodes in nets.items() for node in nodes}
