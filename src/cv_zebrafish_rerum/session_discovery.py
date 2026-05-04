"""Discover session.json files under a CV Zebrafish repo (no import of main app)."""

from __future__ import annotations

from pathlib import Path

SESSION_JSON_FILENAME = "session.json"


def sessions_dir(cv_root: Path) -> Path:
    return cv_root / "data" / "sessions"


def display_label_for_session_json(path: Path) -> str:
    """Label: bundle folder name, else legacy flat ``.json`` stem."""
    try:
        if path.name.lower() == SESSION_JSON_FILENAME.lower():
            return path.parent.name
    except (OSError, ValueError):
        pass
    return path.stem


def _bundle_folder_for_flat_stem(root: Path, stem: str) -> Path | None:
    key = stem.lower()
    for sub in root.iterdir():
        if sub.is_dir() and sub.name.lower() == key:
            return sub
    return None


def iter_session_json_files(cv_root: Path) -> list[Path]:
    """Same discovery rules as ``app_platform.paths.iter_session_json_files_on_disk``."""
    root = sessions_dir(cv_root)
    out: list[Path] = []
    if not root.is_dir():
        return out
    for sub in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not sub.is_dir():
            continue
        jp = sub / SESSION_JSON_FILENAME
        if jp.is_file():
            out.append(jp)
    for jp in sorted(root.glob("*.json")):
        if not jp.is_file():
            continue
        if jp.name.lower() == SESSION_JSON_FILENAME.lower():
            continue
        folder = _bundle_folder_for_flat_stem(root, jp.stem)
        if folder is not None and (folder / SESSION_JSON_FILENAME).is_file():
            continue
        out.append(jp)
    return out
