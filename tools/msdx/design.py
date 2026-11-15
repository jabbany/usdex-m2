"""The design: every part, every pin-to-net assignment, every placement.

This file is the single source of truth. gen_sch.py draws the schematic from
it, gen_pcb.py builds the board from it, verify.py checks both against it.
Positions are in the board frame defined in geom.py.
"""
from . import geom as g

PROJECT = "msdx_m2_2230"
TITLE = "microSD Express to M.2 2230 (Key M) adapter"
REV = "A0"
DATE = "2026-11-14"

GND, V33, V18 = "GND", "+3V3", "+1V8"

# --------------------------------------------------------------------------
# J1: M.2 Key M card edge (signal names as the M.2 spec gives them, i.e. from
# the host's point of view: PET = host transmits, PER = host receives)
# --------------------------------------------------------------------------
M2_PIN_NAMES = {
    1: "GND", 2: "3.3V", 3: "GND", 4: "3.3V", 5: "PERn3", 6: "PWRDIS", 7: "PERp3",
    8: "PLN#", 9: "GND", 10: "LED1#/DAS", 11: "PETn3", 12: "3.3V", 13: "PETp3",
    14: "3.3V", 15: "GND", 16: "3.3V", 17: "PERn2", 18: "3.3V", 19: "PERp2",
    20: "NC", 21: "GND", 22: "VIO_1.8V", 23: "PETn2", 24: "NC", 25: "PETp2",
    26: "NC", 27: "GND", 28: "NC", 29: "PERn1", 30: "PLA_S3#", 31: "PERp1",
    32: "NC", 33: "GND", 34: "USB_D+", 35: "PETn1", 36: "USB_D-", 37: "PETp1",
    38: "DEVSLP", 39: "GND", 40: "SMB_CLK", 41: "PERn0", 42: "SMB_DATA",
    43: "PERp0", 44: "ALERT#", 45: "GND", 46: "NC", 47: "PETn0", 48: "NC",
    49: "PETp0", 50: "PERST#", 51: "GND", 52: "CLKREQ#", 53: "REFCLKn",
    54: "PEWAKE#", 55: "REFCLKp", 56: "MFG_DATA", 57: "GND", 58: "MFG_CLOCK",
    67: "NC", 68: "SUSCLK", 69: "PEDET", 70: "3.3V", 71: "GND", 72: "3.3V",
    73: "VIO_CFG/GND", 74: "3.3V", 75: "GND",
}

M2_NETS = {n: GND for n in (1, 3, 9, 15, 21, 27, 33, 39, 45, 51, 57, 71, 75)}
M2_NETS.update({n: V33 for n in (2, 4, 12, 14, 16, 18, 70, 72, 74)})
M2_NETS.update({
    41: "PCIE_RX_N",        # PERn0: host receive, card transmit, after AC cap
    43: "PCIE_RX_P",
    47: "PCIE_TX_N",        # PETn0: host transmit, card receive
    49: "PCIE_TX_P",
    53: "PCIE_REFCLK_N",
    55: "PCIE_REFCLK_P",
    50: "PCIE_PERST_N",
    52: "PCIE_CLKREQ_N",
    73: "M2_PIN73",
})

# --------------------------------------------------------------------------
# J2: microSD Express socket (SD 7.1 microSD pad assignment, PCIe mode)
# --------------------------------------------------------------------------
SKT_PIN_NAMES = {
    "1": "DAT2/CLKREQ#", "2": "DAT3/PERST#", "3": "CMD", "4": "VDD1", "5": "CLK",
    "6": "VSS", "7": "DAT0/REFCLK+", "8": "DAT1/REFCLK-", "9": "VDD2", "10": "VSS",
    "11": "PCIe_Tx+", "12": "PCIe_Tx-", "13": "VSS", "14": "PCIe_Rx-",
    "15": "PCIe_Rx+", "16": "VSS", "17": "VDD3", "DET": "DET", "SH": "SHIELD",
}
SKT_NETS = {
    "1": "SD_CLKREQ_N", "2": "SD_PERST_N", "3": "SD_CMD", "4": V33, "5": "SD_CLK",
    "6": GND, "7": "PCIE_REFCLK_P", "8": "PCIE_REFCLK_N", "9": V18, "10": GND,
    "11": "PCIE_TX_P", "12": "PCIE_TX_N", "13": GND, "14": "PCIE_RX_C_N",
    "15": "PCIE_RX_C_P", "16": GND, "SH": GND,
    # "17" (VDD3, 1.2 V, optional) and "DET" are left unconnected
}

# --------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"

ROW_X = -8.2   # centre of the 0402s lined up with socket row 1


def _p(ref, value, sym, fp, pos, rot, pins, desc="", mpn="", dnp=False, group=""):
    return dict(ref=ref, value=value, sym=sym, fp=fp, pos=pos, rot=rot, pins=pins,
                desc=desc, mpn=mpn, dnp=dnp, group=group)


def _row(name):
    return g.skt_pad(name)[1]


PARTS = [
    _p("J1", "M.2 Key M 2230 edge", "msdx:M2_KeyM_2230_Edge", "msdx:M2_2230_KeyM_Edge",
       (0, g.BOARD_L), 0,
       {**{str(n): M2_NETS[n] for n in M2_NETS}, "MP": GND},
       desc="M.2 socket-3 card edge, PCB gold fingers, plus mounting-notch ground pads",
       group="m2"),
    _p("J2", "10102166A812A", "msdx:microSD_Express_Socket", "msdx:Amphenol_10102166A812A",
       g.SKT_POS, g.SKT_ROT, dict(SKT_NETS),
       desc="microSD Express socket, 3-in-1, push-pull, card detect, 1.55 mm",
       mpn="Amphenol 10102166A812A", group="socket"),

    # --- 1.8 V buck ---------------------------------------------------------
    _p("U1", "TLV62568DBV", "Regulator_Switching:TLV62568DBV", "Package_TO_SOT_SMD:SOT-23-5",
       (5.0, 3.4), 90,
       {"1": "BUCK_EN", "2": GND, "3": "BUCK_SW", "4": V33, "5": "BUCK_FB"},
       desc="1 A synchronous buck, 1.5 MHz, 0.6 V feedback", mpn="TI TLV62568DBVR", group="buck"),
    _p("L1", "2.2uH", "Device:L", "Inductor_SMD:L_Murata_DFE201610P",
       (8.0, 4.2), 0, {"1": "BUCK_SW", "2": V18},
       desc="2.2 uH, 2016, Isat >= 1.5 A, <= 1.2 mm high", mpn="Murata DFE201612E-2R2M=P2",
       group="buck"),
    _p("C7", "4.7uF", "Device:C", C0603, (8.2, 2.35), 0, {"1": V33, "2": GND},
       desc="buck input, X5R 6.3 V", group="buck"),
    _p("C8", "10uF", "Device:C", C0603, (10.0, 4.6), 90, {"1": V18, "2": GND},
       desc="buck output, X5R 6.3 V", group="buck"),
    _p("C9", "4.7uF", "Device:C", C0402, (7.9, 6.05), 0, {"1": GND, "2": V18},
       desc="buck output, second capacitor, X5R 6.3 V (0402)", group="buck"),
    _p("C10", "100nF", "Device:C", C0402, (9.6, 7.65), 0, {"1": GND, "2": V18},
       desc="VDD2 decoupling toward socket pin 9, X7R", group="buck"),
    _p("R7", "200k", "Device:R", R0402, (6.5, 0.8), 0, {"1": "BUCK_FB", "2": V18},
       desc="feedback divider top, 1 %", group="buck"),
    _p("R8", "100k", "Device:R", R0402, (4.6, 0.8), 0, {"1": GND, "2": "BUCK_FB"},
       desc="feedback divider bottom, 1 %", group="buck"),
    _p("R6", "100k", "Device:R", R0402, (2.17, 5.6), 0, {"1": V33, "2": "BUCK_EN"},
       desc="EN pull-up; with C6 delays VDD2 about 8 ms after VDD1", group="buck"),
    _p("C6", "220nF", "Device:C", C0402, (2.2, 4.55), 0, {"1": GND, "2": "BUCK_EN"},
       desc="EN delay", group="buck"),

    # --- 3.3 V bulk -----------------------------------------------------------
    _p("C1", "10uF", "Device:C", C0603, (-8.9, 3.4), 0, {"1": GND, "2": V33},
       desc="3.3 V bulk, X5R 6.3 V", group="power"),
    _p("C2", "10uF", "Device:C", C0603, (-8.9, 5.9), 0, {"1": GND, "2": V33},
       desc="VDD1 bulk, X5R 6.3 V", group="power"),
    _p("C3", "100nF", "Device:C", C0402, (ROW_X, _row("4")), 0, {"1": GND, "2": V33},
       desc="VDD1 decoupling at socket pin 4, X7R", group="socket"),

    # --- PCIe lane --------------------------------------------------------------
    _p("C4", "220nF", "Device:C", C0402, (8.8, 23.2), 90,
       {"1": "PCIE_RX_P", "2": "PCIE_RX_C_P"},
       desc="AC coupling, card Rx+ to host PERp0, X7R 10 %", group="pcie"),
    _p("C5", "220nF", "Device:C", C0402, (9.8, 23.2), 90,
       {"1": "PCIE_RX_N", "2": "PCIE_RX_C_N"},
       desc="AC coupling, card Rx- to host PERn0, X7R 10 %", group="pcie"),

    # --- sideband and legacy SD pins --------------------------------------------
    _p("R1", "0R", "Device:R", R0402, (ROW_X, _row("2")), 0,
       {"1": "PCIE_PERST_N", "2": "SD_PERST_N"},
       desc="PERST# series link (33-100 R optional)", group="sideband"),
    _p("R2", "0R", "Device:R", R0402, (ROW_X, _row("1")), 0,
       {"1": "PCIE_CLKREQ_N", "2": "SD_CLKREQ_N"},
       desc="CLKREQ# series link", group="sideband"),
    _p("R3", "10k", "Device:R", R0402, (ROW_X, _row("1") - 1.1), 0,
       {"1": "PCIE_CLKREQ_N", "2": V33},
       desc="CLKREQ# pull-up, fit only if the host has none", dnp=True, group="sideband"),
    _p("R4", "47k", "Device:R", R0402, (ROW_X, _row("3")), 0, {"1": V33, "2": "SD_CMD"},
       desc="CMD pull-up (must not float in PCIe mode)", group="sideband"),
    _p("R5", "0R", "Device:R", R0402, (ROW_X, _row("5")), 0, {"1": GND, "2": "SD_CLK"},
       desc="CLK held low (must not float; an edge selects SD mode)", group="sideband"),
    _p("R9", "0R", "Device:R", R0402, (-9.4, 24.9), 90, {"1": "M2_PIN73", "2": GND},
       desc="M.2 pin 73 (GND / VIO_CFG) to ground, legacy 3.3 V sideband module",
       group="sideband"),

    # --- test points ----------------------------------------------------------------
    _p("TP1", "3V3", "Connector:TestPoint", "msdx:TestPad_D0.8mm",
       (-5.6, 4.6), 0, {"1": V33}, desc="test pad", group="power"),
    _p("TP2", "1V8", "Connector:TestPoint", "msdx:TestPad_D0.8mm",
       (10.2, 0.85), 0, {"1": V18}, desc="test pad on the feedback sense line",
       group="buck"),
]

BY_REF = {p["ref"]: p for p in PARTS}


def nets():
    """net name -> sorted list of (ref, pad)."""
    out = {}
    for p in PARTS:
        for pad, net in p["pins"].items():
            out.setdefault(net, []).append((p["ref"], pad))
    return {k: sorted(v) for k, v in sorted(out.items())}


def unconnected_pins():
    """(ref, pad) pairs intentionally left open."""
    out = [("J1", str(n)) for n in g.m2_pins() if n not in M2_NETS]
    out += [("J2", "17"), ("J2", "DET")]
    return out


# Net classes: name -> (track width, clearance, [net name patterns])
NETCLASSES = {
    "PCIe_85R": dict(width=g.DP_W, gap=g.DP_GAP, clearance=0.15,
                     nets=["PCIE_TX_P", "PCIE_TX_N", "PCIE_RX_P", "PCIE_RX_N",
                           "PCIE_RX_C_P", "PCIE_RX_C_N", "PCIE_REFCLK_P", "PCIE_REFCLK_N"]),
    "Power": dict(width=0.4, gap=0.2, clearance=0.15, nets=[V33, V18, "BUCK_SW"]),
}

DIFF_PAIRS = {
    "TX": ("PCIE_TX_P", "PCIE_TX_N"),
    "RX": ("PCIE_RX_P", "PCIE_RX_N"),
    "RXC": ("PCIE_RX_C_P", "PCIE_RX_C_N"),
    "REFCLK": ("PCIE_REFCLK_P", "PCIE_REFCLK_N"),
}
