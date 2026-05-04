"""Stage artifacts under ``shadow_store/staging/`` (same offline package tree as bundles)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path


def staging_dir(repo_root: Path) -> Path:
    """Gitignored via ``shadow_store/`` — one tree with JSON-LD bundles + ad-hoc staged opens."""
    d = repo_root / "shadow_store" / "staging"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_file(repo_root: Path, source: Path) -> Path:
    """Copy *source* into ``shadow_store/staging/`` with a unique name; return destination path."""
    scratch = staging_dir(repo_root)
    suffix = source.suffix or ""
    dest = scratch / f"{source.stem}_{uuid.uuid4().hex[:8]}{suffix}"
    shutil.copy2(source, dest)
    return dest
