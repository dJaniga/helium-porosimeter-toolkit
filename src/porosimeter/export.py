"""
Export measured core plugs as sample files for other tools.

The porosimeter measures the rock; other rigs measure the same plug and need
the same provenance and geometry.  The "export" command writes one sample
file per plug in the format those tools expect, so a number never has to be
retyped between them.

Currently one target format:

  "gasperm"  the per-plug SAMPLE configuration of the gas-permeameter
             toolkit - a commented YAML file per plug.  Only "length" and
             "diameter" enter its Darcy calculation; porosity, bulk and
             grain density are carried as provenance.

The export takes a measurement input file (the same one "measure" takes):
the plug geometry, provenance and uncertainties live there, and the derived
porosity and densities are computed on the way out.  A measurement *result*
file also works, but it no longer knows the caliper dimensions - only the
bulk volume they produced - so the geometry fields come out empty.
"""

import os
import re
from datetime import datetime

from .constants import DEFAULT_MEAS_UNCERTAINTIES
from .errors import InputError

FORMATS = ("gasperm",)

# Sample keys that are provenance only: copied through to the exported file
# without ever touching a calculation.  "depth_unit" is the unit of "depth".
PROVENANCE_KEYS = ("description", "lithology", "formation", "well", "depth",
                   "depth_unit", "prepared_by", "prepared_on", "notes")


# ---------------------------------------------------------------------------
# Minimal YAML scalar emitter (the toolkit is standard library only)
# ---------------------------------------------------------------------------
_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ./+-]*$")


def _fmt_number(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = "%.6f" % value
    text = text.rstrip("0").rstrip(".")
    return text or "0"


def _scalar(value):
    """One YAML scalar: numbers plain, empty and risky strings quoted."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _fmt_number(value)
    text = str(value)
    if text and _PLAIN.match(text) and text.lower() not in (
            "null", "true", "false", "yes", "no", "on", "off"):
        return text
    return "'%s'" % text.replace("'", "''")


def _line(key, value, comment=None, pad=44):
    text = "%s: %s" % (key, _scalar(value))
    if comment:
        text = "%-*s# %s" % (pad, text, comment)
    return text.rstrip()


# ---------------------------------------------------------------------------
# Field collection
# ---------------------------------------------------------------------------
def _uncertainties(data, sample):
    u = dict(DEFAULT_MEAS_UNCERTAINTIES)
    u.update(data.get("uncertainties", {}) or {})
    u.update(sample.get("uncertainties", {}) or {})
    return u


def _geometry(sample):
    """
    Caliper dimensions of the plug, in cm.  A bulk volume given as a ready
    made value carries no dimensions, and gasperm needs both, so the export
    says so instead of inventing them from the volume.
    """
    bulk = sample.get("bulk_volume") or {}
    if "diameter_cm" in bulk and "length_cm" in bulk:
        return float(bulk["length_cm"]), float(bulk["diameter_cm"]), None
    return None, None, (
        "no caliper dimensions in the input (the bulk volume was given "
        "directly) - fill in length and diameter before running gasperm")


def gasperm_fields(sample, result, data):
    """
    Map one measured plug onto the gasperm SAMPLE fields.  `sample` is its
    measurement input record (empty when exporting from a result file),
    `result` the matching entry of the measurement result.  Returns
    (fields, warnings).
    """
    warnings = []
    meta = data.get("meta", {}) or {}
    derived = result.get("results", {})
    u = _uncertainties(data, sample)
    length, diameter, geom_warning = _geometry(sample)
    if geom_warning:
        warnings.append(geom_warning)

    def provenance(key, default=""):
        value = sample.get(key)
        return default if value is None else value

    # Grain density is the dry mass over the grain volume the two holder
    # readings measured directly - the one quantity here that no later rig
    # can recover from the porosity alone.
    mass = result.get("dry_mass_g")
    V_g = (result.get("core_holder") or {}).get("V_g_cm3")
    grain_density = ""
    if mass is not None and V_g is not None:
        if V_g > 0:
            grain_density = round(float(mass) / float(V_g), 4)
        else:
            warnings.append(
                "grain volume is not positive - grain density left empty")

    porosity = derived.get("porosity_pct")
    if porosity is None:
        warnings.append(
            "no porosity in the result - porosity_fraction is null")

    return {
        "id": result.get("sample_id", "?"),
        "description": provenance("description"),
        "lithology": provenance("lithology", "N/A"),
        "formation": provenance("formation", "N/A"),
        "well": provenance("well", "N/A"),
        "depth": sample.get("depth"),
        "depth_unit": provenance("depth_unit", "m"),
        "dimension_unit": "cm",
        "length": length,
        "diameter": diameter,
        "length_uncertainty": float(u["length_cm"]),
        "diameter_uncertainty": float(u["diameter_cm"]),
        "porosity_fraction": (None if porosity is None
                              else round(porosity / 100.0, 5)),
        "porosity_method": "Helium porosity",
        "grain_density_g_cm3": grain_density,
        "bulk_density_g_cm3": derived.get("bulk_density_g_cm3", ""),
        "prepared_by": (sample.get("prepared_by")
                        or meta.get("operator") or ""),
        "prepared_on": sample.get("prepared_on") or meta.get("date"),
        "notes": provenance("notes"),
    }, warnings


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def render_gasperm(fields, source=None):
    """The commented YAML document for one plug."""
    origin = "helium-porosimeter-toolkit"
    if source:
        origin += ", from %s" % source
    return "\n".join([
        "# gasperm -- SAMPLE configuration (the core plug)",
        "#",
        "# Written by %s" % origin,
        "# on %s.  Confining pressure and working gas are not"
        % datetime.now().strftime("%Y-%m-%d %H:%M"),
        "# here: the same plug is routinely measured at several of each, so",
        "# they belong to run.yaml.",
        "#",
        "# Only length and diameter enter the Darcy calculation. Everything",
        "# else is provenance, carried into every run so a number stays",
        "# traceable to a rock.",
        "",
        _line("id", fields["id"]),
        _line("description", fields["description"]),
        _line("lithology", fields["lithology"]),
        _line("formation", fields["formation"]),
        _line("well", fields["well"]),
        _line("depth", fields["depth"]),
        _line("depth_unit", fields["depth_unit"], "m | ft"),
        "",
        "# Geometry -- the only part of this file the physics uses. Every",
        "# dimension below is in dimension_unit; the calculation converts to",
        "# cm internally. Area goes as diameter^2, so the diameter",
        "# uncertainty enters the budget doubled.",
        _line("dimension_unit", fields["dimension_unit"], "cm, ft, in, m, mm"),
        _line("length", fields["length"], "caliper, cm"),
        _line("diameter", fields["diameter"], "caliper, cm"),
        _line("length_uncertainty", fields["length_uncertainty"],
              "standard uncertainty, cm"),
        _line("diameter_uncertainty", fields["diameter_uncertainty"],
              "standard uncertainty, cm -- counts double"),
        "",
        "# Petrophysics. Informational; not used by the Darcy calc.",
        _line("porosity_fraction", fields["porosity_fraction"]),
        _line("porosity_method", fields["porosity_method"],
              "helium pycnometry, MICP, image analysis, ..."),
        _line("grain_density_g_cm3", fields["grain_density_g_cm3"],
              "dry mass / measured grain volume"),
        _line("bulk_density_g_cm3", fields["bulk_density_g_cm3"]),
        "",
        "# Provenance.",
        _line("prepared_by", fields["prepared_by"]),
        _line("prepared_on", fields["prepared_on"], "YYYY-MM-DD"),
        _line("notes", fields["notes"]),
        "",
    ])


def _filename(sample_id, taken):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(sample_id)).strip("_.")
    stem = stem or "sample"
    name = stem + ".yaml"
    n = 2
    while name.lower() in taken:
        name = "%s_%d.yaml" % (stem, n)
        n += 1
    taken.add(name.lower())
    return name


def build_documents(data, result, fmt="gasperm", source=None):
    """
    Render every measured plug.  Returns a list of
    {"filename", "sample_id", "text", "warnings"} in input order.
    """
    if fmt not in FORMATS:
        raise InputError('Unknown export format "%s" (known: %s).'
                         % (fmt, ", ".join(FORMATS)))
    results = result.get("samples") or []
    if not results:
        raise InputError("Nothing to export: the measurement has no samples.")
    raw = data.get("samples") or []
    # A result file carries no raw records; a measurement input has one per
    # result, in the same order.
    if len(raw) != len(results):
        raw = [{}] * len(results)

    documents, taken = [], set()
    for sample, res in zip(raw, results):
        fields, warnings = gasperm_fields(sample, res, data)
        documents.append({
            "filename": _filename(fields["id"], taken),
            "sample_id": fields["id"],
            "text": render_gasperm(fields, source),
            "warnings": list(res.get("warnings", [])) + warnings,
        })
    return documents


def write_documents(documents, directory):
    """Write rendered documents into `directory`; returns their paths."""
    os.makedirs(directory, exist_ok=True)
    paths = []
    for doc in documents:
        path = os.path.join(directory, doc["filename"])
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(doc["text"])
        paths.append(path)
    return paths
