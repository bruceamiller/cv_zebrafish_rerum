"""Generate a local HTML page that previews bundle contents (RERUM-shaped summary + carry-forward)."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from cv_zebrafish_rerum.carry_forward_devlog import carry_forward_lists
from cv_zebrafish_rerum.session_payload import ArtifactRecord, encoding_format_for_path

_RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"})
_HTML_SUFFIXES = frozenset({".html", ".htm"})

# Inline SVG for “open file in new tab” (used in graph list + compact artifact lines).
_OPEN_TAB_ICON_SVG = """<svg class="open-tab-svg" xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>"""


def _open_file_icon_link(uri: str, *, css_class: str = "open-file-ico") -> str:
    esc_uri = html.escape(uri, quote=True)
    title = html.escape("Open file in new tab", quote=True)
    return (
        f'<a class="{css_class}" href="{esc_uri}" title="{title}" aria-label="{title}" '
        'target="_blank" rel="noopener noreferrer">'
        f"{_OPEN_TAB_ICON_SVG}</a>"
    )


def _graph_external_open_link(uri: str) -> str:
    """Icon-only link: opens Plotly/HTML or image in a separate browser window (Graph preview toolbar)."""
    esc_uri = html.escape(uri, quote=True)
    title = html.escape("Open graph in new window", quote=True)
    return (
        f'<a class="gvf-open" href="{esc_uri}" title="{title}" aria-label="{title}" rel="noopener noreferrer" '
        'onclick="event.preventDefault();window.open(this.href,\'gvfPlot\','
        '\'noopener,noreferrer,width=1280,height=900\');">'
        f"{_OPEN_TAB_ICON_SVG}</a>"
    )


def _bundle_doc_line(rel_href: str, label_html: str) -> str:
    """One list row: open-in-new-tab icon plus visible label (both inside the same anchor)."""
    esc_h = html.escape(rel_href, quote=True)
    title = html.escape("Open in new tab", quote=True)
    return (
        f'<li class="doc-graph-line"><a class="doc-line-a" href="{esc_h}" target="_blank" '
        f'rel="noopener noreferrer" title="{title}" aria-label="{title}">'
        f'<span class="doc-line-ico">{_OPEN_TAB_ICON_SVG}</span>'
        f'<span class="doc-line-txt">{label_html}</span></a></li>'
    )


def _bundle_top_link(rel_href: str, text: str) -> str:
    esc_h = html.escape(rel_href, quote=True)
    esc_t = html.escape(text)
    title = html.escape("Open in new tab", quote=True)
    return (
        f'<a class="top-bundle-link" href="{esc_h}" target="_blank" rel="noopener noreferrer" title="{title}">'
        f'<span class="doc-line-ico">{_OPEN_TAB_ICON_SVG}</span><span>{esc_t}</span></a>'
    )


def _graph_dataset_label(art: ArtifactRecord) -> str:
    """Match Graph Viewer: folder runs group by CSV file; single-csv uses CSV stem."""
    if art.source == "folder_graph" and art.folder_csv:
        return Path(art.folder_csv).name
    if art.csv_id:
        return Path(str(art.csv_id)).name
    return "Graphs"


def _graph_preview_buckets(resolved: list[ArtifactRecord]) -> dict[tuple[str, str], dict[str, str | None]]:
    """(dataset label, graph stem) -> {'html': file uri | None, 'img': file uri | None}."""
    buckets: dict[tuple[str, str], dict[str, str | None]] = {}
    for art in resolved:
        suf = art.suffix.lower()
        if suf not in _HTML_SUFFIXES and suf not in _RASTER_SUFFIXES:
            continue
        group = _graph_dataset_label(art)
        stem = Path(art.path).stem
        key = (group, stem)
        slot = buckets.setdefault(key, {"html": None, "img": None})
        uri = Path(art.path).resolve().as_uri()
        if suf in _HTML_SUFFIXES:
            slot["html"] = uri
        else:
            slot["img"] = uri
    return buckets


def _build_graph_viewer_preview_section(resolved: list[ArtifactRecord], *, session_name: str) -> str:
    """
    Offline mirror of CV Zebrafish Graph Viewer **Graphs** tab: context strip, tab row,
    CSV Prev/Next + combo when multiple datasets, pick buttons + separate open-in-new-window icon, preview pane.
    """
    buckets = _graph_preview_buckets(resolved)
    rows: list[tuple[str, str, str, str, str]] = []
    for (group, stem) in sorted(buckets.keys(), key=lambda k: (k[0].lower(), k[1].lower())):
        b = buckets[(group, stem)]
        if b.get("html"):
            kind, preview_uri, open_uri = "html", str(b["html"]), str(b["html"])
        elif b.get("img"):
            kind, preview_uri, open_uri = "img", str(b["img"]), str(b["img"])
        else:
            continue
        rows.append((group, stem, kind, preview_uri, open_uri))

    groups_in_order: list[str] = []
    seen_g: set[str] = set()
    for group, _stem, _k, _p, _o in rows:
        if group not in seen_g:
            seen_g.add(group)
            groups_in_order.append(group)

    esc_session = html.escape(session_name)
    multi_csv = len(groups_in_order) > 1
    csv_row_style = "" if multi_csv else "display:none"
    select_opts = "".join(
        f'<option value="{i}">{html.escape(g)}</option>' for i, g in enumerate(groups_in_order)
    )

    if not rows:
        list_inner = ""
        right_placeholder = "No graphs available."
    else:
        row_chunks: list[str] = []
        for group, stem, kind, preview_uri, open_uri in rows:
            ds_idx = groups_in_order.index(group)
            hidden = "display:none" if ds_idx != 0 else ""
            pr = html.escape(preview_uri, quote=True)
            row_chunks.append(
                f'<div class="gvf-row" role="option" tabindex="0" data-dataset="{ds_idx}" '
                f'data-kind="{kind}" data-preview="{pr}" style="{hidden}">'
                f'<button type="button" class="gvf-pick">{html.escape(stem)}</button>'
                f"{_graph_external_open_link(open_uri)}"
                "</div>"
            )
        list_inner = "\n".join(row_chunks)
        right_placeholder = "Select a graph on the left."

    return f"""<section class="gvf-outer"><h2>Graph preview</h2>
<p class="small">Mirrors CV Zebrafish <strong>Graph Viewer → Graphs</strong>: pick a graph with the button; the icon opens the same file in a <strong>new browser window</strong>. Folder bundles: CSV drop-down and Prev/Next. Cross-Correlation and Compare stay in the desktop app.</p>
<div class="gvf-chrome">
  <div class="gvf-context">
    <span class="gvf-ctx-icon" aria-hidden="true">◆</span>
    <div class="gvf-ctx-text"><span class="gvf-ctx-k">Session</span> {esc_session}</div>
  </div>
  <div class="gvf-tabs" role="tablist" aria-label="Graph viewer tabs">
    <span class="gvf-tab gvf-tab-active" role="tab" aria-selected="true">Graphs</span>
    <span class="gvf-tab gvf-tab-disabled" role="tab" aria-selected="false" title="Not in offline preview">Cross-Correlation</span>
    <span class="gvf-tab gvf-tab-disabled" role="tab" aria-selected="false" title="Not in offline preview">Compare</span>
  </div>
  <div class="gvf-panel">
    <div class="gvf-left">
      <div id="gvfCsvRow" class="gvf-csv-row" style="{csv_row_style}">
        <button type="button" id="gvfPrevCsv" class="gvf-navbtn" title="Previous dataset">◀ Prev</button>
        <select id="gvfCsvSelect" class="gvf-select" aria-label="CSV file (folder runs)">{select_opts}</select>
        <button type="button" id="gvfNextCsv" class="gvf-navbtn" title="Next dataset">Next ▶</button>
      </div>
      <div class="gvf-listhead"><span id="gvfListLabel">Graphs</span></div>
      <div id="gvfGraphList" class="gvf-list" role="listbox" aria-labelledby="gvfListLabel" tabindex="-1">
{list_inner}
      </div>
    </div>
    <div class="gvf-right">
      <div id="gvfCaption" class="gvf-caption"></div>
      <iframe id="gvfFrame" class="gvf-frame" title="Selected graph"></iframe>
      <img id="gvfImg" class="gvf-img" alt="Selected graph" />
      <div id="gvfEmpty" class="gvf-empty">{html.escape(right_placeholder)}</div>
    </div>
  </div>
</div>
<script>
(function() {{
  var list = document.getElementById("gvfGraphList");
  var sel = document.getElementById("gvfCsvSelect");
  var prevB = document.getElementById("gvfPrevCsv");
  var nextB = document.getElementById("gvfNextCsv");
  var cap = document.getElementById("gvfCaption");
  var fr = document.getElementById("gvfFrame");
  var im = document.getElementById("gvfImg");
  var empty = document.getElementById("gvfEmpty");
  if (!list) return;

  function visibleRows() {{
    return Array.prototype.slice.call(list.querySelectorAll(".gvf-row[data-preview]")).filter(function(r) {{
      return r.style.display !== "none";
    }});
  }}

  function clearSelected() {{
    var all = list.querySelectorAll(".gvf-row");
    for (var i = 0; i < all.length; i++) all[i].classList.remove("gvf-selected");
  }}

  function showRow(row) {{
    if (!row || !row.getAttribute("data-preview")) return;
    var kind = row.getAttribute("data-kind");
    var uri = row.getAttribute("data-preview");
    var pick = row.querySelector(".gvf-pick");
    var label = pick ? pick.textContent : "";
    clearSelected();
    row.classList.add("gvf-selected");
    if (cap) cap.textContent = label;
    empty.style.display = "none";
    if (kind === "html") {{
      im.style.display = "none";
      im.removeAttribute("src");
      fr.style.display = "block";
      fr.setAttribute("sandbox", "allow-scripts allow-same-origin allow-downloads");
      fr.src = uri;
    }} else {{
      fr.style.display = "none";
      try {{ fr.removeAttribute("src"); }} catch (e1) {{}}
      im.style.display = "block";
      im.src = uri;
    }}
  }}

  function showDatasetIndex(idx) {{
    if (!sel || sel.options.length === 0) return;
    idx = (idx + sel.options.length) % sel.options.length;
    sel.selectedIndex = idx;
    var rows = list.querySelectorAll(".gvf-row");
    for (var i = 0; i < rows.length; i++) {{
      var r = rows[i];
      if (!r.getAttribute("data-preview")) continue;
      var d = parseInt(r.getAttribute("data-dataset"), 10);
      r.style.display = (d === idx) ? "" : "none";
    }}
    var vis = visibleRows();
    if (vis.length) showRow(vis[0]);
  }}

  list.addEventListener("click", function(ev) {{
    if (ev.target.closest("a.gvf-open")) return;
    var btn = ev.target.closest(".gvf-pick");
    var row = btn ? btn.closest(".gvf-row") : ev.target.closest(".gvf-row");
    if (row && row.getAttribute("data-preview")) showRow(row);
  }});

  if (sel && sel.options.length > 1) {{
    sel.addEventListener("change", function() {{
      showDatasetIndex(sel.selectedIndex);
    }});
    if (prevB) prevB.addEventListener("click", function() {{
      showDatasetIndex(sel.selectedIndex - 1);
    }});
    if (nextB) nextB.addEventListener("click", function() {{
      showDatasetIndex(sel.selectedIndex + 1);
    }});
  }}

  var first = visibleRows()[0];
  if (first) showRow(first);
  else {{
    if (cap) cap.textContent = "";
    fr.style.display = "none";
    im.style.display = "none";
    empty.style.display = "flex";
  }}
}})();
</script>
</section>"""


def write_publication_preview(
    run_folder: Path,
    *,
    session_name: str,
    leftover_report: dict[str, Any],
    resolved: list[ArtifactRecord],
    document: dict[str, Any] | None = None,
) -> Path:
    """Write ``publication_preview.html`` next to ``session_bundle.jsonld`` and return its path."""
    lp = leftover_report or {}
    leftovers_present = bool(lp.get("leftovers_present") or lp.get("has_uncategorized_carry_forward"))
    devlog = str(lp.get("companion_devlog") or "")
    warn_lines: list[str] = []
    if leftovers_present:
        warn_lines.append(
            "Uncategorized carry-forward exists (stale session paths and/or orphan output files). "
            "They are <strong>not</strong> separate <code>MediaObject</code> nodes in <code>@graph</code>; "
            "see <code>leftover_report.json</code> and <code>companion_carry_forward_devlog.txt</code> in this folder."
        )
        if devlog:
            warn_lines.append(html.escape(devlog))

    lines_modeled: list[str] = []
    for art in resolved:
        uri = Path(art.path).resolve().as_uri()
        name = html.escape(Path(art.path).name)
        enc = html.escape(encoding_format_for_path(art.path))
        prov = html.escape(
            " | ".join(
                x
                for x in (
                    art.source,
                    art.csv_id or "",
                    art.config_path or "",
                    art.folder_path or "",
                )
                if x
            )
        )
        lines_modeled.append(
            f'<li class="artifact-line">{_open_file_icon_link(uri)}'
            f'<span class="artifact-meta"><span class="artifact-name">{name}</span>'
            f' <span class="artifact-sep">—</span> <code>{enc}</code>'
            f'<span class="artifact-prov"> — {prov}</span></span></li>'
        )

    um, ors = carry_forward_lists(lp)
    lines_carry: list[str] = []
    for item in um:
        if isinstance(item, dict):
            raw = str(item.get("raw_path", ""))
            src = str(item.get("source", ""))
            lines_carry.append(
                '<li class="carry-line"><span class="ico-placeholder" aria-hidden="true"></span>'
                '<span class="carry-body"><span class="carry-kind">unmapped path</span> '
                f'<code>{html.escape(raw)}</code>'
                f'<span class="carry-src"> — {html.escape(src)}</span></span></li>'
            )
    for p in ors:
        ps = str(p)
        open_ico = ""
        try:
            pp = Path(ps)
            if pp.is_file():
                open_ico = _open_file_icon_link(pp.resolve().as_uri())
        except OSError:
            pass
        if not open_ico:
            open_ico = '<span class="ico-placeholder" aria-hidden="true"></span>'
        lines_carry.append(
            f'<li class="carry-line">{open_ico}'
            f'<span class="carry-body"><span class="carry-kind">orphan file</span> '
            f'<code>{html.escape(ps)}</code></span></li>'
        )

    warn_html = ""
    if warn_lines:
        warn_html = (
            '<div class="warn"><strong>Warning — uncategorized carry-forward</strong><p>'
            + "</p><p>".join(warn_lines)
            + "</p></div>"
        )

    jsonld_block = ""
    if document is not None:
        graph_doc_label = (
            html.escape("session_bundle.jsonld ")
            + "<code>@graph</code>"
            + html.escape(" — full JSON-LD (opens in a new tab; not embedded here)")
        )
        jsonld_block = (
            "<section><h2>Parallel view — same @graph as would be POSTed (offline)</h2>"
            "<p class=\"small\">This is the document your adapter would send after swapping <code>file:</code> "
            "URLs for HTTPS artifact locations. Open the file instead of scrolling a huge inline dump.</p>"
            "<ul class=\"graph-doc-lines\">"
            f"{_bundle_doc_line('./session_bundle.jsonld', graph_doc_label)}"
            "</ul></section>"
        )

    graph_viewer_section = _build_graph_viewer_preview_section(resolved, session_name=session_name)

    devlog_link = ""
    if leftovers_present:
        devlog_link = " " + _bundle_top_link(
            "./companion_carry_forward_devlog.txt",
            "companion_carry_forward_devlog.txt",
        )

    top_links = (
        _bundle_top_link("./session_bundle.jsonld", "session_bundle.jsonld")
        + _bundle_top_link("./package_manifest.json", "package_manifest.json")
        + _bundle_top_link("./leftover_report.json", "leftover_report.json")
        + devlog_link
    )

    modeled_block = (
        f'<ul class="compact-lines">{"".join(lines_modeled)}</ul>'
        if lines_modeled
        else '<p class="none-hint">No resolved artifacts.</p>'
    )
    carry_block = (
        f'<ul class="compact-lines">{"".join(lines_carry)}</ul>'
        if lines_carry
        else '<p class="none-hint">None.</p>'
    )

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>CV Zebrafish — publication preview (offline)</title>
<style>
body {{
  font-family: Segoe UI, system-ui, sans-serif;
  background: #1e1e1e;
  color: #e0e0e0;
  margin: 0;
  padding: 24px 32px 48px;
  line-height: 1.45;
}}
h1 {{ font-size: 1.35rem; font-weight: 600; margin-bottom: 0.25rem; }}
.sub {{ color: #858585; font-size: 0.9rem; margin-bottom: 1.25rem; }}
.warn {{
  background: #3a2f1a;
  border: 1px solid #a67c00;
  border-radius: 8px;
  padding: 12px 16px;
  margin: 16px 0 24px;
}}
.warn strong {{ color: #ffcc66; }}
section {{ margin-top: 28px; }}
h2 {{ font-size: 1.05rem; margin-bottom: 10px; color: #cccccc; }}
code {{ font-size: 0.84rem; }}
a {{ color: #569cd6; }}
.links {{ display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; margin: 8px 0 4px; }}
.top-bundle-link {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 10px;
  color: #569cd6;
  text-decoration: none;
}}
.top-bundle-link:hover {{ color: #7eb8e8; }}
.top-bundle-link span:last-child {{ text-decoration: underline; }}
.small {{ font-size: 0.82rem; color: #858585; margin-top: 8px; }}
.compact-lines {{
  list-style: none;
  padding: 0;
  margin: 10px 0 0 0;
  border: 1px solid #3e3e42;
  border-radius: 8px;
  background: #252526;
}}
.artifact-line, .carry-line {{
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #3e3e42;
  font-size: 0.88rem;
}}
.artifact-line:last-child, .carry-line:last-child {{ border-bottom: none; }}
.artifact-meta {{ flex: 1; min-width: 0; }}
.artifact-name {{ font-weight: 600; }}
.artifact-sep, .artifact-prov {{ color: #858585; }}
.carry-kind {{ font-weight: 600; color: #858585; margin-right: 6px; }}
.carry-body {{ flex: 1; min-width: 0; word-break: break-word; }}
.carry-src {{ color: #858585; font-size: 0.82rem; }}
.ico-placeholder {{
  display: inline-block;
  width: 15px;
  height: 15px;
  flex: 0 0 15px;
}}
.none-hint {{ color: #858585; font-size: 0.88rem; margin-top: 10px; }}
.graph-doc-lines {{
  list-style: none;
  padding: 0;
  margin: 12px 0 0 0;
}}
.doc-graph-line {{ margin: 8px 0; }}
.doc-line-a {{
  display: inline-flex;
  align-items: flex-start;
  gap: 8px;
  color: #569cd6;
  text-decoration: none;
}}
.doc-line-a:hover {{ color: #7eb8e8; }}
.doc-line-txt {{ flex: 1; min-width: 0; line-height: 1.35; }}
.doc-line-ico {{ flex: 0 0 auto; line-height: 0; padding-top: 2px; }}
.gvf-outer {{ margin-top: 28px; }}
.gvf-chrome {{
  border: 1px solid #3e3e42;
  border-radius: 8px;
  background: #252526;
  overflow: hidden;
}}
.gvf-context {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  background: #2d2d30;
  border-bottom: 1px solid #3e3e42;
}}
.gvf-ctx-icon {{ color: #569cd6; font-size: 0.85rem; line-height: 1.4; }}
.gvf-ctx-text {{ flex: 1; font-size: 0.88rem; color: #d0d0d0; }}
.gvf-ctx-k {{ color: #858585; margin-right: 6px; }}
.gvf-tabs {{
  display: flex;
  gap: 0;
  border-bottom: 1px solid #3e3e42;
  background: #2d2d30;
  padding: 0 8px;
}}
.gvf-tab {{
  padding: 10px 16px;
  font-size: 0.86rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}}
.gvf-tab-active {{
  color: #e0e0e0;
  font-weight: 600;
  border-bottom-color: #569cd6;
}}
.gvf-tab-disabled {{
  color: #6a6a6a;
  cursor: default;
}}
.gvf-panel {{
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 12px;
  min-height: 480px;
  padding: 12px;
}}
.gvf-left {{
  flex: 0 0 min(280px, 32vw);
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}}
.gvf-csv-row {{
  display: flex;
  align-items: center;
  gap: 6px;
}}
.gvf-navbtn {{
  flex: 0 0 auto;
  padding: 6px 10px;
  font-size: 0.8rem;
  border-radius: 4px;
  border: 1px solid #555;
  background: #3c3c3c;
  color: #e0e0e0;
  cursor: pointer;
}}
.gvf-navbtn:hover {{ background: #4a4a4a; }}
.gvf-select {{
  flex: 1;
  min-width: 0;
  padding: 6px 8px;
  font-size: 0.82rem;
  border-radius: 4px;
  border: 1px solid #555;
  background: #1e1e1e;
  color: #e0e0e0;
}}
.gvf-listhead {{
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #858585;
}}
.gvf-list {{
  flex: 1;
  min-height: 260px;
  max-height: 68vh;
  overflow-y: auto;
  background: #1e1e1e;
  border: 1px solid #3e3e42;
  border-radius: 4px;
  padding: 4px 0;
}}
.gvf-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  margin: 2px 6px;
  border-radius: 4px;
}}
.gvf-row:hover {{ background: #2d2d30; }}
.gvf-row.gvf-selected {{
  background: #094771;
  outline: 1px solid #569cd6;
}}
.gvf-pick {{
  flex: 1;
  min-width: 0;
  text-align: left;
  padding: 6px 8px;
  font-size: 0.86rem;
  border-radius: 4px;
  border: 1px solid #444;
  background: #333;
  color: #e8e8e8;
  cursor: pointer;
}}
.gvf-pick:hover {{ background: #3d3d3d; }}
.gvf-open {{
  flex: 0 0 auto;
  color: #569cd6;
  line-height: 0;
  padding: 4px;
  border-radius: 4px;
}}
.gvf-open:hover {{ color: #7eb8e8; background: #2a2a2a; }}
.gvf-open .open-tab-svg {{ display: block; }}
.open-file-ico {{
  display: inline-flex;
  color: #569cd6;
  vertical-align: middle;
  line-height: 0;
}}
.open-file-ico:hover {{
  color: #7eb8e8;
}}
.open-file-ico .open-tab-svg {{
  display: block;
}}
.gvf-right {{
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}}
.gvf-caption {{
  font-size: 0.9rem;
  color: #cccccc;
  margin-bottom: 8px;
  min-height: 1.3em;
  word-break: break-word;
}}
.gvf-frame {{
  display: none;
  flex: 1;
  width: 100%;
  min-height: 400px;
  border: 1px solid #444;
  border-radius: 6px;
  background: #111;
}}
.gvf-img {{
  display: none;
  max-width: 100%;
  height: auto;
  align-self: center;
}}
.gvf-empty {{
  flex: 1;
  display: none;
  align-items: center;
  justify-content: center;
  color: #858585;
  border: 1px dashed #3e3e42;
  border-radius: 6px;
  min-height: 200px;
  text-align: center;
  padding: 16px;
}}
</style></head><body>
<h1>{html.escape(session_name)}</h1>
<p class="sub">Offline preview: JSON-LD is the registration-shaped summary; plot bytes stay as files until you host them at HTTPS for a real POST. Modeled lines match <code>@graph</code> MediaObject entries; carry-forward is only in <code>leftover_report.json</code>.</p>
<p class="links">{top_links}</p>
{warn_html}
{graph_viewer_section}
<section><h2>In JSON-LD @graph (modeled outputs)</h2>
<p class="small">Each row: open-in-new-tab icon, then file name, encoding, and provenance.</p>
{modeled_block}
</section>
<section><h2>Carry-forward (not separate RERUM / @graph objects)</h2>
<p class="small">Compact list; line-by-line detail is in <code>companion_carry_forward_devlog.txt</code> (when this bundle has carry-forward) and <code>leftover_report.json</code>. Orphan files that still exist on disk get the same open icon.</p>
{carry_block}
</section>
{jsonld_block}
<p class="small">Companion tool: cv_zebrafish_rerum — no POST performed.</p>
</body></html>"""

    dest = run_folder / "publication_preview.html"
    dest.write_text(body, encoding="utf-8")
    return dest


def write_package_manifest(
    run_folder: Path,
    *,
    session_name: str,
    leftovers_present: bool,
    companion_devlog: str,
    leftover_report: dict[str, Any],
) -> Path:
    payload: dict[str, Any] = {
        "version": 1,
        "kind": "cv_zebrafish_rerum_offline_bundle",
        "session_name": session_name,
        "session_bundle_jsonld": "session_bundle.jsonld",
        "leftover_report": "leftover_report.json",
        "ingest_meta": "ingest_meta.json",
        "publication_preview_html": "publication_preview.html",
        "has_uncategorized_carry_forward": leftovers_present,
        "leftovers_present": leftovers_present,
        "companion_devlog": companion_devlog,
        "staging_relative": "shadow_store/staging/",
        "notes": (
            "Zip this folder to move the dry-run bundle. JSON-LD connects to outputs: each modeled artifact's "
            "MediaObject.url is a file: URI to the resolved path on disk (see modeled list and graph preview in "
            "publication_preview.html). Dataset no longer lists duplicate associatedMedia @id entries — size scales "
            "mainly with the number of MediaObject nodes. For Tiny Things POST later: upload blobs to HTTPS, replace "
            "file: URLs in JSON-LD, then POST with Bearer token."
        ),
    }
    if leftovers_present:
        payload["carry_forward_devlog"] = "companion_carry_forward_devlog.txt"
    dest = run_folder / "package_manifest.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest
