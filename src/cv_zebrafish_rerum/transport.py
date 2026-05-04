"""Transport abstraction: local shadow files today; HTTP POST later."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class Transport(Protocol):
    def persist_bundle(self, document: dict[str, Any], dest_path: Path) -> None: ...


class LocalShadowTransport:
    """Writes JSON-LD to disk only (no network)."""

    def persist_bundle(self, document: dict[str, Any], dest_path: Path) -> None:
        import json

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
