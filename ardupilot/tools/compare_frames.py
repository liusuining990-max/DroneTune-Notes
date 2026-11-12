#!/usr/bin/env python3
"""Compare parameters across the upstream reference airframes.

Examples:
  python ardupilot/tools/compare_frames.py --list
  python ardupilot/tools/compare_frames.py --phase 05-attitude-stabilize
  python ardupilot/tools/compare_frames.py --params ATC_RAT_RLL_P,ATC_RAT_RLL_D,MOT_THST_HOVER
  python ardupilot/tools/compare_frames.py --phase 05-attitude-stabilize \
      --frames edu450,S500,X500 --add my_quad.param
  python ardupilot/tools/compare_frames.py --phase 01-frame-motors --format csv

By default the columns are the phase's key parameters and the rows are all
upstream Copter frames. A summary row (min / median / max) shows the range
real airframes use, which is a sensible starting window for your own tune.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apparams import (FRAME_PARAMS_DIR, PhaseMap, find_param_files,  # noqa: E402
                      is_copter_file, known_fraction, load_metadata, md_escape,
                      parse_param_file, resolve_frame)


def copter_frames(meta: dict, wanted: list[str] | None = None):
    frames = [parse_param_file(p) for p in find_param_files()]
    frames = [f for f in frames if is_copter_file(f, meta)]
    if wanted:
        keep = []
        for w in wanted:
            hits = [f for f in frames if w.lower() in f.name.lower()]
            if not hits:
                raise SystemExit(f"No upstream Copter frame matches '{w}' (see --list)")
            keep += [h for h in hits if h not in keep]
        frames = keep
    return frames


def summary(values: list[float]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return f"{values[0]:g}"
    return f"{min(values):g} / {statistics.median(values):g} / {max(values):g}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list upstream frame files and exit")
    ap.add_argument("--phase", help="use this phase's key parameters as columns")
    ap.add_argument("--params", help="comma-separated parameter names (overrides --phase)")
    ap.add_argument("--frames", help="comma-separated (partial) frame names to include")
    ap.add_argument("--add", action="append", default=[], type=Path,
                    help="add your own param file as an extra row (repeatable)")
    ap.add_argument("--format", choices=["md", "csv"], default="md")
    args = ap.parse_args()

    meta = load_metadata()
    phases = PhaseMap()

    if args.list:
        print("| File | Params | Known to this Copter firmware | Used for comparisons |")
        print("|---|---|---|---|")
        for p in find_param_files():
            pf = parse_param_file(p)
            print(f"| {p.relative_to(FRAME_PARAMS_DIR)} | {len(pf.params)} | "
                  f"{known_fraction(pf, meta):.0%} | "
                  f"{'yes' if is_copter_file(pf, meta) else 'no (other vehicle)'} |")
        return

    if args.params:
        cols = [c.strip().upper() for c in args.params.split(",") if c.strip()]
    elif args.phase:
        if args.phase not in phases.by_id:
            raise SystemExit(f"Unknown phase. Options: {', '.join(phases.by_id)}")
        cols = phases.by_id[args.phase].key_params
    else:
        raise SystemExit("Give --phase, --params or --list")

    frames = copter_frames(meta, args.frames.split(",") if args.frames else None)
    extra = [parse_param_file(resolve_frame(str(p))) for p in args.add]

    # Drop columns no frame sets, so tables stay readable.
    rows = frames + extra
    cols = [c for c in cols if any(c in f.params for f in rows)] or cols

    def cell(f, c):
        v = f.params.get(c)
        return "" if v is None else f"{v:g}"

    stats = [summary([f.params[c] for f in frames if c in f.params]) for c in cols]

    if args.format == "csv":
        w = csv.writer(sys.stdout)
        w.writerow(["frame"] + cols)
        for f in rows:
            w.writerow([f.name] + [cell(f, c) for c in cols])
        w.writerow(["min / median / max (upstream)"] + stats)
        return

    print("| Frame | " + " | ".join(cols) + " |")
    print("|---|" + "---|" * len(cols))
    for f in rows:
        label = f"**{f.name}** (yours)" if f in extra else f.name
        print(f"| {md_escape(label)} | " + " | ".join(cell(f, c) for c in cols) + " |")
    print("| _min / median / max_ | " + " | ".join(f"_{s}_" if s else "" for s in stats) + " |")
    units = [meta.get(c, {}).get("Units", "") for c in cols]
    if any(units):
        print("\nUnits: " + ", ".join(f"{c} [{u}]" for c, u in zip(cols, units) if u))
    print("\nBlank = the frame file leaves this at the firmware default.")


if __name__ == "__main__":
    main()
