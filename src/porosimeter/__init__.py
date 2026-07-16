"""
HMPoRZ helium porosimeter toolkit (Corexport Extended Range Helium Porosimeter).

Implements the calculations from "Procedura Pomiarowa Porowatosci Skal przy
Uzyciu Helowego Miernika Porowatosci o Rozszerzonym Zakresie (HMPoRZ)":

  * daily hardware calibration of a reference cell (Vr, V_LIN, V_D)
    from the two-disc procedure, eqs. (4)-(11) of the procedure,
  * grain-volume measurement with a matrix cup, eqs. (12)-(13),
  * pore-volume measurement with a Hassler core holder, eqs. (14)-(15),
  * derived results: bulk volume, grain density, bulk density, porosity,
    eqs. (16)-(20).

All interaction is file based (JSON in, JSON out):

    python -m porosimeter init      [directory]          # write example inputs
    python -m porosimeter calibrate input.json [-o out.json]
    python -m porosimeter measure   input.json [-o out.json]

Requires Python 3.8+, standard library only.
"""

from .calibration import calibrate_cell, run_calibration
from .errors import InputError
from .measurement import (
    load_calibration_reference,
    measure_sample,
    run_measurement,
)
from .physics import expanded_volume, expansion_ratio, reference_pressure
from .uncertainty import propagate

__version__ = "0.1.0"

__all__ = [
    "InputError",
    "expansion_ratio",
    "expanded_volume",
    "reference_pressure",
    "propagate",
    "calibrate_cell",
    "run_calibration",
    "load_calibration_reference",
    "measure_sample",
    "run_measurement",
]
