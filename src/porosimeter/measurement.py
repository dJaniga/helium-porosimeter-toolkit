"""
Sample measurements (procedure sections 6-8): grain volume with the matrix
cup, pore volume with the Hassler core holder, and the derived bulk volume,
densities and porosity.
"""

import json
import math
import os
from datetime import datetime

from .constants import DEFAULT_MEAS_UNCERTAINTIES, normalize_sample_type
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
        cells = cal.get("cells", [])
        match = None
        for c in cells:
            if cell_name is None or c.get("cell") == cell_name:
                match = c
                break
        if match is None:
            raise InputError(
                'Cell "%s" not found in calibration file %s.'
                % (cell_name, block["file"]))
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


def measure_sample(sample, cal, offset=0.0, default_type="core",
                   unc_file=None):
    """Process one sample record; returns the data-recording-card dict."""
    sid = sample.get("sample_id", "?")
    stype = normalize_sample_type(
        sample.get("sample_type", default_type), 'Sample "%s"' % sid)
    R = cal["R"]
    warnings = []
    result = {
        "sample_id": sid,
        "sample_type": stype,
        "dry_mass_g": sample.get("dry_mass_g"),
    }

    u_in = dict(DEFAULT_MEAS_UNCERTAINTIES)
    u_in.update(unc_file or {})
    u_in.update(sample.get("uncertainties", {}))

    grain = sample.get("grain_volume")
    pore = sample.get("pore_volume")
    bulk_block = sample.get("bulk_volume")
    ms = sample.get("dry_mass_g")

    if pore is not None and stype == "cuttings":
        warnings.append(
            'Sample type is "cuttings" (okruchy): the Hassler core-holder '
            'pore-volume measurement applies only to core plugs - the '
            '"pore_volume" block was ignored.')
        pore = None
    if stype == "cuttings" and grain is None:
        warnings.append(
            'Sample type is "cuttings" (okruchy): a "grain_volume" '
            "measurement (matrix cup) is expected but missing.")
    if (stype == "cuttings" and bulk_block is not None
            and "value_cm3" not in bulk_block):
        warnings.append(
            'Sample type is "cuttings" (okruchy): cylinder dimensions do '
            'not apply - give "bulk_volume": {"value_cm3": ...} from an '
            "independent method if total volume is known; the block was "
            "ignored.")
        bulk_block = None

    # ---- assemble the input vector (values + standard uncertainties) -------
    vals = {"Vr": cal["Vr"], "V_LIN": cal["V_LIN"]}
    u = {"Vr": cal.get("u_Vr", 0.0), "V_LIN": cal.get("u_V_LIN", 0.0)}
    if grain is not None:
        vals["gP_DV"] = float(grain["P_DV"])  # cup empty (mini) or full
        vals["gP1"] = float(grain["P1"])      # cup with sample
        # 1"/1-1/2" cup variant: the sample replaces removed discs whose
        # known volume is given (manual 3.6.2 step 9); 0 for an empty cup.
        vals["gV_rem"] = float(grain.get("removed_disc_volume_cm3", 0.0))
        u["gP_DV"] = u["gP1"] = float(u_in["pressure"])
        u["gV_rem"] = (float(u_in["removed_disc_volume_cm3"])
                       if vals["gV_rem"] else 0.0)
    if pore is not None:
        vals["pP_DV"] = float(pore["P_DV"])   # holder with solid plug
        vals["pP1"] = float(pore["P1"])       # holder with core sample
        u["pP_DV"] = u["pP1"] = float(u_in["pressure"])
    if ms is not None:
        vals["m"] = float(ms)
        u["m"] = float(u_in["mass_g"])
    vt_mode = None
    if bulk_block is not None:
        if "value_cm3" in bulk_block:
            vt_mode = "given"
            vals["VT_given"] = float(bulk_block["value_cm3"])
            u["VT_given"] = float(u_in["bulk_volume_cm3"])
        else:
            try:
                vals["dia"] = float(bulk_block["diameter_cm"])
                vals["len"] = float(bulk_block["length_cm"])
            except (KeyError, TypeError, ValueError):
                raise InputError(
                    'Sample "%s": "bulk_volume" needs "value_cm3" or '
                    '{"diameter_cm", "length_cm"}.' % sid)
            vt_mode = "cylinder geometry"
            u["dia"] = float(u_in["diameter_cm"])
            u["len"] = float(u_in["length_cm"])

    def compute(v):
        """All derived quantities from the raw inputs (used for the nominal
        result and, re-evaluated with perturbed inputs, for propagation)."""
        out = {}
        Vg = Vp = None
        if grain is not None:
            V_D_cup = expanded_volume(R, v["gP_DV"], v["Vr"], v["V_LIN"],
                                      offset)
            # Grain volume per the manufacturer's HP-41 program (Annex B,
            # LBL A/E): Vg = V_removed - (-V_D + Vr*x1 + V_LIN*x1^2).
            # The printed equation in the manual shows "+V_LIN(...)^2";
            # the HP-41 listing and eq. (1) require subtracting the whole
            # expanded-volume term.
            Vg = (V_D_cup + v["gV_rem"]
                  - expanded_volume(R, v["gP1"], v["Vr"], v["V_LIN"], offset))
            out["V_D_grain_cm3"] = V_D_cup
            out["V_g_cm3"] = Vg
        if pore is not None:
            V_D_holder = expanded_volume(R, v["pP_DV"], v["Vr"], v["V_LIN"],
                                         offset)
            Vp = -V_D_holder + expanded_volume(R, v["pP1"], v["Vr"],
                                               v["V_LIN"], offset)
            out["V_D_pore_cm3"] = V_D_holder
            out["V_p_cm3"] = Vp
        VT = None
        if vt_mode == "given":
            VT = v["VT_given"]
        elif vt_mode == "cylinder geometry":
            VT = math.pi * v["dia"] * v["dia"] / 4.0 * v["len"]
        elif Vg is not None and Vp is not None:
            VT = Vg + Vp
        if VT is not None:
            out["V_T_cm3"] = VT
        if Vp is None and VT is not None and Vg is not None:
            Vp = VT - Vg  # indirect pore volume
            out["V_p_cm3"] = Vp
        if "m" in v and Vg is not None and Vg > 0:
            out["grain_density_g_cm3"] = v["m"] / Vg
        if Vp is not None and VT is not None and VT > 0:
            out["porosity_pct"] = 100.0 * Vp / VT
        if "m" in v and VT is not None and VT > 0:
            out["bulk_density_g_cm3"] = v["m"] / VT
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

    def put(dest, key, digits):
        if key in y0:
            dest[key] = round(y0[key], digits)
            if u_y.get(key, 0.0) > 0:
                dest["u_" + key] = round(u_y[key], digits)

    # ---- report blocks ------------------------------------------------------
    if grain is not None:
        Vg = y0["V_g_cm3"]
        if Vg <= 0:
            warnings.append(
                "Grain volume is not positive - P1 and P_DV are probably "
                "swapped or the cup was not sealed.")
        elif Vg < 1.0:
            warnings.append(
                "Grain volume < 1 cm3: expect a larger percentage error "
                "(manual section 3.6.1 item 7).")
        block = {"P_DV": vals["gP_DV"], "P1": vals["gP1"],
                 "removed_disc_volume_cm3": vals["gV_rem"],
                 "V_D_cm3": round(y0["V_D_grain_cm3"], 4),
                 "Vg_cm3": round(Vg, 4)}
        if u_y.get("V_g_cm3", 0.0) > 0:
            block["u_Vg_cm3"] = round(u_y["V_g_cm3"], 4)
        result["grain_volume"] = block
    if pore is not None:
        Vp = y0["V_p_cm3"]
        if Vp <= 0:
            warnings.append(
                "Pore volume is not positive - check P_DV (solid plug) vs "
                "P1 (sample) readings.")
        block = {"P_DV": vals["pP_DV"], "P1": vals["pP1"],
                 "V_D_cm3": round(y0["V_D_pore_cm3"], 4),
                 "Vp_cm3": round(Vp, 4)}
        if u_y.get("V_p_cm3", 0.0) > 0:
            block["u_Vp_cm3"] = round(u_y["V_p_cm3"], 4)
        result["pore_volume"] = block

    derived = {}
    put(derived, "V_T_cm3", 4)
    if "V_T_cm3" in y0:
        derived["V_T_method"] = vt_mode or "Vg + Vp"
    put(derived, "V_g_cm3", 4)
    put(derived, "grain_density_g_cm3", 4)
    put(derived, "V_p_cm3", 4)
    if pore is None and "V_p_cm3" in y0:
        derived["V_p_method"] = "V_T - V_g (indirect)"
    put(derived, "porosity_pct", 3)
    put(derived, "bulk_density_g_cm3", 4)

    if not derived and grain is None and pore is None:
        warnings.append(
            'No "grain_volume", "pore_volume" or "bulk_volume" block given - '
            "nothing to compute.")

    result["results"] = derived
    result["warnings"] = warnings
    return result


def run_measurement(data, base_dir):
    offset = float(data.get("meter_offset", 0.0))
    default_type = normalize_sample_type(
        data.get("sample_type", "core"), "Top-level")
    cal = load_calibration_reference(data.get("calibration", {}), base_dir,
                                     offset)
    samples = data.get("samples")
    if not samples:
        raise InputError('Measurement input needs a non-empty "samples" list.')

    unc_file = data.get("uncertainties", {})
    out_samples = [measure_sample(s, cal, offset, default_type, unc_file)
                   for s in samples]
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
        "samples": out_samples,
    }
