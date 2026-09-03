"""
Human-readable console summary of a calibration or measurement result.
"""


def print_summary(result):
    if result["type"] == "calibration_result":
        print("Calibration  (R = %.1f meter counts)" % result["R"])
        for c in result["cells"]:
            unc = c.get("uncertainty", {})
            print("  cell %-5s Vr = %10.4f +/- %.4f cm3   "
                  "V_LIN = %9.6f +/- %.6f cm3   V_D = %8.4f cm3"
                  % (c["cell"], c["Vr_cm3"], unc.get("u_Vr_cm3", 0.0),
                     c["V_LIN_cm3"], unc.get("u_V_LIN_cm3", 0.0),
                     c["V_D_cm3"]))
            for w in c["warnings"]:
                print("    WARNING: %s" % w)
    else:
        print("Measurement  (calibration: %s, R = %.1f, Vr = %.4f, "
              "V_LIN = %.6f)" % (result["calibration"]["source"],
                                 result["calibration"]["R"],
                                 result["calibration"]["Vr_cm3"],
                                 result["calibration"]["V_LIN_cm3"]))
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
