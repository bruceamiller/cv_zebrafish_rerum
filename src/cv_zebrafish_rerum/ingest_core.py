"""High-level ingest/analyze API for CLI and GUI (no network)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cv_zebrafish_rerum.jsonld_emit import build_session_graph
from cv_zebrafish_rerum.manifest_check import check_session_keys, compatibility_note, load_manifest
from cv_zebrafish_rerum.session_payload import (
    ArtifactRecord,
    UnresolvedRef,
    iter_artifacts,
    iter_unresolved,
    load_session_dict,
    scan_orphan_files,
)

# Shipped as companionDevlog in JSON-LD + leftover_report when uncategorized paths exist.
COMPANION_DEVLOG = (
    "DEVLOG (implementation backlog): paths under non_rerum_carry_forward are included in this bundle "
    "for audit but not modeled as separate @graph objects until mapping rules exist (orphans, stale refs). "
    "Wire them into typed JSON-LD or hosted blobs when RERUM policy allows."
)


@dataclass
class IngestResult:
    session_name: str
    session_json_path: Path
    cv_root: Path
    manifest_warnings: list[str]
    compatibility_note: str
    resolved: list[ArtifactRecord]
    unresolved: list[UnresolvedRef]
    orphans: list[Path]
    document: dict[str, Any]
    leftover_report: dict[str, Any] = field(default_factory=dict)

    def build_leftover_report(self) -> dict[str, Any]:
        """Partial bucket / incomplete mapper — JSON-serializable (includes uncategorized carry-forward)."""
        leftovers_present = bool(self.unresolved or self.orphans)
        um = [
            {
                "raw_path": u.raw_path,
                "source": u.source,
                "kind": u.kind,
                "pending_mapper": True,
            }
            for u in self.unresolved
        ]
        orphan_paths = [str(p.resolve()) for p in self.orphans]
        return {
            "status": "offline_partial_bucket",
            "session_name": self.session_name,
            "session_json": str(self.session_json_path.resolve()),
            "leftovers_present": leftovers_present,
            # Explicit alias for tooling: uncategorized paths/files are included but not @graph objectized.
            "has_uncategorized_carry_forward": leftovers_present,
            "companion_devlog": COMPANION_DEVLOG if leftovers_present else "",
            "notes": (
                "Unresolved references are stale paths in session.json. Orphans are outputs under the bundle "
                "not linked from session.json (uploads/ excluded from orphan scan). "
                "They do not block JSON-LD for resolved artifacts; see non_rerum_carry_forward."
            ),
            "non_rerum_carry_forward": {
                "description": (
                    "Included for audit and future mappers; not duplicated as separate Dataset/MediaObject "
                    "nodes in session_bundle.jsonld."
                ),
                "unmapped_references": um,
                "orphan_files": orphan_paths,
            },
        }


def analyze_session(
    *,
    session_json_path: Path,
    cv_root: Path,
    manifest_path: Path,
) -> IngestResult:
    data = load_session_dict(session_json_path)
    session_name = data.get("name")
    if not session_name or not isinstance(session_name, str):
        raise ValueError("session.json must contain a string 'name' field.")

    manifest = load_manifest(manifest_path)
    manifest_warnings = check_session_keys(data, manifest)
    note = compatibility_note(manifest)

    resolved = list(iter_artifacts(data, cv_root, session_name=session_name))
    unresolved = list(iter_unresolved(data, cv_root, session_name=session_name))
    orphans = scan_orphan_files(session_json_path, data, cv_root, session_name)

    leftovers_present = bool(unresolved or orphans)
    companion_devlog = COMPANION_DEVLOG if leftovers_present else ""

    doc = build_session_graph(
        session_name=session_name,
        session_json_path=session_json_path,
        artifacts=resolved,
        annotation=(
            f"Unresolved references in session.json: {len(unresolved)}. "
            f"Orphan output files under bundle: {len(orphans)}."
        ),
        leftovers_present=leftovers_present,
        companion_devlog=companion_devlog,
    )

    r = IngestResult(
        session_name=session_name,
        session_json_path=session_json_path,
        cv_root=cv_root,
        manifest_warnings=manifest_warnings,
        compatibility_note=note,
        resolved=resolved,
        unresolved=unresolved,
        orphans=orphans,
        document=doc,
    )
    r.leftover_report = r.build_leftover_report()
    return r
