#!/usr/bin/env python3
"""Explain a parameter file, grouped by flight phase.

Examples:
  python ardupilot/tools/classify.py my_quad.param
  python ardupilot/tools/classify.py Hexsoon-edu450               # an upstream frame
  python ardupilot/tools/classify.py my_quad.param --phase 07-altitude-hold
  python ardupilot/tools/classify.py my_quad.param --format csv > my_quad.csv

For every parameter it prints the value (with the enum label when there is
one), units, the official ArduPilot description and allowed range. It
also flags values outside the documented range, and names that this
firmware does not know (usually renamed in a newer release) with the
closest current names.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apparams import (PhaseMap, describe, format_range, format_value,  # noqa: E402
                      load_metadata, load_source_info, md_escape, out_of_range,
                      parse_param_file, resolve_frame, suggest_names)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("param_file", help="path to a .param/.parm file, or an upstream frame name")
    ap.add_argument("--phase", help="only show one phase id (e.g. 05-attitude-stabilize)")
    ap.add_argument("--format", choices=["md", "csv"], default="md")
    ap.add_argument("-o", "--output", type=Path, help="write to a file instead of stdout")
    args = ap.parse_args()

    meta = load_metadata()
    phases = PhaseMap()
    pf = parse_param_file(resolve_frame(args.param_file))
    if args.phase and args.phase not in phases.by_id:
        raise SystemExit(f"Unknown phase '{args.phase}'. Options: {', '.join(phases.by_id)}")

    grouped = phases.group(pf.params)
    out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        if args.format == "csv":
            w = csv.writer(out)
            w.writerow(["phase", "name", "value", "units", "range", "flag", "description"])
            for pid, names in grouped.items():
                if args.phase and pid != args.phase:
                    continue
                for n in names:
                    m = meta.get(n)
                    v = pf.params[n]
                    flag = ("unknown" if m is None
                            else "out_of_range" if out_of_range(v, m) else "")
                    w.writerow([pid, n, format_value(n, v, m), (m or {}).get("Units", ""),
                                format_range(m), flag, describe(m)])
            return

        src = load_source_info()
        print(f"# {pf.name}\n", file=out)
        if pf.notes:
            print("> " + "\n> ".join(pf.notes) + "\n", file=out)
        print(f"{len(pf.params)} parameters, checked against "
              f"{src.get('firmware', 'ArduCopter')} metadata "
              f"(ArduPilot `{src.get('commit', '?')[:10]}`).\n", file=out)

        unknown = [n for n in pf.params if n not in meta]
        bad = [n for n in pf.params if n in meta and out_of_range(pf.params[n], meta[n])]
        if unknown or bad:
            print("## Warnings\n", file=out)
            for n in unknown:
                sug = suggest_names(n, meta)
                hint = f" Closest current names: {', '.join(f'`{s}`' for s in sug)}." if sug else ""
                print(f"- `{n}` is not a parameter in this firmware "
                      f"(renamed, removed, or for another vehicle).{hint} "
                      "Check units before copying the value.", file=out)
            for n in bad:
                print(f"- `{n}` = {pf.params[n]:g} is outside the documented range "
                      f"{format_range(meta[n])}.", file=out)
            print(file=out)

        for phase in phases.phases:
            names = grouped[phase.id]
            if not names or (args.phase and phase.id != args.phase):
                continue
            print(f"## {phase.title}\n\n_{phase.summary}_\n", file=out)
            print("| Parameter | Value | Units | Range | Meaning |", file=out)
            print("|---|---|---|---|---|", file=out)
            for n in names:
                m = meta.get(n)
                v = pf.params[n]
                name = f"**{n}**" if n in phase.key_params else n
                print(f"| {name} | {md_escape(format_value(n, v, m))} | "
                      f"{md_escape((m or {}).get('Units', ''))} | "
                      f"{md_escape(format_range(m))} | "
                      f"{md_escape(describe(m) or 'not in this firmware')} |", file=out)
            print(file=out)
    finally:
        if args.output:
            out.close()


if __name__ == "__main__":
    main()
