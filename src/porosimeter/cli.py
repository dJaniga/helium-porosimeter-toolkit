"""
Command-line interface: the ``init`` / ``calibrate`` / ``measure`` commands
and JSON file input/output helpers.
"""

import argparse
import json
import os
import sys

from .calibration import run_calibration
from .errors import InputError
from .examples import write_examples
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="HMPoRZ helium porosimeter: reference-cell calibration "
                    "and core-plug pore-volume measurement, with JSON file "
                    "input/output.")
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

    args = parser.parse_args(argv)

    if args.command == "init":
        for path in write_examples(args.directory):
            print("wrote %s" % path)
        return 0

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
