"""
Daily hardware calibration of a reference cell (procedure section 5.3,
eqs. (4)-(11)): determination of Vr, V_LIN and V_D.

Every calibration configuration i obeys the base equation

    V_i = Vr*x_i + V_LIN*x_i^2 - V_D ,   x_i = (R - P_i) / P_i

where P_i is the equilibrium pressure and V_i the void volume in the matrix
cup for that configuration.  Three unknowns (Vr, V_LIN, V_D) are determined
from three or more configurations by an ordinary linear least-squares fit;
with exactly three points the fit is exact and reproduces the manual's
closed-form two-disc solution (eqs. (9)-(11)).
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


def _solve3(A, b):
    """
    Solve the 3x3 linear system A x = b by Gauss elimination with partial
    pivoting.  Returns the solution list, or None if A is singular.
    """
    M = [list(A[i]) + [b[i]] for i in range(3)]
    scale = max((abs(v) for row in A for v in row), default=0.0)
    tol = 1e-12 * scale if scale else 1e-12
    for c in range(3):
        piv = max(range(c, 3), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) <= tol:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [val / pv for val in M[c]]
        for r in range(3):
            if r != c:
                f = M[r][c]
                M[r] = [M[r][k] - f * M[c][k] for k in range(4)]
    return [M[i][3] for i in range(3)]


def _fit_two_disc(xs, ys, name):
    """
    Exact closed-form solution for the classic three-point (two-disc)
    calibration, eqs. (9)-(11) of the manual.  Kept as a distinct path from
    the general least-squares fit so the legacy input reproduces the original
    tool bit-for-bit (the two agree to rounding, but the raw covariance is
    sensitive to arithmetic order).
    """
    x0, x1, x2 = xs
    V0, V1, V2 = ys
    # Subtracting eq. (4) from (5) and (4) from (6) gives the linear system
    # (7)-(8):  dV1 = A*Vr + B*V_LIN ;  dV2 = C*Vr + D*V_LIN
    A, B = x1 - x0, x1 * x1 - x0 * x0
    C, D = x2 - x0, x2 * x2 - x0 * x0
    dV1, dV2 = V1 - V0, V2 - V0
    det = A * D - B * C
    if abs(det) < 1e-12:
        raise InputError(
            'Cell "%s": the three pressures are too close together, the '
            "calibration system is singular." % name)
    Vr = (D * dV1 - B * dV2) / det                 # eq. (9)
    V_LIN = (C * dV1 - A * dV2) / (C * B - D * A)  # eq. (10)
    V_D = Vr * x0 + V_LIN * x0 * x0 - V0           # eq. (11), general V0
    return [Vr, V_LIN, V_D]


def _fit_curve(xs, ys, name):
    """
    Least-squares fit of [Vr, V_LIN, V_D] to the base equation
    V = Vr*x + V_LIN*x^2 - V_D over the expansion ratios `xs` and void
    volumes `ys` (design row a = [x, x^2, -1]).
    """
    ATA = [[0.0] * 3 for _ in range(3)]
    ATy = [0.0] * 3
    for x, y in zip(xs, ys):
        a = (x, x * x, -1.0)
        for i in range(3):
            ATy[i] += a[i] * y
            for j in range(3):
                ATA[i][j] += a[i] * a[j]
    sol = _solve3(ATA, ATy)
    if sol is None:
        raise InputError(
            'Cell "%s": the calibration pressures do not span enough '
            "distinct expansion ratios - the fit is singular (need at least "
            "three configurations at clearly different pressures)." % name)
    return sol


def _parse_configs(cell_input, name):
    """
    Return (configs, source) where configs is a list of (P, V) tuples -
    equilibrium pressure and matrix-cup void volume - accepting either the
    general "configurations" list or the legacy two-disc shape.

    Legacy: "pressures" {P_DV, P1, P2} + "disc_volumes_cm3" {V1, V2, opt V0}.
    General: "configurations" [{"P": ..., "V": ...}, ...], three or more
    points, where V is the total void volume in the cup at that pressure
    (0 for the completely filled cup, the removed-disc volume otherwise).
    """
    if "configurations" in cell_input:
        raw = cell_input["configurations"]
        if not isinstance(raw, list) or len(raw) < 3:
            raise InputError(
                'Cell "%s": "configurations" must be a list of at least '
                "three {P, V} points." % name)
        configs = []
        try:
            for c in raw:
                configs.append((float(c["P"]), float(c["V"])))
        except (KeyError, TypeError, ValueError):
            raise InputError(
                'Cell "%s": each configuration needs a numeric "P" '
                '(equilibrium pressure) and "V" (void volume in cm3).' % name)
        return configs, "configurations"
    try:
        p = cell_input["pressures"]
        P_DV, P1, P2 = float(p["P_DV"]), float(p["P1"]), float(p["P2"])
        v = cell_input["disc_volumes_cm3"]
        V1, V2 = float(v["V1"]), float(v["V2"])
        V0 = float(v.get("V0", 0.0))
    except (KeyError, TypeError, ValueError):
        raise InputError(
            'Cell "%s": needs "configurations" [{P, V}, ...] (three or more '
            'points) or the legacy "pressures" {P_DV, P1, P2} + '
            '"disc_volumes_cm3" {V1, V2, optional V0}.' % name)
    return [(P_DV, V0), (P1, V1), (P2, V2)], "legacy"


def calibrate_cell(cell_input, R, tolerances, offset=0.0,
                   uncertainties=DEFAULT_CAL_UNCERTAINTIES):
    """
    Daily determination of Vr, V_LIN and V_D for one reference cell
    (manual sections 3.5 and 4.5-4.6) from three or more configurations.

    The classic two-disc procedure (P_DV with the matrix cup completely
    filled with calibration discs, P1/P2 with disc set 1/2 removed) is the
    three-point special case; extra configurations at further pressures make
    the fit over-determined and let residuals flag a bad reading.
    """
    name = cell_input.get("cell", "?")
    configs, source = _parse_configs(cell_input, name)
    n = len(configs)

    # Flatten to a per-reading dict so the GUM propagation can perturb each
    # pressure and void volume independently.
    vals = {}
    for i, (P, V) in enumerate(configs):
        vals["P%d" % i] = P
        vals["V%d" % i] = V

    # The legacy three-point shape uses the exact closed form; extra
    # configurations are fitted by least squares.
    fit = _fit_two_disc if source == "legacy" else _fit_curve

    def solve(v):
        xs = [expansion_ratio(R, v["P%d" % i], offset) for i in range(n)]
        ys = [v["V%d" % i] for i in range(n)]
        Vr, V_LIN, V_D = fit(xs, ys, name)
        return {"Vr": Vr, "V_LIN": V_LIN, "V_D": V_D}

    nominal = solve(vals)
    Vr, V_LIN, V_D = nominal["Vr"], nominal["V_LIN"], nominal["V_D"]

    u_p = float(uncertainties["pressure"])
    u_v = float(uncertainties["disc_volume_cm3"])
    # A completely filled cup (V == 0) is a defined reference with no disc
    # volume, hence no disc-table uncertainty (matches the legacy V0 rule).
    u_in = {}
    for i, (P, V) in enumerate(configs):
        u_in["P%d" % i] = u_p
        u_in["V%d" % i] = u_v if V else 0.0
    u_out, sens = propagate(solve, vals, u_in, nominal)
    cov = sum(d.get("Vr", 0.0) * d.get("V_LIN", 0.0)
              for d in sens.values())

    # Fit residuals (predicted minus measured void volume) at each point.
    residuals = []
    for P, V in configs:
        x = expansion_ratio(R, P, offset)
        residuals.append((Vr * x + V_LIN * x * x - V_D) - V)
    max_res = max((abs(r) for r in residuals), default=0.0)
    rms_res = (sum(r * r for r in residuals) / n) ** 0.5

    warnings = []
    if Vr <= 0:
        warnings.append("Computed Vr is not positive - check the input data.")
    res_tol_pct = float(tolerances.get("fit_residual_pct",
                                       DEFAULT_TOLERANCES["fit_residual_pct"]))
    if Vr > 0 and 100.0 * max_res / Vr > res_tol_pct:
        warnings.append(
            "A calibration point deviates %.3f cm3 (%.2f%% of Vr) from the "
            "fitted curve (tolerance %.1f%%): suspect a misread pressure or "
            "wrong void volume - check the configurations."
            % (max_res, 100.0 * max_res / Vr, res_tol_pct))

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

    if source == "legacy":
        (P_DV, V0), (P1, V1), (P2, V2) = configs
        inputs = {
            "pressures": {"P_DV": P_DV, "P1": P1, "P2": P2},
            "disc_volumes_cm3": {"V0": V0, "V1": V1, "V2": V2},
        }
    else:
        inputs = {"configurations": [{"P": P, "V": V} for P, V in configs]}

    result = {
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
        "inputs": inputs,
        "factory_comparison": deviation,
        "warnings": warnings,
    }
    # The redundant-point fit quality is only meaningful for the general
    # configurations input; the legacy three-point solve is always exact.
    if source == "configurations":
        result["fit"] = {
            "n_points": n,
            "rms_residual_cm3": round(rms_res, 6),
            "max_residual_cm3": round(max_res, 6),
        }
    return result


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
