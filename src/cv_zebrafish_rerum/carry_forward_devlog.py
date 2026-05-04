"""Human-readable carry-forward audit log (text); GUI/CLI write sink under shadow_store/."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def carry_forward_lists(leftover_report: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """Leftovers live under non_rerum_carry_forward (legacy bundles may use top-level keys)."""
    nrc = leftover_report.get("non_rerum_carry_forward") or {}
    if isinstance(nrc, dict):
        um = nrc.get("unmapped_references") or []
        ofs = nrc.get("orphan_files") or []
    else:
        um, ofs = [], []
    if not um and not ofs:
        um = leftover_report.get("unmapped_references") or []
        ofs = leftover_report.get("orphan_files") or []
    return um, ofs


def format_carry_forward_devlog(leftover_report: dict[str, Any]) -> str:
    """Plain-text detail for uncategorized paths and orphan files (not duplicated as @graph nodes)."""
    lines: list[str] = []
    lp = leftover_report or {}
    lines.append("cv_zebrafish_rerum — carry-forward devlog")
    lines.append("=" * 60)
    lines.append(f"session_name: {lp.get('session_name', '')}")
    lines.append(f"session_json: {lp.get('session_json', '')}")
    lines.append(f"leftovers_present: {lp.get('leftovers_present', lp.get('has_uncategorized_carry_forward', False))}")
    lines.append("")
    dev = (lp.get("companion_devlog") or "").strip()
    if dev:
        lines.append("--- companion_devlog (implementation backlog) ---")
        lines.append(dev)
        lines.append("")
    notes = (lp.get("notes") or "").strip()
    if notes:
        lines.append("--- notes ---")
        lines.append(notes)
        lines.append("")
    nrc = lp.get("non_rerum_carry_forward")
    if isinstance(nrc, dict) and (nrc.get("description")):
        lines.append("--- non_rerum_carry_forward.description ---")
        lines.append(str(nrc.get("description")))
        lines.append("")
    um, ofs = carry_forward_lists(lp)
    lines.append("--- unmapped_references (paths in session.json that did not resolve) ---")
    if not um:
        lines.append("(none)")
    else:
        for item in um:
            if isinstance(item, dict):
                lines.append(f"  raw_path: {item.get('raw_path', '')}")
                lines.append(f"  kind:     {item.get('kind', '')}")
                lines.append(f"  source:   {item.get('source', '')}")
                lines.append("")
    lines.append("--- orphan_files (outputs under bundle not referenced in session.json; uploads/ excluded) ---")
    if not ofs:
        lines.append("(none)")
    else:
        for p in ofs:
            lines.append(f"  {p}")
    lines.append("")
    lines.append("Machine JSON: leftover_report.json in the same bundle folder.")
    return "\n".join(lines).rstrip() + "\n"


def write_last_carry_forward_devlog(repo_root: Path, leftover_report: dict[str, Any]) -> Path | None:
    """Write ``shadow_store/last_carry_forward_devlog.txt`` when carry-forward exists; else delete stale file."""
    out_dir = repo_root / "shadow_store"
    dest = out_dir / "last_carry_forward_devlog.txt"
    lp = leftover_report or {}
    present = bool(lp.get("leftovers_present") or lp.get("has_uncategorized_carry_forward"))
    if not present:
        try:
            if dest.is_file():
                dest.unlink()
        except OSError:
            pass
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(format_carry_forward_devlog(leftover_report), encoding="utf-8")
    return dest
