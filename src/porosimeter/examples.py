"""
Example input templates written by the "init" command.

Both templates describe the same reference cell ("C"), so the pair can be
run end to end straight after "init":

    python -m porosimeter calibrate examples/calibration_input.json
    python -m porosimeter measure   examples/measurement_input.json

The calibration template ships the recommended disc sequence for cell C:
the full spacer stack in the Hassler holder, about a quarter of it removed,
then the holder empty.  That last, widest configuration is what pins V_LIN
down - see the README for the numbers behind the choice.
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
    "model": "quadratic",
    "_model_comment": (
        "Model fitted to the multi-point 'configurations' below, and the "
        "one every measurement based on this calibration will use: "
        "'quadratic' V = Vr*x + V_LIN*x^2 - V_D (the manual's equation, "
        "default, 3+ points), 'linear' V = Vr*x - V_D (pure Boyle's law, "
        "no linearity correction, 2+ points), or 'harmonic' "
        "V = Vr*x/(1 + D*x) - V_D (harmonic decline of the apparent "
        "reference volume, 3+ points; D is small and normally negative, "
        "with -Vr*D playing the role of V_LIN). Override per cell with a "
        "'model' key inside the cell object. The legacy two-disc shape is "
        "the manual's closed form and is always quadratic."),
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
            "cell": "C",
            "_comment": ("Recommended three-point sequence for cell C, "
                         "run in the Hassler holder on the port you "
                         "measure through: (1) the FULL spacer-disc stack, "
                         "V = 0; (2) about a quarter of the stack volume "
                         "removed, V = 10.144 here; (3) every disc out, "
                         "holder EMPTY, V = 40.770 here. V is the "
                         "cumulative void - the sum of the discs removed "
                         "so far - and you never put a disc back "
                         "mid-sequence. The empty-holder point is what "
                         "pins down V_LIN: stopping halfway triples "
                         "u(V_LIN). The widest void must be at least Vr "
                         "(22.23 cm3 for cell C). Add a fourth point if "
                         "you want the fit-residual check that flags a "
                         "misread pressure. Substitute your own disc "
                         "volumes and readings; one object per cell you "
                         "calibrate, and only one per cell."),
            "configurations": [
                {"P": 18820.3, "V": 0.0},
                {"P": 13148.8, "V": 10.144},
                {"P": 6926.1, "V": 40.770},
            ],
        },
    ],
}

SAMPLE_COMMENT = (
    "core_holder (required): the two Hassler-holder readings. Pick the "
    "spacer discs that leave a gap just big enough for the plug, read P_DV "
    "with those discs alone, then add the core WITHOUT disturbing them and "
    "read P1. Expect P1 > P_DV: the core displaces gas space. The disc "
    "volumes cancel and the holder need not be packed full. bulk_volume "
    "(required): caliper dimensions of the plug, or {\"value_cm3\": ...} "
    "from an independent method - the readings give the grain volume, so "
    "the pore volume is Vp = V_T - Vg. dry_mass_g (optional): dry mass of "
    "the plug, used for the bulk density. The provenance keys below "
    "(description, lithology, formation, well, depth, depth_unit, "
    "prepared_by, prepared_on, notes) never enter a calculation; they are "
    "carried through to 'python -m porosimeter export', which writes one "
    "sample file per plug for the gas-permeameter toolkit.")

EXAMPLE_MEASUREMENT = {
    "meta": {
        "operator": "User",
        "date": "2026-07-15",
        "temperature_C": 21.5,
    },
    "calibration": {
        "file": "calibration_result.json",
        "cell": "C",
        "_comment": ("Points at the output of 'python -m porosimeter "
                     "calibrate'. The model fitted there is read from the "
                     "file and used to reduce these samples, so a harmonic "
                     "or linear calibration is never re-interpreted as the "
                     "quadratic default. Inline alternative: {\"R\": "
                     "19836.0, \"Vr_cm3\": 22.2263, \"V_LIN_cm3\": "
                     "0.155776}, or with a model: {\"R\": 19836.0, "
                     "\"model\": \"harmonic\", \"Vr_cm3\": 22.2263, "
                     "\"D\": -0.007}."),
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
            "core_holder": {"P_DV": 9374.0, "P1": 17395.7},
            "bulk_volume": {"diameter_cm": 2.54, "length_cm": 5.08},
            "well": "N/A",
            "formation": "N/A",
            "lithology": "N/A",
            "depth": None,
            "depth_unit": "m",
        },
        {
            "sample_id": "S-02",
            "dry_mass_g": 58.31,
            "core_holder": {"P_DV": 9374.0, "P1": 17233.5},
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
