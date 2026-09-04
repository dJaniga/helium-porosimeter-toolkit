"""
Daily hardware calibration of a reference cell (procedure section 5.3,
eqs. (4)-(11)): determination of Vr, the curvature term and V_D.

Every calibration configuration i obeys a base equation of the form

    V_i = f(x_i) - V_D ,   x_i = (R - P_i) / P_i

where P_i is the equilibrium pressure and V_i the void volume in the matrix
cup for that configuration.  Three models are offered for f (see
`physics`), selected with "model" in the input file:

    "quadratic"  (default)   f = Vr*x + V_LIN*x^2      - the manual's eq. (4)
    "linear"                 f = Vr*x                  - pure Boyle's law
    "harmonic"               f = Vr*x/(1 + D*x)        - harmonic decline of
                                                         the apparent Vr

The unknowns are determined from at least as many configurations as the
model has parameters by least squares; with exactly that many points the
fit is exact, and for the quadratic model it reproduces the manual's
closed-form two-disc solution (eqs. (9)-(11)).

The model choice applies to the general "configurations" input only.  The
legacy two-disc shape is the manual's closed form and is always quadratic.
"""

from datetime import datetime

from .constants import (
    DEFAULT_CAL_UNCERTAINTIES,
    DEFAULT_TOLERANCES,
    FACTORY_CELLS,
)
from .errors import InputError
from .physics import (
    HARMONIC,
    LINEAR,
    MODEL_CURVATURE,
    MODEL_MIN_POINTS,
    MODEL_PARAMS,
    PARAM_KEYS,
    QUADRATIC,
    check_model,
    equivalent_V_LIN,
    expansion_ratio,
    gas_volume,
    reference_pressure,
)
from .uncertainty import propagate

# Reported decimals per fitted parameter (D is a dimensionless decline
# constant of order 0.01 and needs more digits than the volumes).
_PARAM_DIGITS = {"D": 9}


def _solve(A, b):
    """
    Solve the square linear system A x = b by Gauss elimination with partial
    pivoting.  Returns the solution list, or None if A is singular.
    """
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    scale = max((abs(v) for row in A for v in row), default=0.0)
    tol = 1e-12 * scale if scale else 1e-12
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) <= tol:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [val / pv for val in M[c]]
        for r in range(n):
            if r != c:
                f = M[r][c]
                M[r] = [M[r][k] - f * M[c][k] for k in range(n + 1)]
    return [M[i][n] for i in range(n)]


def _lstsq(rows, ys):
    """Least-squares solution of rows*p = ys via the normal equations."""
    n = len(rows[0])
    ATA = [[0.0] * n for _ in range(n)]
    ATy = [0.0] * n
    for a, y in zip(rows, ys):
        for i in range(n):
            ATy[i] += a[i] * y
            for j in range(n):
                ATA[i][j] += a[i] * a[j]
    return _solve(ATA, ATy)


def _singular(name, model):
    return InputError(
        'Cell "%s": the calibration pressures do not span enough distinct '
        "expansion ratios - the %s fit is singular (need at least %d "
        "configurations at clearly different pressures)."
        % (name, model, MODEL_MIN_POINTS[model]))


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
    return {"Vr": Vr, "V_LIN": V_LIN, "V_D": V_D}


def _fit_quadratic(xs, ys, name):
    """
    Least-squares fit of [Vr, V_LIN, V_D] to V = Vr*x + V_LIN*x^2 - V_D
    (design row a = [x, x^2, -1]).
    """
    sol = _lstsq([(x, x * x, -1.0) for x in xs], ys)
    if sol is None:
        raise _singular(name, QUADRATIC)
    return {"Vr": sol[0], "V_LIN": sol[1], "V_D": sol[2]}


def _fit_linear(xs, ys, name):
    """Least-squares fit of [Vr, V_D] to V = Vr*x - V_D."""
    sol = _lstsq([(x, -1.0) for x in xs], ys)
    if sol is None:
        raise _singular(name, LINEAR)
    return {"Vr": sol[0], "V_D": sol[1]}


def _harmonic_profile(D, xs, ys):
    """
    For a fixed decline constant D the harmonic model is linear in
    (Vr, V_D), so the fit reduces to a one-dimensional search over D.
    Returns (sse, [Vr, V_D]) at this D, or (None, None) if D puts a point
    outside the model's validity range or leaves the system singular.
    """
    rows = []
    for x in xs:
        den = 1.0 + D * x
        if den <= 1e-9:
            return None, None
        rows.append((x / den, -1.0))
    sol = _lstsq(rows, ys)
    if sol is None:
        return None, None
    Vr, V_D = sol
    sse = sum((Vr * a[0] - V_D - y) ** 2 for a, y in zip(rows, ys))
    return sse, sol


def _harmonic_sse(xs, ys, Vr, D, V_D):
    """Sum of squared residuals of the harmonic model, or None if D puts a
    calibration point outside its validity range."""
    total = 0.0
    for x, y in zip(xs, ys):
        den = 1.0 + D * x
        if den <= 1e-9:
            return None
        total += (Vr * x / den - V_D - y) ** 2
    return total


def _fit_harmonic(xs, ys, name):
    """
    Fit [Vr, D, V_D] to V = Vr*x/(1 + D*x) - V_D.

    The model is linear in (Vr, V_D) once D is fixed, so a coarse scan over
    the admissible D gives a starting point that is already close; the fit
    is then finished by Gauss-Newton on all three parameters with
    backtracking (the residuals are small, so it converges quadratically and
    reproduces the exact solution when the points exactly determine it).
    """
    xmax = max(xs)
    # Keep 1 + D*x inside [0.1, 10] over the calibrated range: outside it the
    # model is being extrapolated far past anything the data can support.
    lo, hi = -0.9 / xmax, 9.0 / xmax
    best = None
    scan = 200
    for k in range(scan + 1):
        D = lo + (hi - lo) * k / scan
        sse, sol = _harmonic_profile(D, xs, ys)
        if sse is not None and (best is None or sse < best[0]):
            best = (sse, D, sol)
    if best is None:
        raise _singular(name, HARMONIC)
    sse, D, (Vr, V_D) = best

    for _ in range(200):
        JTJ = [[0.0] * 3 for _ in range(3)]
        JTr = [0.0] * 3
        for x, y in zip(xs, ys):
            d = 1.0 + D * x
            # d(residual)/d(Vr, D, V_D)
            a = (x / d, -Vr * x * x / (d * d), -1.0)
            r = Vr * x / d - V_D - y
            for i in range(3):
                JTr[i] -= a[i] * r
                for j in range(3):
                    JTJ[i][j] += a[i] * a[j]
        delta = _solve(JTJ, JTr)
        if delta is None:
            break
        step, moved = 1.0, None
        for _ in range(60):            # backtrack until the fit improves
            cand = (Vr + step * delta[0], D + step * delta[1],
                    V_D + step * delta[2])
            c_sse = _harmonic_sse(xs, ys, *cand)
            if c_sse is not None and c_sse <= sse:
                moved = max(abs(step * delta[k]) / (1.0 + abs(cand[k]))
                            for k in range(3))
                Vr, D, V_D, sse = cand[0], cand[1], cand[2], c_sse
                break
            step *= 0.5
        if moved is None or moved <= 1e-15:
            break

    return {"Vr": Vr, "D": D, "V_D": V_D}


_FITTERS = {QUADRATIC: _fit_quadratic, LINEAR: _fit_linear,
            HARMONIC: _fit_harmonic}


def _parse_configs(cell_input, name, model):
    """
    Return (configs, source) where configs is a list of (P, V) tuples -
    equilibrium pressure and matrix-cup void volume - accepting either the
    general "configurations" list or the legacy two-disc shape.

    Legacy: "pressures" {P_DV, P1, P2} + "disc_volumes_cm3" {V1, V2, opt V0}.
    General: "configurations" [{"P": ..., "V": ...}, ...], at least as many
    points as the selected model has parameters, where V is the total void
    volume in the cup at that pressure (0 for the completely filled cup, the
    removed-disc volume otherwise).
    """
    if "configurations" in cell_input:
        raw = cell_input["configurations"]
        need = MODEL_MIN_POINTS[model]
        if not isinstance(raw, list) or len(raw) < need:
            raise InputError(
                'Cell "%s": "configurations" must be a list of at least '
                "%d {P, V} points for the %s model." % (name, need, model))
        configs = []
        try:
            for c in raw:
                configs.append((float(c["P"]), float(c["V"])))
        except (KeyError, TypeError, ValueError):
            raise InputError(
                'Cell "%s": each configuration needs a numeric "P" '
                '(equilibrium pressure) and "V" (void volume in cm3).' % name)
        return configs, "configurations"
    if model != QUADRATIC:
        raise InputError(
            'Cell "%s": the legacy two-disc shape is the manual\'s '
            'closed-form solution and is always quadratic; give the points '
            'as "configurations" [{P, V}, ...] to fit the "%s" model.'
            % (name, model))
    try:
        p = cell_input["pressures"]
        P_DV, P1, P2 = float(p["P_DV"]), float(p["P1"]), float(p["P2"])
        v = cell_input["disc_volumes_cm3"]
        V1, V2 = float(v["V1"]), float(v["V2"])
        V0 = float(v.get("V0", 0.0))
    except (KeyError, TypeError, ValueError):
        raise InputError(
            'Cell "%s": needs "configurations" [{P, V}, ...] (at least three '
            'points) or the legacy "pressures" {P_DV, P1, P2} + '
            '"disc_volumes_cm3" {V1, V2, optional V0}.' % name)
    return [(P_DV, V0), (P1, V1), (P2, V2)], "legacy"


def calibrate_cell(cell_input, R, tolerances, offset=0.0,
                   uncertainties=DEFAULT_CAL_UNCERTAINTIES,
                   model=QUADRATIC):
    """
    Daily determination of the calibration constants for one reference cell
    (manual sections 3.5 and 4.5-4.6) from three or more configurations.

    The classic two-disc procedure (P_DV with the matrix cup completely
    filled with calibration discs, P1/P2 with disc set 1/2 removed) is the
    exactly-determined special case of the quadratic model; extra
    configurations make the fit over-determined and let residuals flag a bad
    reading.  `model` is the file-level default; a cell may override it with
    its own "model" key.
    """
    name = cell_input.get("cell", "?")
    model = check_model(cell_input.get("model", model), 'Cell "%s"' % name)
    configs, source = _parse_configs(cell_input, name, model)
    n = len(configs)

    # Flatten to a per-reading dict so the GUM propagation can perturb each
    # pressure and void volume independently.
    vals = {}
    for i, (P, V) in enumerate(configs):
        vals["P%d" % i] = P
        vals["V%d" % i] = V

    # The legacy three-point shape uses the manual's exact closed form; the
    # general shape is fitted with the selected model.
    fit = _fit_two_disc if source == "legacy" else _FITTERS[model]

    def solve(v):
        xs = [expansion_ratio(R, v["P%d" % i], offset) for i in range(n)]
        ys = [v["V%d" % i] for i in range(n)]
        return fit(xs, ys, name)

    params = solve(vals)
    Vr = params["Vr"]

    u_p = float(uncertainties["pressure"])
    u_v = float(uncertainties["disc_volume_cm3"])
    # A completely filled cup (V == 0) is a defined reference with no disc
    # volume, hence no disc-table uncertainty (matches the legacy V0 rule).
    u_in = {}
    for i, (P, V) in enumerate(configs):
        u_in["P%d" % i] = u_p
        u_in["V%d" % i] = u_v if V else 0.0
    u_out, sens = propagate(solve, vals, u_in, params)
    curvature = MODEL_CURVATURE[model]
    cov = None
    if curvature is not None:
        cov = sum(d.get("Vr", 0.0) * d.get(curvature, 0.0)
                  for d in sens.values())

    # Fit residuals (predicted minus measured void volume) at each point.
    residuals = []
    for P, V in configs:
        x = expansion_ratio(R, P, offset)
        residuals.append((gas_volume(model, x, params) - params["V_D"]) - V)
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
        deviation = {
            "factory_Vr_cm3": factory["Vr"],
            "factory_V_LIN_cm3": factory["V_LIN"],
            "Vr_deviation_pct": round(dev_Vr, 3),
        }
        if abs(dev_Vr) > tolerances["Vr_pct"]:
            warnings.append(
                "Vr deviates %.2f%% from the factory value (tolerance %.1f%%): "
                "suspect a leak or temperature drift - run diagnostics before "
                "measuring." % (dev_Vr, tolerances["Vr_pct"]))
        if model == LINEAR:
            # A linear fit has no second-order term, so there is nothing to
            # compare with the factory V_LIN.
            deviation["V_LIN_comparison"] = (
                "not applicable: the linear model has no second-order term")
        else:
            # For the harmonic model the comparable quantity is the
            # second-order coefficient of its expansion, -Vr*D.
            V_LIN_eq = equivalent_V_LIN(model, params)
            dev_VL = 100.0 * (V_LIN_eq - factory["V_LIN"]) / factory["V_LIN"]
            if model == HARMONIC:
                deviation["V_LIN_equivalent_cm3"] = round(V_LIN_eq, 6)
            deviation["V_LIN_deviation_pct"] = round(dev_VL, 3)
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

    def digits(param):
        return _PARAM_DIGITS.get(param, 6)

    unc = {}
    for param in MODEL_PARAMS[model]:
        unc["u_" + PARAM_KEYS[param]] = round(u_out[param], digits(param))
    if cov is not None:
        unc["cov_Vr_" + curvature] = cov
    unc["inputs_1sigma"] = {"pressure": u_p, "disc_volume_cm3": u_v}

    result = {"cell": name, "R": R}
    # The legacy shape has no model choice, and omitting the key keeps its
    # output identical to the original tool's.
    if source == "configurations":
        result["model"] = model
    for param in MODEL_PARAMS[model]:
        result[PARAM_KEYS[param]] = round(params[param], digits(param))
    result["uncertainty"] = unc
    result["inputs"] = inputs
    result["factory_comparison"] = deviation
    result["warnings"] = warnings
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
    model = check_model(data.get("model"), "Calibration input")

    cells = data.get("cells")
    if not cells:
        raise InputError('Calibration input needs a non-empty "cells" list.')

    results = [calibrate_cell(cell, R, tolerances, offset, uncertainties,
                              model)
               for cell in cells]
    return {
        "type": "calibration_result",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": data.get("meta", {}),
        "R": R,
        "meter_offset": offset,
        "cells": results,
    }
