"""
Factory reference-cell values, default tolerances and uncertainties, and the
sample-type vocabulary used throughout the toolkit.
"""

from .errors import InputError

# ----------------------------------------------------------------------------
# Factory calibration values of the reference cells (procedure, Table 1)
# ----------------------------------------------------------------------------
FACTORY_CELLS = {
    "Mini": {"Vr": 7.6695,   "V_LIN": 0.092998},
    "A":    {"Vr": 10.9175,  "V_LIN": 0.061402},
    "B":    {"Vr": 14.7018,  "V_LIN": 0.092785},
    "C":    {"Vr": 22.2263,  "V_LIN": 0.155776},
    "#1":   {"Vr": 293.1392, "V_LIN": 1.982447},
    "#2":   {"Vr": 575.5168, "V_LIN": 2.834110},
}

# Default tolerances for the daily check against factory values.
# "fit_residual_pct" bounds, as a fraction of Vr, the largest allowed
# deviation of any calibration point from the fitted curve (used only when
# three or more configurations over-determine the fit).
DEFAULT_TOLERANCES = {"Vr_pct": 1.0, "V_LIN_pct": 10.0,
                      "fit_residual_pct": 1.0}

# Sample types: core plugs (rdzenie) vs cuttings / loose grains (okruchy).
SAMPLE_TYPES = {
    "core": "core", "rdzen": "core", "rdzeń": "core", "plug": "core",
    "czop": "core",
    "cuttings": "cuttings", "okruchy": "cuttings", "zwierciny": "cuttings",
    "grains": "cuttings", "ziarna": "cuttings", "piasek": "cuttings",
}

# ----------------------------------------------------------------------------
# Default standard uncertainties (1-sigma) of the raw inputs.  "pressure" is
# the repeatability of a stabilized meter reading in counts (display
# resolution + stabilization); 2 counts = 0.01 psi at R = 19836.  With this
# default the propagated grain-volume uncertainty is ~0.5%, matching the
# accuracy stated in the manual (section 1).  Increase it in the input file
# if readings drift (temperature instability, slow equilibration).
# ----------------------------------------------------------------------------
DEFAULT_CAL_UNCERTAINTIES = {
    "pressure": 2.0,           # meter counts, repeatability of a reading
    "disc_volume_cm3": 0.002,  # calibration disc volume (Annex A table)
}
DEFAULT_MEAS_UNCERTAINTIES = {
    "pressure": 2.0,
    "mass_g": 0.01,               # analytical balance
    "diameter_cm": 0.01,          # caliper on the plug
    "length_cm": 0.01,
    "bulk_volume_cm3": 0.05,      # directly given V_T
    "removed_disc_volume_cm3": 0.002,
}


def normalize_sample_type(value, where):
    if value is None:
        return "core"
    key = str(value).strip().lower()
    if key not in SAMPLE_TYPES:
        raise InputError(
            '%s: unknown "sample_type" %r - use "core"/"rdzen" or '
            '"cuttings"/"okruchy".' % (where, value))
    return SAMPLE_TYPES[key]
