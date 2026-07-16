"""
Daily hardware calibration of a reference cell (procedure section 5.3,
eqs. (4)-(11)): determination of Vr, V_LIN and V_D from the two-disc
procedure.
"""

from datetime import datetime

from .constants import (
    DEFAULT_CAL_UNCERTAINTIES,
    DEFAULT_TOLERANCES,
    FACTORY_CELLS,
)
from .errors import InputError
from .physics import expansion_ratio, reference_pressure
from .uncertainty import propagate


def calibrate_cell(cell_input, R, tolerances, offset=0.0,
                   uncertainties=DEFAULT_CAL_UNCERTAINTIES):
    """
    Daily determination of Vr, V_LIN and V_D for one reference cell
    (manual sections 3.5 and 4.5-4.6).

    Measurements: P_DV with the matrix cup completely filled with calibration
    discs, P1 with disc set 1 removed, P2 with disc set 2 removed.  V1, V2
    are the corresponding known removed-disc volumes from the disc table
    (Annex A, section 4.3); V0 is the void volume at P_DV (0 for a full cup).
    """
    name = cell_input.get("cell", "?")
    try:
        p = cell_input["pressures"]
        P_DV, P1, P2 = float(p["P_DV"]), float(p["P1"]), float(p["P2"])
        v = cell_input["disc_volumes_cm3"]
        V1, V2 = float(v["V1"]), float(v["V2"])
        V0 = float(v.get("V0", 0.0))
    except (KeyError, TypeError, ValueError):
        raise InputError(
            'Cell "%s": needs "pressures" {P_DV, P1, P2} and '
            '"disc_volumes_cm3" {V1, V2, optional V0}.' % name)

    def solve(v):
        x0 = expansion_ratio(R, v["P_DV"], offset)
        x1 = expansion_ratio(R, v["P1"], offset)
        x2 = expansion_ratio(R, v["P2"], offset)
        # Subtracting eq. (4) from (5) and (4) from (6) gives the linear
        # system (7)-(8):  dV1 = A*Vr + B*V_LIN ;  dV2 = C*Vr + D*V_LIN
        A, B = x1 - x0, x1 * x1 - x0 * x0
        C, D = x2 - x0, x2 * x2 - x0 * x0
        dV1, dV2 = v["V1"] - v["V0"], v["V2"] - v["V0"]
        det = A * D - B * C
        if abs(det) < 1e-12:
            raise InputError(
                'Cell "%s": the three pressures are too close together, the '
                "calibration system is singular." % name)
        Vr = (D * dV1 - B * dV2) / det                 # eq. (9)
        V_LIN = (C * dV1 - A * dV2) / (C * B - D * A)  # eq. (10)
        V_D = Vr * x0 + V_LIN * x0 * x0 - v["V0"]      # eq. (11), general V0
        return {"Vr": Vr, "V_LIN": V_LIN, "V_D": V_D}

    vals = {"P_DV": P_DV, "P1": P1, "P2": P2, "V0": V0, "V1": V1, "V2": V2}
    nominal = solve(vals)
    Vr, V_LIN, V_D = nominal["Vr"], nominal["V_LIN"], nominal["V_D"]

    u_p = float(uncertainties["pressure"])
    u_v = float(uncertainties["disc_volume_cm3"])
    u_in = {"P_DV": u_p, "P1": u_p, "P2": u_p,
            "V0": u_v if V0 else 0.0, "V1": u_v, "V2": u_v}
    u_out, sens = propagate(solve, vals, u_in, nominal)
    cov = sum(d.get("Vr", 0.0) * d.get("V_LIN", 0.0)
              for d in sens.values())

    warnings = []
    if Vr <= 0:
        warnings.append("Computed Vr is not positive - check the input data.")

    factory = FACTORY_CELLS.get(name)
    deviation = None
    if factory is not None:
        dev_Vr = 100.0 * (Vr - factory["Vr"]) / factory["Vr"]
        dev_VL = 100.0 * (V_LIN - factory["V_LIN"]) / factory["V_LIN"]
        deviation = {
            "factory_Vr_cm3": factory["Vr"],
            "factory_V_LIN_cm3": factory["V_LIN"],
            "Vr_deviation_pct": round(dev_Vr, 3),
            "V_LIN_deviation_pct": round(dev_VL, 3),
        }
        if abs(dev_Vr) > tolerances["Vr_pct"]:
            warnings.append(
                "Vr deviates %.2f%% from the factory value (tolerance %.1f%%): "
                "suspect a leak or temperature drift - run diagnostics before "
                "measuring." % (dev_Vr, tolerances["Vr_pct"]))
        if abs(dev_VL) > tolerances["V_LIN_pct"]:
            warnings.append(
                "V_LIN deviates %.2f%% from the factory value (tolerance "
                "%.1f%%): verify barometric/temperature stability."
                % (dev_VL, tolerances["V_LIN_pct"]))

    return {
        "cell": name,
        "R": R,
        "Vr_cm3": round(Vr, 6),
        "V_LIN_cm3": round(V_LIN, 6),
        "V_D_cm3": round(V_D, 6),
        "uncertainty": {
            "u_Vr_cm3": round(u_out["Vr"], 6),
            "u_V_LIN_cm3": round(u_out["V_LIN"], 6),
            "u_V_D_cm3": round(u_out["V_D"], 6),
            "cov_Vr_V_LIN": cov,
            "inputs_1sigma": {"pressure": u_p, "disc_volume_cm3": u_v},
        },
        "inputs": {
            "pressures": {"P_DV": P_DV, "P1": P1, "P2": P2},
            "disc_volumes_cm3": {"V0": V0, "V1": V1, "V2": V2},
        },
        "factory_comparison": deviation,
        "warnings": warnings,
    }


def run_calibration(data):
    offset = float(data.get("meter_offset", 0.0))
    R = reference_pressure(data.get("reference_pressure", {}), offset)
    tolerances = dict(DEFAULT_TOLERANCES)
    tolerances.update(data.get("tolerances", {}))
    uncertainties = dict(DEFAULT_CAL_UNCERTAINTIES)
    uncertainties.update(data.get("uncertainties", {}))

    cells = data.get("cells")
    if not cells:
        raise InputError('Calibration input needs a non-empty "cells" list.')

    results = [calibrate_cell(cell, R, tolerances, offset, uncertainties)
               for cell in cells]
    return {
        "type": "calibration_result",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": data.get("meta", {}),
        "R": R,
        "meter_offset": offset,
        "cells": results,
    }
