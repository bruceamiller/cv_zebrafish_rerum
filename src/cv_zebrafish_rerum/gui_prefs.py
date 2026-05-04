"""Persist lightweight GUI settings in the companion repo (gitignored)."""

from __future__ import annotations

import json
import os
from pathlib import Path

PREFS_FILENAME = "companion_gui_prefs.json"


def prefs_path(repo_root: Path) -> Path:
    return repo_root / PREFS_FILENAME


def load_startup_cv_root(repo_root: Path) -> str | None:
    """Restore last cv_zebrafish folder if it still exists; else honor ``CV_ZEBRAFISH_ROOT``."""
    pfile = prefs_path(repo_root)
    if pfile.is_file():
        try:
            data = json.loads(pfile.read_text(encoding="utf-8"))
            s = (data.get("cv_zebrafish_root") or "").strip()
            if s:
                cand = Path(s)
                if cand.is_dir():
                    return str(cand.resolve())
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    env = os.environ.get("CV_ZEBRAFISH_ROOT", "").strip()
    if env:
        ep = Path(env).expanduser()
        if ep.is_dir():
            return str(ep.resolve())
    return None


def persist_cv_zebrafish_root(repo_root: Path, cv_root_field: str) -> None:
    """Write last-used main-app clone path (no-op if empty or not a directory)."""
    raw = cv_root_field.strip()
    if not raw:
        return
    path = Path(raw)
    if not path.is_dir():
        return
    payload = {"version": 1, "cv_zebrafish_root": str(path.resolve())}
    dest = prefs_path(repo_root)
    try:
        dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass
