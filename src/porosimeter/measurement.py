"""
Pore-volume measurement of core plugs (procedure sections 6-8): helium
expansion into the Hassler core holder, and the derived porosity and bulk
density.

One sample, one measurement: two meter readings taken on the core holder,
`P_DV` (blank - the holder closed on the solid steel plug) and `P1` (the
same holder with the core plug in it).  The difference of the two expanded
volumes is the pore volume.
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


def _read_pore_pressures(sample, sid):
    """The two required meter readings taken on the core holder."""
    pore = sample.get("pore_volume")
    if pore is None:
        raise InputError(
            'Sample "%s": a "pore_volume" block is required - the helium '
            'expansion into the core holder is the only measurement this '
            'toolkit performs.' % sid)
    try:
        return float(pore["P_DV"]), float(pore["P1"])
    except (KeyError, TypeError, ValueError):
        raise InputError(
            'Sample "%s": "pore_volume" needs the numeric readings "P_DV" '
            '(blank: the holder closed on the solid plug) and "P1" (the '
            'same holder with the core sample).' % sid)


def _read_bulk_volume(sample, sid, vals, u, u_in):
    """
    Total (bulk) volume of the plug: either measured off the plug with a
    caliper, or supplied ready-made.  Fills `vals` / `u` and returns the
    method name, or None when the block is absent.
    """
    bulk = sample.get("bulk_volume")
    if bulk is None:
        return None
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
    P_DV, P1 = _read_pore_pressures(sample, sid)
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
        # V_D is the dead volume of the holder, its tubing and the annulus
        # around the solid plug; the porous sample adds its pore space to it.
        V_D = expanded_volume(R, v["P_DV"], v["Vr"], v["V_LIN"], offset)
        out = {
            "V_D_cm3": V_D,
            "V_p_cm3": expanded_volume(R, v["P1"], v["Vr"], v["V_LIN"],
                                       offset) - V_D,
        }
        if vt_method == "given":
            out["V_T_cm3"] = v["V_T"]
        elif vt_method == "cylinder geometry":
            out["V_T_cm3"] = (math.pi * v["diameter"] * v["diameter"] / 4.0
                              * v["length"])
        else:
            return out
        if out["V_T_cm3"] > 0:
            out["porosity_pct"] = 100.0 * out["V_p_cm3"] / out["V_T_cm3"]
            if "mass" in v:
                out["bulk_density_g_cm3"] = v["mass"] / out["V_T_cm3"]
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
    if y0["V_p_cm3"] <= 0:
        warnings.append(
            "Pore volume is not positive - P_DV (blank, solid plug) and P1 "
            "(core sample) are probably swapped, or the holder did not seal.")
    elif y0.get("porosity_pct", 0.0) >= 100.0:
        warnings.append(
            "Porosity is at or above 100 percent - the pore volume exceeds "
            "the bulk volume of the plug; check the plug dimensions and the "
            "holder for a leak.")
    if vt_method is None:
        warnings.append(
            'No "bulk_volume" block: the pore volume was computed, but '
            "porosity and bulk density need the total volume of the plug.")

    # ---- report ------------------------------------------------------------
    def put(dest, key, digits):
        if key in y0:
            dest[key] = round(y0[key], digits)
            if u_y.get(key, 0.0) > 0:
                dest["u_" + key] = round(u_y[key], digits)

    result = {"sample_id": sid}
    if mass is not None:
        result["dry_mass_g"] = float(mass)
    result["pore_volume"] = {"P_DV": P_DV, "P1": P1,
                             "V_D_cm3": round(y0["V_D_cm3"], 4)}
    derived = {}
    put(derived, "V_p_cm3", 4)
    put(derived, "V_T_cm3", 4)
    if vt_method is not None:
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
