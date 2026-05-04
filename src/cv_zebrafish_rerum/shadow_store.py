"""Write JSON-LD bundles under gitignored ``shadow_store/``."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from cv_zebrafish_rerum.carry_forward_devlog import format_carry_forward_devlog
from cv_zebrafish_rerum.preview_emit import write_package_manifest, write_publication_preview
from cv_zebrafish_rerum.shadow_index import append_run


def _safe_slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip()).strip("_")
    return s[:80] if s else "session"


def write_run_bundle(
    *,
    repo_root: Path,
    session_name: str,
    session_json_path: Path,
    document: dict[str, Any],
    leftover_report: dict[str, Any] | None = None,
    resolved_artifacts: list[Any] | None = None,
    resolved_count: int = 0,
    unresolved_count: int = 0,
    orphan_count: int = 0,
) -> Path:
    """Write ``shadow_store/runs/<slug>_<short>/`` and update ``shadow_store/index.json``."""
    out_dir = repo_root / "shadow_store" / "runs"
    # Stable suffix: built-in hash() is salted per Python process and would create a new folder every run.
    key = session_json_path.resolve().as_posix().encode("utf-8")
    short = hashlib.sha256(key).hexdigest()[:8]
    run_folder_name = f"{_safe_slug(session_name)}_{short}"
    run_folder = out_dir / run_folder_name
    run_folder.mkdir(parents=True, exist_ok=True)
    dest = run_folder / "session_bundle.jsonld"
    dest.write_text(json.dumps(document, indent=2), encoding="utf-8")
    leftovers_present = bool(
        leftover_report
        and (
            leftover_report.get("leftovers_present")
            or leftover_report.get("has_uncategorized_carry_forward")
        )
    )
    companion_devlog = str((leftover_report or {}).get("companion_devlog") or "")
    meta = {
        "session_name": session_name,
        "session_json": str(session_json_path.resolve()),
        "graph_nodes": len(document.get("@graph") or []),
        "resolved_artifacts": resolved_count,
        "unresolved_references": unresolved_count,
        "orphan_files": orphan_count,
        "has_uncategorized_carry_forward": leftovers_present,
        "posting_readiness": (
            "JSON-LD alone is not enough to publish online: you still need (1) HTTPS-hosted artifact URLs "
            "or blob policy for the store, (2) Tiny Things / store registration + Bearer token when SLU approves POST, "
            "and (3) visibility review. This bundle's MediaObject nodes use file: URLs for offline audit; "
            "replace those with public HTTPS URLs in a publishing step. See package_manifest.json notes."
        ),
        "browser_preview_html": "publication_preview.html",
    }
    (run_folder / "ingest_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if leftover_report is not None:
        (run_folder / "leftover_report.json").write_text(
            json.dumps(leftover_report, indent=2),
            encoding="utf-8",
        )
        if leftovers_present:
            (run_folder / "companion_carry_forward_devlog.txt").write_text(
                format_carry_forward_devlog(leftover_report),
                encoding="utf-8",
            )
    append_run(
        repo_root,
        run_folder_name=run_folder_name,
        session_name=session_name,
        session_json=session_json_path,
        run_folder=run_folder,
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
        orphan_count=orphan_count,
        bundle_jsonld=dest,
    )
    resolved_list = resolved_artifacts if resolved_artifacts is not None else []
    if leftover_report is not None:
        write_package_manifest(
            run_folder,
            session_name=session_name,
            leftovers_present=leftovers_present,
            companion_devlog=companion_devlog,
            leftover_report=leftover_report,
        )
        write_publication_preview(
            run_folder,
            session_name=session_name,
            leftover_report=leftover_report,
            resolved=resolved_list,
            document=document,
        )
    return dest
