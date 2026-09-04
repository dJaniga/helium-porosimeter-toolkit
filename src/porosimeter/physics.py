"""
Core physics helpers: the Boyle's-law expansion term, the calibration
models and the reference pressure resolution.

Three models describe how the gas volume seen by the instrument grows with
the expansion ratio x = (R - P) / P.  All of them share the offset V_D (the
dead volume of the circuit), and all reduce to Boyle's law for small x:

    quadratic   V(x) = Vr*x + V_LIN*x^2 - V_D
    linear      V(x) = Vr*x             - V_D
    harmonic    V(x) = Vr*x/(1 + D*x)   - V_D

"quadratic" is the manual's equation (4) and stays the default.  Written as
an apparent reference volume Vr(x) = (V + V_D)/x the three read as
Vr + V_LIN*x, a constant Vr, and the harmonic decline Vr/(1 + D*x): D is a
decline constant per unit expansion ratio, and it comes out slightly
NEGATIVE for a cell whose apparent volume grows with expansion (the usual
case, V_LIN > 0), since to second order V_LIN = -Vr*D.
"""

from .errors import InputError

QUADRATIC = "quadratic"
LINEAR = "linear"
HARMONIC = "harmonic"
MODELS = (QUADRATIC, LINEAR, HARMONIC)

# Fitted parameters of each model, in report order.
MODEL_PARAMS = {
    QUADRATIC: ("Vr", "V_LIN", "V_D"),
    LINEAR: ("Vr", "V_D"),
    HARMONIC: ("Vr", "D", "V_D"),
}

# Calibration configurations needed to determine the model (= its parameter
# count); more points make the fit over-determined and the residuals useful.
MODEL_MIN_POINTS = {m: len(p) for m, p in MODEL_PARAMS.items()}

# The curvature parameter of each model - the second one, strongly
# anti-correlated with Vr, whose covariance with Vr has to be carried into
# the measurement.  The linear model has none.
MODEL_CURVATURE = {QUADRATIC: "V_LIN", LINEAR: None, HARMONIC: "D"}

# JSON key each parameter is reported and read under.
PARAM_KEYS = {"Vr": "Vr_cm3", "V_LIN": "V_LIN_cm3", "V_D": "V_D_cm3",
              "D": "D"}


def check_model(name, where):
    """Validate a model name coming from an input file."""
    if name is None:
        return QUADRATIC
    if name not in MODELS:
        raise InputError(
            '%s: unknown calibration model "%s" - use one of %s.'
            % (where, name, ", ".join('"%s"' % m for m in MODELS)))
    return name


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


def gas_volume(model, x, params):
    """
    Volume seen by the gas at expansion ratio x, excluding V_D, for the
    selected calibration model and its fitted `params`.
    """
    Vr = params["Vr"]
    if model == LINEAR:
        return Vr * x
    if model == HARMONIC:
        den = 1.0 + params["D"] * x
        if den <= 0.0:
            raise InputError(
                "Harmonic model evaluated outside its validity range "
                "(1 + D*x = %r must stay positive, at x = %r): the expansion "
                "ratio is far beyond the calibrated range." % (den, x))
        return Vr * x / den
    return Vr * x + params["V_LIN"] * x * x


def expanded_volume_for(model, R, P, params, offset=0.0):
    """`gas_volume` evaluated at the meter reading P."""
    return gas_volume(model, expansion_ratio(R, P, offset), params)


def expanded_volume(R, P, Vr, V_LIN, offset=0.0):
    """Vr*x + V_LIN*x^2 with x = (R-P)/P - the quadratic model."""
    return expanded_volume_for(QUADRATIC, R, P,
                               {"Vr": Vr, "V_LIN": V_LIN}, offset)


def equivalent_V_LIN(model, params):
    """
    The second-order coefficient of the model's Taylor expansion in x - the
    quantity comparable with the factory V_LIN whichever model was fitted
    (0 for the linear model, -Vr*D for the harmonic one).
    """
    if model == LINEAR:
        return 0.0
    if model == HARMONIC:
        return -params["Vr"] * params["D"]
    return params["V_LIN"]


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
