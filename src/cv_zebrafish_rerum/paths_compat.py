"""Resolve graph/config paths stored in session.json against a CV Zebrafish repo root.

Mirrors ``cv_zebrafish.src.app_platform.paths.resolve_graph_asset_path`` without importing PyQt.
"""

from __future__ import annotations

from pathlib import Path


def project_sessions_dir(cv_root: Path) -> Path:
    return cv_root / "data" / "sessions"


def resolve_graph_asset_path(
    stored_path_str: str,
    cv_root: Path,
    session_name: str | None = None,
) -> str | None:
    """Return an on-disk path for a graph/config file if it exists."""
    if not stored_path_str:
        return None
    p = Path(stored_path_str).expanduser()
    try:
        if p.is_file():
            return str(p.resolve())
    except OSError:
        if p.is_file():
            return str(p)

    _TOP = frozenset({"data", "configs", "assets", "src"})
    try:
        parts = p.parts
        idx = next(i for i, part in enumerate(parts) if part.lower() in _TOP)
        rel = Path(*parts[idx:])
        cand = cv_root / rel
        if cand.is_file():
            try:
                return str(cand.resolve())
            except OSError:
                return str(cand)
    except (StopIteration, OSError, ValueError):
        pass

    if session_name:
        bundle = project_sessions_dir(cv_root) / session_name
        name_lower = session_name.lower()
        try:
            for i, part in enumerate(p.parts):
                if part.lower() == name_lower:
                    tail = Path(*p.parts[i + 1 :])
                    if tail.parts:
                        cand = bundle / tail
                        if cand.is_file():
                            try:
                                return str(cand.resolve())
                            except OSError:
                                return str(cand)
                    break
        except (OSError, ValueError):
            pass
        cand = bundle / p.name
        if cand.is_file():
            try:
                return str(cand.resolve())
            except OSError:
                return str(cand)

    return None


def resolve_folder_graphs_asset_paths(
    folder_graphs: dict,
    cv_root: Path,
    session_name: str,
) -> dict:
    """Rebuild *folder_graphs* with assets re-pointed via :func:`resolve_graph_asset_path`."""
    out: dict = {}
    for folder_path, cfgs in (folder_graphs or {}).items():
        new_cfgs: dict = {}
        for config_path, per_csv in (cfgs or {}).items():
            new_per_csv: dict = {}
            for csv_file, assets in (per_csv or {}).items():
                new_assets: list = []
                for a in assets or []:
                    r = resolve_graph_asset_path(a, cv_root, session_name)
                    if r:
                        new_assets.append(r)
                if new_assets:
                    new_per_csv[csv_file] = new_assets
            if new_per_csv:
                new_cfgs[config_path] = new_per_csv
        if new_cfgs:
            out[folder_path] = new_cfgs
    return out


def infer_cv_root_from_session_json(session_json: Path) -> Path | None:
    """If ``session_json`` is ``…/<repo>/data/sessions/<name>/session.json``, return ``<repo>``."""
    try:
        p = session_json.resolve()
    except OSError:
        p = session_json
    parts = p.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].lower() == "sessions" and i >= 2:
            if parts[i - 1].lower() == "data":
                candidate = Path(*parts[: i - 1])
                if (candidate / "data" / "sessions").is_dir():
                    return candidate
    return None
