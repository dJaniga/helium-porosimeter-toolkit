"""
Example input templates written by the "init" command.

Both templates describe the same reference cell ("A"), so the pair can be
run end to end straight after "init":

    python -m porosimeter calibrate examples/calibration_input.json
    python -m porosimeter measure   examples/measurement_input.json
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
                         "cup). More than two discs? Replace \"pressures\" "
                         "and \"disc_volumes_cm3\" with \"configurations\": "
                         "[{\"P\": 17872.7, \"V\": 0.0}, {\"P\": 13967.4, "
                         "\"V\": 3.398}, ...], one entry per disc set - P "
                         "the equilibrium reading, V the total void volume "
                         "in the cup. Three points or more; beyond three "
                         "the constants are least-squares fitted and a "
                         "\"fit\" block reports the residuals. Add one "
                         "object per cell you calibrate, and only one per "
                         "cell."),
            "disc_volumes_cm3": {"V0": 0.0, "V1": 3.398, "V2": 6.768},
            "pressures": {"P_DV": 17872.7, "P1": 13967.4, "P2": 11486.7},
        },
    ],
}

SAMPLE_COMMENT = (
    "pore_volume (required): P_DV = blank reading with the Hassler holder "
    "closed on the solid steel plug; P1 = the same holder with the core "
    "plug in it. Expect P1 < P_DV - the porous sample adds accessible "
    "volume to the holder. bulk_volume (optional): caliper dimensions of "
    "the plug, or {\"value_cm3\": ...} from an independent method; without "
    "it only Vp is reported, with it also porosity. dry_mass_g (optional): "
    "dry mass of the plug, used for the bulk density.")

EXAMPLE_MEASUREMENT = {
    "meta": {
        "operator": "User",
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
    "meter_offset": 0.0,
    "uncertainties": {
        "pressure": 2.0,
        "mass_g": 0.01,
        "diameter_cm": 0.01,
        "length_cm": 0.01,
        "_comment": ("Standard (1-sigma) uncertainties of the raw inputs, "
                     "used to report each result as value +/- u: pressure "
                     "readings in meter counts, dry mass, caliper "
                     "dimensions. Override per sample with the same key "
                     "inside a sample. u(Vr)/u(V_LIN) are taken from the "
                     "calibration result file."),
    },
    "samples": [
        {
            "sample_id": "S-01",
            "_comment": SAMPLE_COMMENT,
            "dry_mass_g": 58.12,
            "pore_volume": {"P_DV": 11467.4, "P1": 9537.6},
            "bulk_volume": {"diameter_cm": 2.54, "length_cm": 5.08},
        },
        {
            "sample_id": "S-02",
            "dry_mass_g": 58.31,
            "pore_volume": {"P_DV": 11467.4, "P1": 9602.1},
            "bulk_volume": {"diameter_cm": 2.54, "length_cm": 5.08},
        },
    ],
}


def write_examples(directory):
    """Write both input templates into `directory`; returns their paths."""
    os.makedirs(directory, exist_ok=True)
    paths = []
    for name, payload in (
            ("calibration_input.json", EXAMPLE_CALIBRATION),
            ("measurement_input.json", EXAMPLE_MEASUREMENT)):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        paths.append(path)
    return paths
