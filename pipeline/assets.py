"""Helpers that make generation stages idempotent.

Each generated asset ``<dir>/<id>.<ext>`` has a sidecar ``<dir>/<id>.json``
holding a fingerprint of its inputs. An asset counts as done only if the file
exists and the fingerprint matches, so editing a prompt regenerates just that
shot and re-running a stage skips everything else.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_SKIP_SUFFIXES = {".json", ".part"}


def fingerprint(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def find_asset(folder: Path, stem: str) -> Path | None:
    if not folder.exists():
        return None
    for p in sorted(folder.glob(f"{stem}.*")):
        if p.suffix not in _SKIP_SUFFIXES and p.name.split(".")[0] == stem:
            return p
    return None


def read_sidecar(folder: Path, stem: str) -> dict | None:
    p = folder / f"{stem}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def is_current(folder: Path, stem: str, fp: str) -> bool:
    side = read_sidecar(folder, stem)
    return bool(side and side.get("fingerprint") == fp and find_asset(folder, stem))


def write_sidecar(folder: Path, stem: str, data: dict) -> None:
    (folder / f"{stem}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_asset(folder: Path, stem: str) -> None:
    """Remove a stale asset (any extension) before regenerating it."""
    old = find_asset(folder, stem)
    while old is not None:
        old.unlink()
        old = find_asset(folder, stem)
