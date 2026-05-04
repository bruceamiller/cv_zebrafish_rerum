"""Append-only index of shadow_store runs (offline catalog)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def index_path(repo_root: Path) -> Path:
    return repo_root / "shadow_store" / "index.json"


def load_index(repo_root: Path) -> dict[str, Any]:
    p = index_path(repo_root)
    if not p.is_file():
        return {"version": 1, "runs": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_index(repo_root: Path, data: dict[str, Any]) -> None:
    p = index_path(repo_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_run(
    repo_root: Path,
    *,
    run_folder_name: str,
    session_name: str,
    session_json: Path,
    run_folder: Path,
    resolved_count: int,
    unresolved_count: int,
    orphan_count: int,
    bundle_jsonld: Path,
) -> None:
    idx = load_index(repo_root)
    runs: list[dict[str, Any]] = list(idx.get("runs") or [])
    entry = {
        "id": run_folder_name,
        "session_name": session_name,
        "session_json": str(session_json.resolve()),
        "run_folder": str(run_folder.resolve()),
        "bundle_jsonld": str(bundle_jsonld.resolve()),
        "created": datetime.now(timezone.utc).isoformat(),
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "orphan_count": orphan_count,
        "transport": "local_shadow_only",
    }
    # Replace existing entry with same id (re-ingest same session hash slot)
    runs = [r for r in runs if r.get("id") != entry["id"]]
    runs.insert(0, entry)
    idx["runs"] = runs
    save_index(repo_root, idx)
