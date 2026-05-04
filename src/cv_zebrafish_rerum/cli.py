from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

from cv_zebrafish_rerum.carry_forward_devlog import write_last_carry_forward_devlog
from cv_zebrafish_rerum import __version__
from cv_zebrafish_rerum.ingest_core import analyze_session
from cv_zebrafish_rerum.manifest_check import load_manifest
from cv_zebrafish_rerum.paths_compat import infer_cv_root_from_session_json
from cv_zebrafish_rerum.shadow_index import load_index
from cv_zebrafish_rerum.shadow_store import write_run_bundle
from cv_zebrafish_rerum.stage_open import stage_file


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_cv_root(session_json: Path, explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_dir() else None
    env = os.environ.get("CV_ZEBRAFISH_ROOT", "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.is_dir() else None
    return infer_cv_root_from_session_json(session_json)


def _cmd_ingest(args: argparse.Namespace) -> int:
    session_json: Path = args.session_json
    if not session_json.is_file():
        print(f"session.json not found: {session_json}", file=sys.stderr)
        return 1

    manifest_path: Path = args.manifest or (_repo_root() / "session_manifest.json")
    if not manifest_path.is_file():
        print(f"session_manifest.json not found: {manifest_path}", file=sys.stderr)
        return 1

    cv_root = _resolve_cv_root(session_json, args.cv_root)
    if cv_root is None:
        print(
            "Could not resolve CV Zebrafish repo root. Pass --cv-root or set CV_ZEBRAFISH_ROOT.",
            file=sys.stderr,
        )
        return 1

    try:
        result = analyze_session(
            session_json_path=session_json,
            cv_root=cv_root,
            manifest_path=manifest_path,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(result.compatibility_note)
    for w in result.manifest_warnings:
        print(f"Warning: {w}", file=sys.stderr)

    print(f"Session: {result.session_name}")
    print(f"Resolved artifacts on disk: {len(result.resolved)}")
    print(f"Unresolved references (stale paths in session.json): {len(result.unresolved)}")
    print(f"Orphan output files under bundle (not in session.json): {len(result.orphans)}")

    devlog_path = write_last_carry_forward_devlog(_repo_root(), result.leftover_report)
    if devlog_path is not None:
        print(f"Carry-forward devlog (human-readable): {devlog_path}", file=sys.stderr)

    if not result.resolved:
        print(
            "No graph files resolved (paths missing or session has no saved graphs yet).",
            file=sys.stderr,
        )

    if args.show_leftovers:
        for u in result.unresolved:
            print(f"  [unresolved] {u.raw_path}")
            print(f"             ({u.source})")
        for o in result.orphans:
            print(f"  [orphan] {o}")

    if args.emit_shadow:
        dest = write_run_bundle(
            repo_root=_repo_root(),
            session_name=result.session_name,
            session_json_path=session_json,
            document=result.document,
            leftover_report=result.leftover_report,
            resolved_artifacts=result.resolved,
            resolved_count=len(result.resolved),
            unresolved_count=len(result.unresolved),
            orphan_count=len(result.orphans),
        )
        print(f"Wrote shadow bundle: {dest}")
        print(f"Leftover report: {dest.parent / 'leftover_report.json'}")
        lr = result.leftover_report
        if lr.get("leftovers_present") or lr.get("has_uncategorized_carry_forward"):
            print(f"Carry-forward text devlog: {dest.parent / 'companion_carry_forward_devlog.txt'}", file=sys.stderr)
    else:
        print("Dry-run: no shadow_store write (pass --emit-shadow to write JSON-LD).")
        if args.print_jsonld:
            print(json.dumps(result.document, indent=2))

    return 0


def _cmd_stage_open(args: argparse.Namespace) -> int:
    src: Path = args.artifact
    if not src.is_file():
        print(f"Not a file: {src}", file=sys.stderr)
        return 1
    staged = stage_file(_repo_root(), src)
    print(staged.resolve().as_uri())
    print(f"Staged: {staged}")
    if args.open_browser:
        webbrowser.open(staged.resolve().as_uri())
    return 0


def _cmd_list_shadow(args: argparse.Namespace) -> int:
    idx = load_index(_repo_root())
    if args.json:
        print(json.dumps(idx, indent=2))
        return 0
    runs = idx.get("runs") or []
    print(f"shadow_store runs ({len(runs)} entries)")
    for r in runs:
        print(f"  - {r.get('id')} -- resolved={r.get('resolved_count')} "
            f"unresolved={r.get('unresolved_count')} orphans={r.get('orphan_count')}"
        )
        print(f"    {r.get('bundle_jsonld')}")
    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    session_json: Path = args.session_json
    manifest_path: Path = args.manifest or (_repo_root() / "session_manifest.json")
    cv_root = _resolve_cv_root(session_json, args.cv_root)
    if cv_root is None:
        print("Could not resolve CV root.", file=sys.stderr)
        return 1
    if not manifest_path.is_file():
        print(f"Missing manifest: {manifest_path}", file=sys.stderr)
        return 1

    interval = max(0.5, float(args.interval))

    def run_once(label: str) -> None:
        try:
            result = analyze_session(
                session_json_path=session_json,
                cv_root=cv_root,
                manifest_path=manifest_path,
            )
        except ValueError as e:
            print(f"[{label}] {e}", file=sys.stderr)
            return
        print(
            f"[{label}] resolved={len(result.resolved)} unresolved={len(result.unresolved)} "
            f"orphans={len(result.orphans)}"
        )

    if args.run_on_start:
        run_once("start")
    last_mtime: float | None = None
    try:
        last_mtime = session_json.stat().st_mtime
    except OSError as e:
        print(f"Cannot stat session.json: {e}", file=sys.stderr)
        return 1

    print(f"Watching {session_json} (interval={interval}s, Ctrl+C to stop)")
    try:
        while True:
            time.sleep(interval)
            try:
                m = session_json.stat().st_mtime
            except OSError:
                continue
            if m != last_mtime:
                last_mtime = m
                run_once("change")
    except KeyboardInterrupt:
        print()
        return 0


def _cmd_gui(args: argparse.Namespace) -> int:
    try:
        from cv_zebrafish_rerum.gui_main import run_gui
    except ImportError as e:
        print(
            "GUI requires PyQt5. Install with: pip install 'cv-zebrafish-rerum[gui]'",
            file=sys.stderr,
        )
        print(str(e), file=sys.stderr)
        return 1
    return run_gui()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cv-zebrafish-rerum",
        description="Offline companion: session.json → JSON-LD / shadow_store (RERUM-shaped).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Parse session.json, validate keys, emit JSON-LD summary.")
    p_ingest.add_argument("--session-json", type=Path, required=True, help="Path to session.json")
    p_ingest.add_argument(
        "--cv-root",
        type=Path,
        default=None,
        help="CV Zebrafish repo root (default: infer from path or CV_ZEBRAFISH_ROOT)",
    )
    p_ingest.add_argument(
        "--emit-shadow",
        action="store_true",
        help="Write shadow_store/runs/.../session_bundle.jsonld (otherwise dry-run)",
    )
    p_ingest.add_argument(
        "--print-jsonld",
        action="store_true",
        help="Print JSON-LD to stdout when not writing shadow_store",
    )
    p_ingest.add_argument(
        "--show-leftovers",
        action="store_true",
        help="Print unresolved paths and orphan files",
    )
    p_ingest.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="session_manifest.json path (default: beside pyproject in this repo)",
    )
    p_ingest.set_defaults(func=_cmd_ingest)

    p_stage = sub.add_parser(
        "stage-open",
        help="Copy an artifact into shadow_store/staging/ (then optionally open in browser).",
    )
    p_stage.add_argument("artifact", type=Path, help="File to copy (e.g. Plotly HTML)")
    p_stage.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the staged file URI in the default browser",
    )
    p_stage.set_defaults(func=_cmd_stage_open)

    p_list = sub.add_parser("list-shadow", help="List recorded shadow_store runs (offline index).")
    p_list.add_argument("--json", action="store_true", help="Raw index.json")
    p_list.set_defaults(func=_cmd_list_shadow)

    p_watch = sub.add_parser(
        "watch",
        help="Poll session.json; print ingest stats when the file changes (no upload).",
    )
    p_watch.add_argument("--session-json", type=Path, required=True)
    p_watch.add_argument("--cv-root", type=Path, default=None)
    p_watch.add_argument("--manifest", type=Path, default=None)
    p_watch.add_argument("--interval", type=float, default=2.0, help="Seconds between checks")
    p_watch.add_argument(
        "--run-on-start",
        action="store_true",
        help="Analyze once before waiting",
    )
    p_watch.set_defaults(func=_cmd_watch)

    p_gui = sub.add_parser("gui", help="Open desktop UI (requires pip install .[gui]).")
    p_gui.set_defaults(func=_cmd_gui)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
