"""
Human-readable console summary of a calibration or measurement result.
"""

from .physics import QUADRATIC


def _cell_constants(cell):
    """The fitted constants of one cell, formatted for one summary line."""
    unc = cell.get("uncertainty", {})
    parts = ["Vr = %10.4f +/- %.4f cm3"
             % (cell["Vr_cm3"], unc.get("u_Vr_cm3", 0.0))]
    if "V_LIN_cm3" in cell:
        parts.append("V_LIN = %9.6f +/- %.6f cm3"
                     % (cell["V_LIN_cm3"], unc.get("u_V_LIN_cm3", 0.0)))
    if "D" in cell:
        parts.append("D = %11.8f +/- %.8f" % (cell["D"], unc.get("u_D", 0.0)))
    parts.append("V_D = %8.4f cm3" % cell["V_D_cm3"])
    return "   ".join(parts)


def print_summary(result):
    if result["type"] == "calibration_result":
        print("Calibration  (R = %.1f meter counts)" % result["R"])
        for c in result["cells"]:
            model = c.get("model", QUADRATIC)
            label = "%s [%s]" % (c["cell"], model)
            print("  cell %-22s %s" % (label, _cell_constants(c)))
            for w in c["warnings"]:
                print("    WARNING: %s" % w)
    else:
        cal = result["calibration"]
        constants = ["Vr = %.4f" % cal["Vr_cm3"]]
        if "V_LIN_cm3" in cal:
            constants.append("V_LIN = %.6f" % cal["V_LIN_cm3"])
        if "D" in cal:
            constants.append("D = %.8f" % cal["D"])
        print("Measurement  (calibration: %s [%s], R = %.1f, %s)"
              % (cal["source"], cal.get("model", QUADRATIC), cal["R"],
                 ", ".join(constants)))
        for s in result["samples"]:
            r = s["results"]

            def fmt(key, label, unit, decimals):
                val = ("%%.%df" % decimals) % r[key]
                if ("u_" + key) in r:
                    val += (" +/- " + ("%%.%df" % decimals) % r["u_" + key])
                return "%s = %s %s" % (label, val, unit)

            parts = []
            for key, label in (("V_p_cm3", "Vp"), ("V_T_cm3", "VT")):
                if key in r:
                    parts.append(fmt(key, label, "cm3", 3))
            if "porosity_pct" in r:
                parts.append(fmt("porosity_pct", "porosity", "%", 2))
            if "bulk_density_g_cm3" in r:
                parts.append(fmt("bulk_density_g_cm3", "rho_b", "g/cm3", 3))
            print("  %-12s %s" % (s["sample_id"] + ":", ",  ".join(parts)))
            for w in s["warnings"]:
                print("    WARNING: %s" % w)
