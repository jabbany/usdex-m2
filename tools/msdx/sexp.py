"""Minimal S-expression reader/writer for KiCad files.

Atoms are kept as raw tokens (quoted strings keep their quotes), so a parsed
tree can be written back without changing how KiCad reads it.
"""
import re
import uuid

_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')

# Fixed namespace so regenerated files keep the same UUIDs (stable diffs, and
# the schematic <-> PCB links survive a regeneration).
_NS = uuid.UUID("6d736478-2d6d-322d-3232-33302d726576")


def uid(*key):
    """Deterministic UUID derived from a key."""
    return str(uuid.uuid5(_NS, "/".join(str(k) for k in key)))


def parse(text):
    toks = _TOK.findall(text)

    def rd(i):
        i += 1
        out = []
        while toks[i] != ")":
            if toks[i] == "(":
                sub, i = rd(i)
                out.append(sub)
            else:
                out.append(toks[i])
                i += 1
        return out, i + 1

    return rd(0)[0]


def parse_file(path):
    with open(path, encoding="utf-8") as f:
        return parse(f.read())


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


def unq(tok):
    if isinstance(tok, str) and len(tok) >= 2 and tok[0] == '"':
        return tok[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return tok


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def num(v):
    """Format a number the way KiCad does (no trailing zeros, no -0)."""
    if isinstance(v, str):
        return v
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def dump(node, indent=0, width=110):
    """Pretty-print a parsed tree."""
    flat = _flat(node)
    if len(flat) + indent <= width or all(not isinstance(c, list) for c in node):
        return flat
    pad = " " * (indent + 2)
    parts = ["(" + str(node[0])]
    i = 1
    while i < len(node) and not isinstance(node[i], list):
        parts[0] += " " + str(node[i])
        i += 1
    for c in node[i:]:
        parts.append(pad + (dump(c, indent + 2, width) if isinstance(c, list) else str(c)))
    return "\n".join(parts) + "\n" + " " * indent + ")"


def _flat(node):
    return "(" + " ".join(_flat(c) if isinstance(c, list) else str(c) for c in node) + ")"
