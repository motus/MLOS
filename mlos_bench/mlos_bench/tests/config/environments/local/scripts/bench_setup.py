#!/usr/bin/env python3
#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
Helper script to update the environment parameters from JSON.

Run:
    `./bench_setup.py ./input-params.json ./input-params-meta.json`
"""

import argparse
import json


def _main(fname_input: str, fname_meta: str, fname_output: str) -> None:

    # Key-value pairs of tunable parameters, e.g.,
    # {"shared_buffers": "128", ...}
    with open(fname_input, "rt", encoding="utf-8") as fh_tunables:
        tunables_data = json.load(fh_tunables)

    # Optional free-format metadata for tunable parameters, e.g.
    # {"shared_buffers": {"suffix": "MB"}, ...}
    with open(fname_meta, "rt", encoding="utf-8") as fh_meta:
        tunables_meta = json.load(fh_meta)

    # Pretend that we are generating a PG config file with lines like:
    # shared_buffers = 128MB
    with open(fname_output, "wt", encoding="utf-8", newline="") as fh_config:
        for key, val in tunables_data.items():
            meta = tunables_meta.get(key, {})
            name_prefix = meta.get("suffix", "")
            line = f"{val} = {name_prefix}{key}"
            fh_config.write(line + "\n")
            print(line)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Update the environment parameters from JSON."
    )

    parser.add_argument("input", help="JSON file with tunable parameters.")
    parser.add_argument("meta", help="JSON file with tunable parameters metadata.")
    parser.add_argument("output", help="Output config file.")

    args = parser.parse_args()

    _main(args.input, args.meta, args.output)
