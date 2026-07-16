"""
Example input templates written by the "init" command.
"""

import json
import os

EXAMPLE_CALIBRATION = {
    "meta": {
        "operator": "User",
        "date": "2026-07-15",
        "temperature_C": 21.5,
        "instrument": "Corexport HMPoRZ, cat. no. 123",
    },
    "reference_pressure": {
        "R": 19836.0,
        "_comment": ("Daily meter reading with the reference cell charged "
                     "(R = 19836 for S/N A-20833). Alternatively give "
                     "transducer_sensitivity and supply_voltage to use "
                     "R = T.S. x V x 100 psig (manual section 4.2)."),
    },
    "meter_offset": 0.0,
    "tolerances": {"Vr_pct": 1.0, "V_LIN_pct": 10.0},
    "uncertainties": {
        "pressure": 2.0,
        "disc_volume_cm3": 0.002,
        "_comment": ("Standard (1-sigma) uncertainties of the inputs: "
                     "meter-reading repeatability in counts (2 counts = "
                     "0.01 psi at R = 19836; increase if readings drift) "
                     "and calibration-disc volume. Propagated to u(Vr), "
                     "u(V_LIN) in the output and then into every "
                     "measurement that uses this calibration."),
    },
    "cells": [
        {
            "cell": "A",
            "_comment": ("Recommended disc set for cell A (manual section "
                         "4.6): P_DV with the 1-1/2\" cup full of discs; "
                         "P1 with the 1/8\" disc removed (3.398 cm3); P2 "
                         "with the 1/4\" disc removed (6.768 cm3). V1/V2 "
                         "are the removed-disc volumes from the Annex A "
                         "table for this instrument (V0 = 0 for the full "
                         "cup)."),
            "disc_volumes_cm3": {"V0": 0.0, "V1": 3.398, "V2": 6.768},
            "pressures": {"P_DV": 17872.7, "P1": 13967.4, "P2": 11486.7},
        }
    ],
}

GRAIN_COMMENT = ("grain_volume: P_DV = empty matrix cup, P1 = cup "
                 "with sample; when the sample sits among discs in "
                 "a 1\"/1-1/2\" cup, give P_DV for the full cup and "
                 "add removed_disc_volume_cm3.")
CORE_COMMENT = (GRAIN_COMMENT +
                " pore_volume: P_DV = holder with solid plug, P1 = holder "
                "with sample. bulk_volume: plug dimensions or "
                "{\"value_cm3\": ...}; omit it to use V_T = Vg+Vp.")

SAMPLE_CORE_FULL = {
    "sample_id": "S-01",
    "dry_mass_g": 58.12,
    "_comment": CORE_COMMENT,
    "grain_volume": {"P_DV": 6082.5, "P1": 15432.7},
    "pore_volume": {"P_DV": 11467.4, "P1": 9537.6},
    "bulk_volume": {"diameter_cm": 2.54, "length_cm": 5.08},
}
SAMPLE_CUTTINGS_1 = {
    "sample_id": "S-01 (loose sand)",
    "dry_mass_g": 21.507,
    "_comment": GRAIN_COMMENT,
    "grain_volume": {"P_DV": 6082.5, "P1": 7831.3},
}
SAMPLE_CUTTINGS_2 = {
    "sample_id": "S-02 (cuttings)",
    "dry_mass_g": 57.95,
    "grain_volume": {"P_DV": 6082.5, "P1": 15432.7},
}


def build_measurement_example(mode=None):
    """Measurement input template; mode: None (mixed), "core", "cuttings"."""
    doc = {
        "meta": {
            "operator": "user",
            "date": "2026-07-15",
            "temperature_C": 21.5,
        },
        "calibration": {
            "file": "calibration_result.json",
            "cell": "A",
            "_comment": ("Points at the output of 'python -m porosimeter "
                         "calibrate'. Inline alternative: {\"R\": 19836.0, "
                         "\"Vr_cm3\": 10.9175, \"V_LIN_cm3\": 0.061402}."),
        },
        "_comment": ("sample_type: \"core\"/\"rdzen\" (czopy rdzenia) or "
                     "\"cuttings\"/\"okruchy\" (okruchy, ziarna, "
                     "zwierciny). Set once here for the whole file; "
                     "override per sample if needed. For cuttings only the "
                     "matrix-cup grain-volume measurement applies "
                     "(pore_volume and cylinder dimensions are ignored)."),
        "uncertainties": {
            "pressure": 2.0,
            "mass_g": 0.01,
            "diameter_cm": 0.01,
            "length_cm": 0.01,
            "_comment": ("Standard (1-sigma) uncertainties of the raw "
                         "inputs, used to report each result as value +/- "
                         "u: pressure readings in meter counts, dry mass, "
                         "caliper dimensions. Override per sample with the "
                         "same key inside a sample. u(Vr)/u(V_LIN) are "
                         "taken from the calibration result file."),
        },
    }
    if mode == "core":
        doc["sample_type"] = "core"
        second = dict(SAMPLE_CORE_FULL)
        second["sample_id"] = "S-02"
        second["dry_mass_g"] = 58.31
        second.pop("_comment")
        doc["samples"] = [SAMPLE_CORE_FULL, second]
    elif mode == "cuttings":
        doc["sample_type"] = "okruchy"
        doc["samples"] = [SAMPLE_CUTTINGS_1, SAMPLE_CUTTINGS_2]
    else:
        doc["sample_type"] = "core"
        mixed = dict(SAMPLE_CUTTINGS_1)
        mixed["sample_id"] = "S-02 (loose sand)"
        mixed["sample_type"] = "okruchy"
        doc["samples"] = [SAMPLE_CORE_FULL, mixed]
    return doc


def write_examples(directory, mode=None):
    os.makedirs(directory, exist_ok=True)
    paths = []
    for name, payload in (
            ("calibration_input.json", EXAMPLE_CALIBRATION),
            ("measurement_input.json", build_measurement_example(mode))):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        paths.append(path)
    return paths
