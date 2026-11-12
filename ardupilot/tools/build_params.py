#!/usr/bin/env python3
"""Build the parameter file to load onto the flight controller.

    final = reference frame file  +  my overlays (applied in name order)

The reference file is someone else's published, flown configuration (an
upstream ArduPilot Frame_params file). The overlays are small files with
only the values I change, each line carrying the reason:

    PILOT_SPD_UP,0.5    # indoor: slower climb so the 0.8 m target isn't overshot

Example:
  python ardupilot/tools/build_params.py ardupilot/my-quad
  python ardupilot/tools/build_params.py ardupilot/my-quad --out build/my-quad.param

The quad folder holds `base.txt` (one line: upstream frame name or path)
and `NN-*.param` overlays. Every name is checked against the ArduCopter
parameter documentation; unknown names and out-of-range values stop the
build unless --force is given.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apparams import (PhaseMap, format_value, load_metadata,  # noqa: E402
                      load_source_info, out_of_range, parse_param_file,
                      resolve_frame, suggest_names)

_REASON_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*[,\s]\s*([-+0-9.eE]+)\s*#\s*(.+)$")


def read_reasons(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _REASON_RE.match(line)
        if m:
            out[m.group(1).upper()] = m.group(3).strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quad_dir", type=Path, help="folder with base.txt and NN-*.param overlays")
    ap.add_argument("--out", type=Path, help="output .param (default: <quad_dir>/build/final.param)")
    ap.add_argument("--force", action="store_true", help="write even if checks fail")
    args = ap.parse_args()

    qd = args.quad_dir
    base_ref = (qd / "base.txt").read_text(encoding="utf-8").split("#")[0].strip()
    base = parse_param_file(resolve_frame(base_ref))
    overlays = sorted(qd.glob("[0-9][0-9]-*.param"))
    meta = load_metadata()
    phases = PhaseMap()

    final = dict(base.params)
    changes = []  # (overlay, name, old, new, reason)
    problems = []
    for ov in overlays:
        pf = parse_param_file(ov)
        reasons = read_reasons(ov)
        for name, val in pf.params.items():
            if name not in meta:
                sug = suggest_names(name, meta)
                problems.append(f"{ov.name}: {name} is not an ArduCopter parameter"
                                + (f" (did you mean {', '.join(sug)}?)" if sug else ""))
            elif out_of_range(val, meta[name]):
                r = meta[name]["Range"]
                problems.append(f"{ov.name}: {name}={val:g} outside {r['low']}..{r['high']}")
            if not reasons.get(name):
                problems.append(f"{ov.name}: {name} has no '# reason' comment")
            changes.append((ov.name, name, final.get(name), val, reasons.get(name, "")))
            final[name] = val

    for name, val in base.params.items():
        if name not in meta:
            sug = suggest_names(name, meta)
            problems.append(f"base: {name} is not in this firmware"
                            + (f" (renamed? {', '.join(sug)})" if sug else "")
                            + " - dropped from output")
        elif out_of_range(val, meta[name]) and final.get(name) == val:
            r = meta[name]["Range"]
            problems.append(f"base: {name}={val:g} outside the documented range "
                            f"{r['low']}..{r['high']} - kept (warning); override it in an overlay")
    final = {k: v for k, v in final.items() if k in meta or args.force}

    if problems:
        print("Checks:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        hard = [p for p in problems if "dropped" not in p and "(warning)" not in p]
        if hard and not args.force:
            raise SystemExit("Stopped. Fix the overlays or use --force.")

    out = args.out or qd / "build" / "final.param"
    out.parent.mkdir(parents=True, exist_ok=True)
    src = load_source_info()
    with out.open("w", encoding="utf-8") as f:
        f.write(f"# Built {dt.date.today()} from {qd}\n")
        f.write(f"# base: {base.path.name} ({src.get('firmware', '')})\n")
        f.write(f"# overlays: {', '.join(o.name for o in overlays)}\n")
        for name in sorted(final):
            f.write(f"{name},{final[name]:g}\n")

    print(f"Wrote {out}  ({len(final)} params: {len(base.params)} from base, "
          f"{len(changes)} set by overlays)\n")
    print("| Phase | Parameter | Base | Mine | Why |")
    print("|---|---|---|---|---|")
    for ovname, name, old, new, why in sorted(changes, key=lambda c: (phases.classify(c[1]), c[1])):
        m = meta.get(name)
        print(f"| {phases.by_id[phases.classify(name)].title} | {name} | "
              f"{'' if old is None else format_value(name, old, m)} | "
              f"{format_value(name, new, m)} | {why} |")


if __name__ == "__main__":
    main()
