"""Collect graph artifacts from a loaded session payload."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from cv_zebrafish_rerum.paths_compat import resolve_graph_asset_path, resolve_folder_graphs_asset_paths


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    stem: str
    suffix: str
    source: str  # "single_csv" | "folder_graph"
    csv_id: str | None
    config_path: str | None
    folder_path: str | None
    folder_csv: str | None


@dataclass(frozen=True)
class UnresolvedRef:
    """A path string recorded in session.json that did not resolve to an existing file."""

    raw_path: str
    source: str  # human-readable location in JSON
    kind: str  # "single_csv_graph" | "folder_graph_asset"


def _suffix_kind(suffix: str) -> str:
    s = suffix.lower()
    if s == ".html":
        return "text/html"
    if s in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return f"image/{s.lstrip('.')}" if s != ".jpg" else "image/jpeg"
    return "application/octet-stream"


def encoding_format_for_path(path: str) -> str:
    return _suffix_kind(Path(path).suffix)


def load_session_dict(session_json_path: Path) -> dict[str, Any]:
    import json

    return json.loads(session_json_path.read_text(encoding="utf-8"))


def iter_artifacts(
    data: dict[str, Any],
    cv_root: Path,
    *,
    session_name: str,
) -> Iterator[ArtifactRecord]:
    """Yield resolved on-disk artifacts referenced by the session."""
    csvs = data.get("csvs") or {}
    for csv_id, configs in csvs.items():
        csv_resolved = resolve_graph_asset_path(csv_id, cv_root, session_name) or csv_id
        for config_path, graphs in (configs or {}).items():
            cfg_resolved = resolve_graph_asset_path(config_path, cv_root, session_name) or config_path
            for g in graphs or []:
                resolved = resolve_graph_asset_path(g, cv_root, session_name)
                if not resolved:
                    continue
                p = Path(resolved)
                yield ArtifactRecord(
                    path=resolved,
                    stem=p.stem,
                    suffix=p.suffix,
                    source="single_csv",
                    csv_id=str(csv_resolved),
                    config_path=str(cfg_resolved),
                    folder_path=None,
                    folder_csv=None,
                )

    folder_graphs = resolve_folder_graphs_asset_paths(
        data.get("folder_graphs") or {},
        cv_root,
        session_name,
    )
    for folder_path, cfgs in folder_graphs.items():
        for config_path, per_csv in cfgs.items():
            for csv_file, assets in per_csv.items():
                for a in assets:
                    pth = Path(a)
                    yield ArtifactRecord(
                        path=a,
                        stem=pth.stem,
                        suffix=pth.suffix,
                        source="folder_graph",
                        csv_id=None,
                        config_path=config_path,
                        folder_path=folder_path,
                        folder_csv=csv_file,
                    )


def iter_unresolved(
    data: dict[str, Any],
    cv_root: Path,
    *,
    session_name: str,
) -> Iterator[UnresolvedRef]:
    """Yield graph paths in session.json that do not resolve to an existing file."""
    csvs = data.get("csvs") or {}
    for csv_id, configs in csvs.items():
        for config_path, graphs in (configs or {}).items():
            for g in graphs or []:
                if not g or not isinstance(g, str):
                    continue
                if resolve_graph_asset_path(g, cv_root, session_name):
                    continue
                yield UnresolvedRef(
                    raw_path=g,
                    source=f"csvs → config graph ({csv_id[:48]}…)" if len(csv_id) > 48 else f"csvs → config graph ({csv_id})",
                    kind="single_csv_graph",
                )

    raw_fg = data.get("folder_graphs") or {}
    for folder_path, cfgs in raw_fg.items():
        for config_path, per_csv in (cfgs or {}).items():
            for csv_file, assets in (per_csv or {}).items():
                for a in assets or []:
                    if not a or not isinstance(a, str):
                        continue
                    if resolve_graph_asset_path(a, cv_root, session_name):
                        continue
                    yield UnresolvedRef(
                        raw_path=a,
                        source=f"folder_graphs / {Path(folder_path).name} / … / {Path(csv_file).name}",
                        kind="folder_graph_asset",
                    )


_OUTPUT_SUFFIXES = frozenset(
    {".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".csv"}
)


def _norm_key(p: Path) -> str:
    try:
        return str(p.resolve()).lower()
    except OSError:
        return str(p).lower()


def scan_orphan_files(
    session_json_path: Path,
    data: dict[str, Any],
    cv_root: Path,
    session_name: str,
    *,
    max_depth: int = 12,
) -> list[Path]:
    """
    Files under the session bundle folder that look like outputs but are not in the
    resolved artifact set (local ``leftover`` / unindexed outputs).
    """
    resolved = { _norm_key(Path(a.path)) for a in iter_artifacts(data, cv_root, session_name=session_name) }

    bundle = session_json_path.parent
    if not bundle.is_dir():
        return []

    uploads = bundle / "uploads"

    orphans: list[Path] = []
    seen: set[str] = set()

    # BFS with depth
    stack: list[tuple[Path, int]] = [(bundle, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            for child in cur.iterdir():
                if child.is_dir():
                    stack.append((child, depth + 1))
                    continue
                if uploads.is_dir():
                    try:
                        child.relative_to(uploads)
                        continue
                    except ValueError:
                        pass
                if child.name.lower() == "session.json":
                    continue
                suf = child.suffix.lower()
                if suf not in _OUTPUT_SUFFIXES:
                    continue
                nk = _norm_key(child)
                if nk in seen:
                    continue
                seen.add(nk)
                if nk in resolved:
                    continue
                orphans.append(child)
        except OSError:
            continue

    orphans.sort(key=lambda p: str(p).lower())
    return orphans
