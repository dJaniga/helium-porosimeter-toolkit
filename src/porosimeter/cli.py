"""
Command-line interface: the ``init`` / ``calibrate`` / ``measure`` /
``export`` commands and JSON file input/output helpers.
"""

import argparse
import json
import os
import sys

from .calibration import run_calibration
from .errors import InputError
from .examples import write_examples
from .export import (
    DEFAULT_DIMENSION_UNIT,
    DIMENSION_UNITS,
    FORMATS,
    build_documents,
    write_documents,
)
from .measurement import run_measurement
from .reporting import print_summary


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def default_output(input_path):
    stem, _ = os.path.splitext(input_path)
    return stem.replace("_input", "") + "_result.json"


def default_export_dir(input_path):
    stem, _ = os.path.splitext(input_path)
    for suffix in ("_input", "_result"):
        stem = stem.replace(suffix, "")
    return stem + "_samples"


def run_export(args):
    """Measure (or re-read) the samples and write one file per plug."""
    base_dir = os.path.dirname(os.path.abspath(args.input))
    data = load_json(args.input)
    if data.get("type") == "measurement_result":
        # Already reduced: export what it holds.  Such a file no longer
        # carries the caliper dimensions, so the export flags them.
        result = data
    else:
        result = run_measurement(data, base_dir)

    documents = build_documents(data, result, args.format,
                                os.path.basename(args.input), args.unit)
    directory = args.output or default_export_dir(args.input)
    paths = write_documents(documents, directory)
    for doc, path in zip(documents, paths):
        print("wrote %s" % path)
        for warning in doc["warnings"]:
            print("    WARNING: %s" % warning)
    print("\n%d sample file(s) in %s format written to %s"
          % (len(paths), args.format, directory))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="HMPoRZ helium porosimeter: reference-cell calibration "
                    "and core-plug pore-volume measurement, with JSON file "
                    "input/output, and export of the measured plugs as "
                    "sample files for other toolkits.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="write example input JSON files")
    p_init.add_argument("directory", nargs="?", default="examples")

    for name, help_text in (
            ("calibrate", "compute Vr, V_LIN, V_D from a calibration input"),
            ("measure", "compute pore volume, porosity and bulk density")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("input", help="input JSON file")
        p.add_argument("-o", "--output",
                       help="output JSON file (default: <input>_result.json)")

    p_export = sub.add_parser(
        "export",
        help="write the measured core plugs as sample files for another "
             "toolkit")
    p_export.add_argument(
        "input",
        help="measurement input JSON (preferred: only it carries the "
             "provenance keys) or a measurement result JSON")
    p_export.add_argument(
        "-o", "--output", metavar="DIR",
        help="output directory (default: <input>_samples)")
    p_export.add_argument(
        "-f", "--format", choices=FORMATS, default=FORMATS[0],
        help="target format (default: %s)" % FORMATS[0])
    p_export.add_argument(
        "-u", "--unit", choices=sorted(DIMENSION_UNITS),
        default=DEFAULT_DIMENSION_UNIT,
        help="unit for the plug dimensions, written into the file as "
             "\"dimension_unit\" (default: %s)" % DEFAULT_DIMENSION_UNIT)

    args = parser.parse_args(argv)

    if args.command == "init":
        for path in write_examples(args.directory):
            print("wrote %s" % path)
        return 0

    if args.command == "export":
        try:
            return run_export(args)
        except InputError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        except (OSError, json.JSONDecodeError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2

    try:
        data = load_json(args.input)
        if args.command == "calibrate":
            result = run_calibration(data)
        else:
            result = run_measurement(data, os.path.dirname(
                os.path.abspath(args.input)))
    except InputError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    out_path = args.output or default_output(args.input)
    save_json(out_path, result)
    print_summary(result)
    print("\nresult written to %s" % out_path)
    return 0
