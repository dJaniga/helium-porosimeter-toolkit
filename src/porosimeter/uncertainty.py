"""
Uncertainty propagation (GUM, numerical sensitivities).

See JCGM 100:2008 (GUM) for the first-order propagation method.
"""

import math

from .errors import InputError


def propagate(f, vals, u, y0):
    """
    First-order GUM propagation with numerical (central) differences.

    f      : function dict->dict evaluating all outputs from inputs `vals`
    u      : dict of standard uncertainties per input (step size = u)
    y0     : nominal outputs, f(vals)
    Returns (u_y, sens): combined standard uncertainty per output assuming
    independent inputs, and per-input contributions dy_i = (dy/dx_i)*u_i
    (needed for covariance cross-terms added by the caller).
    """
    sens = {}
    for name, un in u.items():
        un = float(un)
        if un == 0.0 or name not in vals:
            continue
        d = None
        try:
            yp = f(dict(vals, **{name: vals[name] + un}))
            ym = f(dict(vals, **{name: vals[name] - un}))
            d = {k: (yp[k] - ym[k]) / 2.0
                 for k in y0 if k in yp and k in ym}
        except InputError:
            try:  # one-sided fallback near a validity boundary
                yp = f(dict(vals, **{name: vals[name] + un}))
                d = {k: yp[k] - y0[k] for k in y0 if k in yp}
            except InputError:
                d = None
        if d:
            sens[name] = d
    u_y = {}
    for k in y0:
        var = sum(d.get(k, 0.0) ** 2 for d in sens.values())
        u_y[k] = math.sqrt(var)
    return u_y, sens
