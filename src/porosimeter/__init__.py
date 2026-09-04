"""
HMPoRZ helium porosimeter toolkit (Corexport Extended Range Helium Porosimeter).

Implements the calculations from "Procedura Pomiarowa Porowatosci Skal przy
Uzyciu Helowego Miernika Porowatosci o Rozszerzonym Zakresie (HMPoRZ)":

  * daily hardware calibration of a reference cell (Vr, V_LIN, V_D)
    from the two-disc procedure, eqs. (4)-(11) of the procedure,
  * multi-point calibration with a selectable model - "quadratic"
    (the manual's equation, default), "linear" or "harmonic" - which is
    recorded in the result and reused by every measurement based on it,
  * porosity of core plugs from two Hassler-holder expansions (spacer
    discs alone, then the same discs plus the core), eqs. (14)-(15),
  * derived results: bulk volume, porosity and bulk density,
    eqs. (16)-(20),
  * export of the measured plugs as per-sample files for other toolkits
    (currently the gasperm gas-permeameter SAMPLE format).

Core plugs only; loose material (cuttings, ziarna) is not supported.

All interaction is file based (JSON in, JSON out):

    python -m porosimeter init      [directory]          # write example inputs
    python -m porosimeter calibrate input.json [-o out.json]
    python -m porosimeter measure   input.json [-o out.json]
    python -m porosimeter export    input.json [-o dir] [-f gasperm]

Requires Python 3.8+, standard library only.
"""

from .calibration import calibrate_cell, run_calibration
from .errors import InputError
from .export import (
    FORMATS,
    build_documents,
    render_gasperm,
    write_documents,
)
from .measurement import (
    load_calibration_reference,
    measure_sample,
    run_measurement,
)
from .physics import (
    MODELS,
    expanded_volume,
    expanded_volume_for,
    expansion_ratio,
    gas_volume,
    reference_pressure,
)
from .uncertainty import propagate

__version__ = "0.1.0"

__all__ = [
    "InputError",
    "MODELS",
    "expansion_ratio",
    "expanded_volume",
    "expanded_volume_for",
    "gas_volume",
    "reference_pressure",
    "propagate",
    "calibrate_cell",
    "run_calibration",
    "load_calibration_reference",
    "measure_sample",
    "run_measurement",
    "FORMATS",
    "build_documents",
    "render_gasperm",
    "write_documents",
]
