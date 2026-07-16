"""
Core physics helpers: the Boyle's-law expansion term and the reference
pressure resolution.
"""

from .errors import InputError


def expansion_ratio(R, P, offset=0.0):
    """
    x = (R - P) / P, the expansion term used in every equation.

    `offset` is the transducer offset in meter units at ambient pressure
    (HP-41 program of the manual, register 15): it is subtracted from the
    raw meter reading before use.  With a properly zeroed meter it is 0.
    """
    P = P - offset
    if P <= 0:
        raise InputError("Pressure reading P must be positive (got %r "
                         "after offset correction)." % P)
    if P >= R:
        raise InputError(
            "Equilibrium pressure P (%r) must be lower than the reference "
            "pressure R (%r); check the readings." % (P, R))
    return (R - P) / P


def expanded_volume(R, P, Vr, V_LIN, offset=0.0):
    """Vr*x + V_LIN*x^2 with x = (R-P)/P — the volume seen by the gas."""
    x = expansion_ratio(R, P, offset)
    return Vr * x + V_LIN * x * x


def reference_pressure(block, offset=0.0):
    """
    Resolve the reference pressure R (meter counts = meter output at
    100 psig above ambient).

    Either given directly as the meter reading: {"R": 19836.0}
    (the offset is subtracted, since the panel meter shows R + offset),
    or from manual section 4.2:  R = T.S. x supply voltage x 100 psig,
    where T.S. = meter counts / 2400 @ 100 psig (manual section 4.1):
                                      {"transducer_sensitivity": 8.265,
                                       "supply_voltage": 24.0}
    """
    if not isinstance(block, dict):
        raise InputError('"reference_pressure" must be an object.')
    if block.get("R") is not None:
        R = float(block["R"]) - offset
    else:
        try:
            ts = float(block["transducer_sensitivity"])
            volts = float(block.get("supply_voltage", 24.0))
        except (KeyError, TypeError, ValueError):
            raise InputError(
                '"reference_pressure" needs either "R" or '
                '"transducer_sensitivity" (+ optional "supply_voltage").')
        R = ts * volts * 100.0  # section 4.2; computed value needs no offset
    if R <= 0:
        raise InputError("Reference pressure R must be positive.")
    return R
