#!/usr/bin/env python3
"""Compare two parameter files, grouped by flight phase.

Typical uses:
  # what did I change compared with the reference frame I started from?
  python ardupilot/tools/diff_params.py Holybro-S500 my_quad.param

  # what did AutoTune change?
  python ardupilot/tools/diff_params.py before_autotune.param after_autotune.param

  # only the attitude loop
  python ardupilot/tools/diff_params.py a.param b.param --phase 05-attitude-stabilize

Each side may be a file path or an upstream frame name.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apparams import (PhaseMap, describe, format_value, load_metadata,  # noqa: E402
                      md_escape, parse_param_file, resolve_frame)


def pct(a: float, b: float) -> str:
    if a == 0:
        return ""
    return f"{(b - a) / abs(a) * 100:+.0f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", help="first (reference) file or frame name")
    ap.add_argument("b", help="second file or frame name")
    ap.add_argument("--phase", help="only show one phase id")
    ap.add_argument("--only-changed", action="store_true",
                    help="hide parameters that exist in only one file")
    args = ap.parse_args()

    meta = load_metadata()
    phases = PhaseMap()
    A = parse_param_file(resolve_frame(args.a))
    B = parse_param_file(resolve_frame(args.b))

    names = set(A.params) | set(B.params)
    grouped = phases.group(names)
    print(f"# {A.name} vs {B.name}\n")
    total = 0
    for phase in phases.phases:
        if args.phase and phase.id != args.phase:
            continue
        rows = []
        for n in grouped[phase.id]:
            a, b = A.params.get(n), B.params.get(n)
            if a is not None and b is not None:
                if math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9):
                    continue
                change = pct(a, b)
            elif args.only_changed:
                continue
            else:
                change = "only in " + (A.name if b is None else B.name)
            m = meta.get(n)
            rows.append((n, "" if a is None else format_value(n, a, m),
                         "" if b is None else format_value(n, b, m),
                         change, (m or {}).get("Units", ""), describe(m)))
        if not rows:
            continue
        total += len(rows)
        print(f"## {phase.title}\n")
        print(f"| Parameter | {md_escape(A.name)} | {md_escape(B.name)} | Change | Units | Meaning |")
        print("|---|---|---|---|---|---|")
        for r in rows:
            print("| " + " | ".join(md_escape(x) for x in r) + " |")
        print()
    if total == 0:
        print("No differences.")


if __name__ == "__main__":
    main()
