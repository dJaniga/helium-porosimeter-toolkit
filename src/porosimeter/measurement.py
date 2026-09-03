"""
Porosity of core plugs measured with the Hassler core holder (procedure
sections 6-8).

Two helium expansions into the same holder, with the same spacer discs in
place both times:

    P_DV  blank   - the selected spacer discs alone, the core's space left
                    open and gas-accessible
    P1    sample  - the same discs, undisturbed, with the core added

The core fills that space with solid while helium re-enters its pore
network, so what the core removes from the gas volume is its solid
framework:

    Vg = V(P_DV) - V(P1)          grain volume, directly measured
    Vp = V_T - Vg                 pore volume, from the caliper bulk volume

Adding the core reduces the gas space, so P1 > P_DV.  The discs cancel
because they do not move between the two readings, and the holder does not
need to be packed full - only unchanged apart from the core.
"""

import json
import math
import os
from datetime import datetime

from .constants import DEFAULT_MEAS_UNCERTAINTIES
from .errors import InputError
from .physics import expanded_volume
from .uncertainty import propagate


def load_calibration_reference(block, base_dir, offset=0.0):
    """
    Resolve {R, Vr, V_LIN} for a measurement.  Either inline:
        {"R": 19836.0, "Vr_cm3": 10.9175, "V_LIN_cm3": 0.061402}
    (R is the raw meter reading; the file-level meter_offset is subtracted)
    or from a calibration result file produced by the "calibrate" command
    (which stores the already offset-corrected R):
        {"file": "calibration_result.json", "cell": "A"}
    """
    if not isinstance(block, dict):
        raise InputError('"calibration" must be an object.')

    if "file" in block:
        path = block["file"]
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)
        with open(path, "r", encoding="utf-8") as fh:
            cal = json.load(fh)
        cell_name = block.get("cell")
        matches = [c for c in cal.get("cells", [])
                   if cell_name is None or c.get("cell") == cell_name]
        if not matches:
            raise InputError(
                'Cell "%s" not found in calibration file %s.'
                % (cell_name, block["file"]))
        if len(matches) > 1:
            # Never guess which calibration of a cell applies to a sample.
            names = ", ".join(sorted(str(c.get("cell")) for c in matches))
            raise InputError(
                'Calibration file %s offers more than one cell entry (%s): '
                'name the one to use in "calibration": {"cell": ...}, and '
                'remove any duplicates.' % (block["file"], names))
        match = matches[0]
        unc = match.get("uncertainty", {})
        return {
            "R": float(cal["R"]),
            "Vr": float(match["Vr_cm3"]),
            "V_LIN": float(match["V_LIN_cm3"]),
            "u_Vr": float(unc.get("u_Vr_cm3", 0.0)),
            "u_V_LIN": float(unc.get("u_V_LIN_cm3", 0.0)),
            "cov_Vr_V_LIN": float(unc.get("cov_Vr_V_LIN", 0.0)),
            "source": "%s (cell %s)" % (block["file"], match.get("cell")),
        }

    try:
        return {
            "R": float(block["R"]) - offset,
            "Vr": float(block["Vr_cm3"]),
            "V_LIN": float(block["V_LIN_cm3"]),
            "u_Vr": float(block.get("u_Vr_cm3", 0.0)),
            "u_V_LIN": float(block.get("u_V_LIN_cm3", 0.0)),
            "cov_Vr_V_LIN": float(block.get("cov_Vr_V_LIN", 0.0)),
            "source": "inline",
        }
    except (KeyError, TypeError, ValueError):
        raise InputError(
            '"calibration" needs either {"file", "cell"} or inline '
            '{"R", "Vr_cm3", "V_LIN_cm3"}.')


def _read_holder_pressures(sample, sid):
    """The two required meter readings taken on the core holder."""
    holder = sample.get("core_holder")
    if holder is None:
        raise InputError(
            'Sample "%s": a "core_holder" block is required - the two helium '
            'expansions into the holder are the measurement this toolkit '
            'performs.' % sid)
    try:
        return float(holder["P_DV"]), float(holder["P1"])
    except (KeyError, TypeError, ValueError):
        raise InputError(
            'Sample "%s": "core_holder" needs the numeric readings "P_DV" '
            '(blank: the selected spacer discs alone) and "P1" (the same '
            'discs, undisturbed, with the core added).' % sid)


def _read_bulk_volume(sample, sid, vals, u, u_in):
    """
    Total (bulk) volume of the plug, required: these two readings measure
    the grain volume, so the pore volume is Vp = V_T - Vg.  Either caliper
    dimensions or a ready-made value.  Fills `vals` / `u`, returns the
    method name.
    """
    bulk = sample.get("bulk_volume")
    if bulk is None:
        raise InputError(
            'Sample "%s": a "bulk_volume" block is required - the two '
            'readings measure the grain volume, and the pore volume is the '
            'bulk volume of the plug minus it.' % sid)
    if not isinstance(bulk, dict):
        raise InputError('Sample "%s": "bulk_volume" must be an object.' % sid)
    if "value_cm3" in bulk:
        try:
            vals["V_T"] = float(bulk["value_cm3"])
        except (TypeError, ValueError):
            raise InputError(
                'Sample "%s": "bulk_volume.value_cm3" must be numeric.' % sid)
        u["V_T"] = float(u_in["bulk_volume_cm3"])
        return "given"
    try:
        vals["diameter"] = float(bulk["diameter_cm"])
        vals["length"] = float(bulk["length_cm"])
    except (KeyError, TypeError, ValueError):
        raise InputError(
            'Sample "%s": "bulk_volume" needs either "value_cm3" or both '
            '"diameter_cm" and "length_cm".' % sid)
    u["diameter"] = float(u_in["diameter_cm"])
    u["length"] = float(u_in["length_cm"])
    return "cylinder geometry"


def measure_sample(sample, cal, offset=0.0, unc_file=None):
    """Process one core-plug record; returns the data-recording-card dict."""
    sid = sample.get("sample_id", "?")
    R = cal["R"]
    warnings = []

    u_in = dict(DEFAULT_MEAS_UNCERTAINTIES)
    u_in.update(unc_file or {})
    u_in.update(sample.get("uncertainties", {}))

    # ---- assemble the input vector (values + standard uncertainties) -------
    P_DV, P1 = _read_holder_pressures(sample, sid)
    vals = {"Vr": cal["Vr"], "V_LIN": cal["V_LIN"], "P_DV": P_DV, "P1": P1}
    u = {"Vr": cal.get("u_Vr", 0.0), "V_LIN": cal.get("u_V_LIN", 0.0),
         "P_DV": float(u_in["pressure"]), "P1": float(u_in["pressure"])}

    mass = sample.get("dry_mass_g")
    if mass is not None:
        vals["mass"] = float(mass)
        u["mass"] = float(u_in["mass_g"])

    vt_method = _read_bulk_volume(sample, sid, vals, u, u_in)

    def compute(v):
        """All derived quantities from the raw inputs (used for the nominal
        result and, re-evaluated with perturbed inputs, for propagation)."""
        # V_D is the gas space of the holder with the selected spacer discs
        # in it and no core.  Adding the core displaces its solid framework
        # only: helium re-enters the pore space, so the difference is Vg.
        V_D = expanded_volume(R, v["P_DV"], v["Vr"], v["V_LIN"], offset)
        Vg = V_D - expanded_volume(R, v["P1"], v["Vr"], v["V_LIN"], offset)
        if vt_method == "given":
            V_T = v["V_T"]
        else:
            V_T = math.pi * v["diameter"] * v["diameter"] / 4.0 * v["length"]
        out = {"V_D_cm3": V_D, "V_g_cm3": Vg, "V_T_cm3": V_T,
               "V_p_cm3": V_T - Vg}
        if V_T > 0:
            out["porosity_pct"] = 100.0 * out["V_p_cm3"] / V_T
            if "mass" in v:
                out["bulk_density_g_cm3"] = v["mass"] / V_T
        return out

    y0 = compute(vals)
    u_y, sens = propagate(compute, vals, u, y0)
    # Vr and V_LIN come from the same calibration and are strongly
    # correlated: add the covariance cross-term 2*(dy/dVr dVr)(dy/dVL dVL)*rho
    if cal.get("u_Vr") and cal.get("u_V_LIN") and cal.get("cov_Vr_V_LIN"):
        rho = cal["cov_Vr_V_LIN"] / (cal["u_Vr"] * cal["u_V_LIN"])
        rho = max(-1.0, min(1.0, rho))
        d_vr, d_vl = sens.get("Vr", {}), sens.get("V_LIN", {})
        for k in u_y:
            var = u_y[k] ** 2 + 2.0 * rho * d_vr.get(k, 0.0) * d_vl.get(k, 0.0)
            u_y[k] = math.sqrt(max(var, 0.0))

    # ---- plausibility checks -----------------------------------------------
    if y0["V_g_cm3"] <= 0:
        warnings.append(
            "Grain volume is not positive - adding the core must RAISE the "
            "reading (P1 > P_DV); the two readings are probably swapped, a "
            "disc moved between them, or - if the blank already packed the "
            "core's space with steel - the holder is in the matched-blank "
            "regime, where Vp is the difference of the readings itself.")
    elif y0["V_p_cm3"] <= 0:
        warnings.append(
            "Pore volume is not positive - the measured grain volume equals "
            "or exceeds the bulk volume of the plug; check the caliper "
            "dimensions and the holder seal.")

    # ---- report ------------------------------------------------------------
    def put(dest, key, digits):
        if key in y0:
            dest[key] = round(y0[key], digits)
            if u_y.get(key, 0.0) > 0:
                dest["u_" + key] = round(u_y[key], digits)

    result = {"sample_id": sid}
    if mass is not None:
        result["dry_mass_g"] = float(mass)
    # The readings and what they measure directly, for the record card.
    result["core_holder"] = {"P_DV": P_DV, "P1": P1,
                             "V_D_cm3": round(y0["V_D_cm3"], 4),
                             "V_g_cm3": round(y0["V_g_cm3"], 4)}
    derived = {}
    put(derived, "V_p_cm3", 4)
    put(derived, "V_T_cm3", 4)
    derived["V_T_method"] = vt_method
    put(derived, "porosity_pct", 3)
    put(derived, "bulk_density_g_cm3", 4)
    result["results"] = derived
    result["warnings"] = warnings
    return result


def run_measurement(data, base_dir):
    offset = float(data.get("meter_offset", 0.0))
    cal = load_calibration_reference(data.get("calibration", {}), base_dir,
                                     offset)
    samples = data.get("samples")
    if not samples:
        raise InputError('Measurement input needs a non-empty "samples" list.')

    unc_file = data.get("uncertainties", {})
    return {
        "type": "measurement_result",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": data.get("meta", {}),
        "calibration": {
            "source": cal["source"],
            "R": cal["R"],
            "Vr_cm3": cal["Vr"],
            "V_LIN_cm3": cal["V_LIN"],
        },
        "meter_offset": offset,
        "samples": [measure_sample(s, cal, offset, unc_file)
                    for s in samples],
    }
