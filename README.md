# cv_zebrafish_rerum

> This repo is an early **cv_zebrafish RERUM wrapper** (offline first). It turns CV Zebrafish session output into **structured objects** (JSON-LD graph, bundle metadata, carry-forward audit).
> It also ships a **baseline publication preview** (HTML). That preview sketches how a Graph Viewer style surface could look if the same ideas land in RERUM later.

This document is for **people who extend or review the code**. End users run the CLI or GUI after install. Behavior details live in source.

---

## What the package does today

| Area | Role |
|------|------|
| **Session ingest** | Reads `session.json` and resolves graph paths (single-CSV and folder-graph layouts). Warns when `session_manifest.json` keys drift from the session file. |
| **JSON-LD** | Writes `session_bundle.jsonld` with `@graph`: `SoftwareApplication`, one summary `Dataset`, and one `MediaObject` per resolved artifact (`encodingFormat`, `file:` URL, optional `conformsTo` for Plotly HTML). |
| **Carry-forward audit** | Stale paths and orphan outputs are not duplicated in `@graph`. They go to `leftover_report.json` under `non_rerum_carry_forward`, with plain-text devlogs when carry-forward exists. |
| **Publication preview** | `publication_preview.html`: session strip, tab chrome (Graphs enabled offline), CSV navigation when needed, graph rows with open-in-new-window, iframe or PNG preview, parallel link to `session_bundle.jsonld`. |
| **Local bundle** | Under `shadow_store/runs/<slug>_<hash>/`: JSON-LD, ingest meta, leftovers, previews, manifest, devlogs. `shadow_store/staging/` holds copies for safe browser opens. |
| **Desktop GUI** | PyQt5: pick CV Zebrafish clone root, select session, **Analyze**, **Write local bundle**; watches `session.json` for the selected session. |

Upstream app: [CV Zebrafish](https://github.com/oss-slu/cv_zebrafish). This package **reads** that tree; it does not patch PyQt in the main app.

---

## Install and entry points

**CLI:** `pip install -e .`  
**CLI + GUI:** `pip install -e ".[gui]"`

```bash
python -m cv_zebrafish_rerum ingest --session-json "…\session.json" --emit-shadow
python -m cv_zebrafish_rerum stage-open "…\plot.html" --open-browser
python -m cv_zebrafish_rerum list-shadow
python -m cv_zebrafish_rerum gui
```

Set **`CV_ZEBRAFISH_ROOT`** or **`--cv-root`** when session path inference fails.

If the preview looks stale, re-run **`ingest --emit-shadow`** or **Write local bundle** in the GUI; HTML is regenerated on emit.

---

## Specs and planning (sibling repo)

Design notes and agent workflow live under **`../cv_zebrafish/.cursor/agent-workspace/`** (often gitignored with `cv_zebrafish`). Useful entry points: **`AGENT_STEP_WORKFLOW.md`**, **`RERUM_WRAPPER_PLAN.md`**. Official API: [RERUM API v1](https://store.rerum.io/API.html).

---

## Repo layout

| Path | Role |
|------|------|
| `session_manifest.json` | Expected `session.json` keys (compatibility and drift warnings). |
| `shadow_store/` | Runtime output (gitignored): bundles, `index.json`, `staging/`. |
| `src/cv_zebrafish_rerum/` | Package source (`ingest_core`, `jsonld_emit`, `preview_emit`, `shadow_store`, CLI, GUI). |

---

## Future steps

The following belong in later layers, not in this repo’s core scope today:

1. **Network registration.** Add Tiny Things `POST` paths, Bearer tokens, and transport that call RERUM HTTP APIs. Keep secrets out of git.
2. **Blob hosting and URL rewrite.** Upload artifacts to HTTPS under lab policy, then replace `file:` with stable `https:` before any registration payload.
3. **App registration and transport.** Wire devstore or prod store tokens (see API doc). Add a thin `TinyThingsTransport` (or similar) that swaps `LocalShadowTransport` for `POST …/app/create` and optional update or query.
4. **Visibility and launch.** Support public versus private objects, tokenized launch URLs, and optional IIIF or manifest viewers (see backlog notes in the agent workspace).
5. **IRB and privacy policy.** Keep defaults offline; follow lab and institutional rules for visibility.
6. **Smaller registration payloads (optional).** Today one `MediaObject` per resolved output keeps the JSON-LD tall by design. The summary `Dataset` already avoids duplicating every artifact `@id` in `associatedMedia`, so noise drops while counts stay available via `resolvedArtifactCount` and `leftoversPresent`. Later options include the following: one bundle node plus a sidecar URL list, hash-only references with blobs hosted elsewhere, or fewer nodes with `hasPart` pointing at a manifest file.

Rough order for full RERUM alignment: blob hosting, URL rewrite, app registration and transport, then visibility and launch. Early work is mostly policy and scripting. Later work is a thin transport and config layer on top of the JSON-LD and bundle layout this package emits today.
