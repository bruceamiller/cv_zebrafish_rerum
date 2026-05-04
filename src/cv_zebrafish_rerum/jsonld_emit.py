"""Build JSON-LD (@graph) for a session run (offline / shadow store)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from cv_zebrafish_rerum.session_payload import ArtifactRecord, encoding_format_for_path

_PROFILE_PLOTLY_HTML = "https://github.com/oss-slu/cv_zebrafish/blob/main/docs/product/PRODUCT_SUMMARY.md#outputs"
_SOFTWARE_ID = "urn:cv-zebrafish:local:software:cv-zebrafish"


def _local_id(prefix: str, *parts: str) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"urn:cv-zebrafish:local:{prefix}:{h}"


def build_session_graph(
    *,
    session_name: str,
    session_json_path: Path,
    artifacts: list[ArtifactRecord],
    annotation: str | None = None,
    leftovers_present: bool = False,
    companion_devlog: str = "",
) -> dict[str, Any]:
    """One JSON-LD document with @graph: software + summary run + artifact nodes."""
    run_id = _local_id(
        "run",
        session_name,
        str(session_json_path.resolve()),
    )

    software: dict[str, Any] = {
        "@id": _SOFTWARE_ID,
        "@type": "SoftwareApplication",
        "name": "CV Zebrafish",
        "url": "https://github.com/oss-slu/cv_zebrafish",
    }

    summary: dict[str, Any] = {
        "@id": run_id,
        "@type": "Dataset",
        "name": f"CV Zebrafish session output — {session_name}",
        "description": "Derived graph artifacts recorded in session.json (offline bundle)."
        + (f" {annotation}" if annotation else ""),
        "generatedBy": {"@id": _SOFTWARE_ID},
    }

    extra_props: list[dict[str, Any]] = [
        {
            "@type": "PropertyValue",
            "name": "leftoversPresent",
            "value": leftovers_present,
        },
        {
            "@type": "PropertyValue",
            "name": "resolvedArtifactCount",
            "value": len(artifacts),
        },
    ]
    if companion_devlog.strip():
        extra_props.append(
            {
                "@type": "PropertyValue",
                "name": "companionDevlog",
                "value": companion_devlog.strip(),
            }
        )
    summary["additionalProperty"] = extra_props

    graph: list[dict[str, Any]] = [software, summary]

    for i, art in enumerate(artifacts):
        aid = _local_id("artifact", art.path, str(i))
        node: dict[str, Any] = {
            "@id": aid,
            "@type": "MediaObject",
            "name": Path(art.path).name,
            "encodingFormat": encoding_format_for_path(art.path),
            "url": Path(art.path).resolve().as_uri(),
        }
        if art.suffix.lower() == ".html":
            node["conformsTo"] = _PROFILE_PLOTLY_HTML
        # Intentionally no Dataset.associatedMedia list: it duplicated every @id and bloated JSON.
        # Consumers traverse @graph for MediaObject nodes linked by provenance conventions.

        prov_bits: list[str] = [art.source]
        if art.csv_id:
            prov_bits.append(f"csv={art.csv_id}")
        if art.config_path:
            prov_bits.append(f"config={art.config_path}")
        if art.folder_path:
            prov_bits.append(f"folder={art.folder_path}")
        if art.folder_csv:
            prov_bits.append(f"folder_csv={art.folder_csv}")
        node["description"] = " | ".join(prov_bits)

        graph.append(node)

    doc: dict[str, Any] = {
        "@context": {
            "@vocab": "https://schema.org/",
        },
        "@graph": graph,
    }
    return doc
