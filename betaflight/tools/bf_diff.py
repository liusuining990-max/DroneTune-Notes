#!/usr/bin/env python3
"""Compare two Betaflight CLI dumps, grouped by what they affect in flight.

Get a dump in Betaflight Configurator → CLI:  `diff all`  (or `dump`), then
save the text. Typical uses:

  # what did I change on top of the preset / stock tune I started from?
  python betaflight/tools/bf_diff.py stock.txt mine.txt

  # what changed between two sessions at the field?
  python betaflight/tools/bf_diff.py before.txt after.txt --section pid

Understands `set`, `feature`, `serial`, `aux`, `map`, `resource`, and the
`profile N` / `rateprofile N` blocks (settings inside them are reported as
`pid_profile 0: p_roll` etc.). Standard library only.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# (section, regex on the setting name). First match wins.
SECTIONS = [
    ("pid", r"^(p|i|d|f|d_min|d_max)_(roll|pitch|yaw)$|^(d_min|dmin|iterm|anti_gravity|feedforward|tpa|pidsum|simplified|throttle_boost|motor_output_limit|thrust_linear|vbat_sag)"),
    ("rates", r"^(roll|pitch|yaw)_(rc_rate|srate|expo|rate_limit)$|^(rates_type|rc_|thr_mid|thr_expo)"),
    ("filters", r"(lpf|notch|filter|rpm_|dyn_|gyro_|dterm_)"),
    ("motors-esc", r"^(motor_|dshot|min_throttle|max_throttle|min_command|digital_idle|idle_|esc_|beeper_dshot|yaw_motors_reversed)"),
    ("receiver", r"^(serialrx|rx_|rssi|rc_smoothing|failsafe|elrs|crsf|spektrum|sbus)"),
    ("vtx-osd", r"^(vtx_|vcd_|osd_|displayport)"),
    ("battery", r"^(vbat|ibata|current_|bat_|battery|cell)"),
    ("arming-modes", r"^(small_angle|auto_disarm|arm|runaway|mode_|crash_|deadband|yaw_deadband)"),
    ("board", r"^(align_|gyro_to_use|acc_|mag_|baro_|board_|imu)"),
]
_SECTION_RX = [(s, re.compile(p)) for s, p in SECTIONS]


def section_of(key: str) -> str:
    kind, _, name = key.partition(": ")
    if kind in ("feature", "serial", "aux", "map", "resource", "adjrange"):
        return {"serial": "receiver", "aux": "arming-modes", "map": "receiver"}.get(kind, "board")
    name = name or kind
    for sec, rx in _SECTION_RX:
        if rx.search(name):
            return sec
    return "other"


def parse_dump(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    scope = ""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        cmd = parts[0]
        if cmd == "profile" and len(parts) > 1:
            scope = f"pid_profile {parts[1]}"
        elif cmd == "rateprofile" and len(parts) > 1:
            scope = f"rate_profile {parts[1]}"
        elif cmd == "set":
            m = re.match(r"set\s+(\S+)\s*=\s*(.*)$", line)
            if m:
                name = m.group(1)
                key = f"{scope}: {name}" if scope else f"set: {name}"
                out[key] = m.group(2).strip()
        elif cmd == "feature" and len(parts) > 1:
            f = parts[1]
            out[f"feature: {f.lstrip('-')}"] = "off" if f.startswith("-") else "on"
        elif cmd in ("serial", "aux", "resource", "adjrange") and len(parts) > 2:
            out[f"{cmd}: {parts[1]}"] = " ".join(parts[2:])
        elif cmd == "map" and len(parts) > 1:
            out["map: channels"] = parts[1]
        elif cmd in ("board_name", "manufacturer_id"):
            out[f"board: {cmd}"] = " ".join(parts[1:])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path, help="first dump (reference)")
    ap.add_argument("b", type=Path, help="second dump")
    ap.add_argument("--section", help="only one section: " + ", ".join(s for s, _ in SECTIONS))
    args = ap.parse_args()

    A, B = parse_dump(args.a), parse_dump(args.b)
    rows: dict[str, list] = {}
    for key in sorted(set(A) | set(B)):
        va, vb = A.get(key), B.get(key)
        if va == vb:
            continue
        sec = section_of(key)
        if args.section and sec != args.section:
            continue
        rows.setdefault(sec, []).append((key.replace("set: ", ""), va or "(default)", vb or "(default)"))

    print(f"# {args.a.name} vs {args.b.name}\n")
    if not rows:
        print("No differences.")
        return
    order = [s for s, _ in SECTIONS] + ["other"]
    for sec in sorted(rows, key=order.index):
        print(f"## {sec}\n")
        print(f"| Setting | {args.a.name} | {args.b.name} |")
        print("|---|---|---|")
        for k, va, vb in rows[sec]:
            print(f"| {k} | {va} | {vb} |")
        print()
    print("`(default)` = not present in that dump. A `diff all` only lists values that "
          "differ from firmware defaults; compare two `dump` files to see every value.")


if __name__ == "__main__":
    main()
