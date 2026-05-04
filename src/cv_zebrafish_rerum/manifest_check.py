"""Load ``session_manifest.json`` and compare to on-disk ``session.json`` keys."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_session_keys(data: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    """Return human-readable warnings (empty if OK)."""
    warnings: list[str] = []
    req = set(manifest.get("session_json_required_keys") or [])
    opt = set(manifest.get("session_json_optional_keys") or [])
    allowed = req | opt
    top = set(data.keys())

    missing = req - top
    if missing:
        warnings.append(f"Missing required session.json keys: {sorted(missing)}")

    unknown = top - allowed
    if unknown:
        warnings.append(
            "Unknown session.json keys (app may be newer than this companion — "
            f"update session_manifest.json): {sorted(unknown)}"
        )

    return warnings


def compatibility_note(manifest: dict[str, Any]) -> str:
    wrapper = str(manifest.get("wrapper_semver", "?"))
    return (
        f"Compatibility: session manifest v{manifest.get('manifest_version', '?')} "
        f"(wrapper_semver={wrapper}). If keys drift, update session_manifest.json and bump wrapper_semver."
    )
