"""Shared helpers: load ArduPilot parameter metadata, parse .param files,
and classify parameters into flight phases.

Standard library only (Python 3.11+ for tomllib).

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
UPSTREAM_DIR = DATA_DIR / "upstream"
METADATA_FILE = UPSTREAM_DIR / "copter_params.json"
SOURCE_FILE = UPSTREAM_DIR / "SOURCE.json"
FRAME_PARAMS_DIR = UPSTREAM_DIR / "frame_params"
PHASE_MAP_FILE = DATA_DIR / "phase_map.toml"

PARAM_FILE_SUFFIXES = (".param", ".parm", ".params")

_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*[,\s]\s*([-+0-9.eE]+)\s*(?:[#;].*)?$")


# --------------------------------------------------------------------------
# Metadata
# --------------------------------------------------------------------------

def load_metadata(path: Path = METADATA_FILE) -> dict[str, dict]:
    """Return {PARAM_NAME: metadata dict} as written by fetch_upstream.py."""
    if not path.exists():
        raise SystemExit(
            f"Metadata not found at {path}.\n"
            "Run:  python ardupilot/tools/fetch_upstream.py"
        )
    with path.open(encoding="utf-8") as f:
        return json.load(f)["params"]


def load_source_info(path: Path = SOURCE_FILE) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def describe(meta: dict | None) -> str:
    """One-line human description of a parameter from its metadata."""
    if not meta:
        return ""
    text = meta.get("DisplayName", "")
    desc = meta.get("Description", "")
    if desc and desc != text:
        text = f"{text}. {desc}" if text else desc
    return " ".join(text.split())


def format_range(meta: dict | None) -> str:
    if not meta:
        return ""
    rng = meta.get("Range")
    if rng:
        return f"{rng.get('low', '')} .. {rng.get('high', '')}"
    values = meta.get("Values")
    if values:
        items = list(values.items())
        shown = ", ".join(f"{k}={v}" for k, v in items[:6])
        return shown + (", ..." if len(items) > 6 else "")
    if meta.get("Bitmask"):
        return "bitmask"
    return ""


def format_value(name: str, value: float, meta: dict | None) -> str:
    """Render a value, adding the enum label when there is one."""
    text = f"{value:g}"
    if meta and meta.get("Values"):
        label = meta["Values"].get(str(int(value))) if value == int(value) else None
        if label:
            text += f" ({label})"
    return text


# --------------------------------------------------------------------------
# Param files
# --------------------------------------------------------------------------

@dataclass
class ParamFile:
    path: Path
    params: dict[str, float]
    notes: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.stem


def parse_param_file(path: Path) -> ParamFile:
    """Parse Mission Planner / MAVProxy / QGC-style parameter files.

    Accepts `NAME,VALUE`, `NAME VALUE` and `NAME<TAB>VALUE`. Lines starting
    with `#` are comments (the first comments are kept as notes); lines
    starting with `@` (MAVProxy directives) are ignored. QGC's 5-column
    format (`sysid compid NAME VALUE type`) is also understood.
    """
    params: dict[str, float] = {}
    notes: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                note = line.lstrip("#").strip()
                if note and len(notes) < 5:
                    notes.append(note)
                continue
            if line.startswith("@"):
                continue
            parts = line.split()
            if len(parts) == 5 and parts[0].isdigit() and parts[1].isdigit():
                name, val = parts[2], parts[3]
            else:
                m = _LINE_RE.match(line)
                if not m:
                    continue
                name, val = m.group(1), m.group(2)
            try:
                params[name.upper()] = float(val)
            except ValueError:
                continue
    return ParamFile(path=path, params=params, notes=notes)


def find_param_files(root: Path = FRAME_PARAMS_DIR) -> list[Path]:
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in PARAM_FILE_SUFFIXES
    )


def resolve_frame(name_or_path: str) -> Path:
    """Accept a path, or a (partial, case-insensitive) upstream frame name."""
    p = Path(name_or_path)
    if p.exists():
        return p
    needle = name_or_path.lower()
    matches = [f for f in find_param_files() if needle in f.stem.lower()]
    exact = [f for f in matches if f.stem.lower() == needle]
    if exact:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"No param file or upstream frame matching '{name_or_path}'. "
                         "Try: python ardupilot/tools/compare_frames.py --list")
    names = ", ".join(m.stem for m in matches)
    raise SystemExit(f"'{name_or_path}' is ambiguous: {names}")


# --------------------------------------------------------------------------
# Phases
# --------------------------------------------------------------------------

@dataclass
class Phase:
    id: str
    title: str
    summary: str
    patterns: list[str]
    names: list[str]
    key_params: list[str]


class PhaseMap:
    def __init__(self, path: Path = PHASE_MAP_FILE):
        with path.open("rb") as f:
            raw = tomllib.load(f)
        self.phases = [Phase(**p) for p in raw["phase"]]
        self.by_id = {p.id: p for p in self.phases}
        self._explicit = {n: p.id for p in self.phases for n in p.names}
        self._compiled = [
            (re.compile(pat), len(pat), p.id)
            for p in self.phases for pat in p.patterns
        ]
        self.fallback = self.phases[-1].id

    def classify(self, name: str) -> str:
        name = name.upper()
        if name in self._explicit:
            return self._explicit[name]
        best_len, best = -1, self.fallback
        for rx, length, pid in self._compiled:
            if length > best_len and rx.match(name):
                best_len, best = length, pid
        return best

    def group(self, names) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {p.id: [] for p in self.phases}
        for n in sorted(names):
            out[self.classify(n)].append(n)
        return out


def known_fraction(pf: ParamFile, meta: dict) -> float:
    if not pf.params:
        return 0.0
    return sum(1 for n in pf.params if n in meta) / len(pf.params)


def is_copter_file(pf: ParamFile, meta: dict, threshold: float = 0.85) -> bool:
    """Upstream Frame_params also holds Plane/Rover/QuadPlane files. A file is
    treated as a Copter file when most of its names are Copter parameters."""
    return known_fraction(pf, meta) >= threshold


def suggest_names(name: str, meta: dict, n: int = 3) -> list[str]:
    """Close current names for an unknown (often renamed) parameter."""
    import difflib
    prefix = name.split("_")[0] + "_"
    pool = [k for k in meta if k.startswith(prefix)] or list(meta)
    return difflib.get_close_matches(name, pool, n=n, cutoff=0.6)


def out_of_range(value: float, meta: dict | None) -> bool:
    if not meta or "Range" not in meta:
        return False
    try:
        lo = float(meta["Range"]["low"])
        hi = float(meta["Range"]["high"])
    except (KeyError, ValueError):
        return False
    return not (lo <= value <= hi)


def md_escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")
