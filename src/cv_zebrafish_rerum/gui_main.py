"""
Desktop UI for cv_zebrafish_rerum (PyQt5). Does not import cv_zebrafish (main app).
Install: pip install 'cv-zebrafish-rerum[gui]'
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from PyQt5.QtCore import QEvent, QFileSystemWatcher, Qt, QTimer
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cv_zebrafish_rerum.carry_forward_devlog import write_last_carry_forward_devlog
from cv_zebrafish_rerum import __version__
from cv_zebrafish_rerum.gui_prefs import load_startup_cv_root, persist_cv_zebrafish_root
from cv_zebrafish_rerum.ingest_core import analyze_session
from cv_zebrafish_rerum.session_discovery import display_label_for_session_json, iter_session_json_files
from cv_zebrafish_rerum.shadow_index import load_index
from cv_zebrafish_rerum.shadow_store import write_run_bundle
from cv_zebrafish_rerum.stage_open import stage_file


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _manifest_path() -> Path:
    """Companion-bundled manifest (not editable in UI)."""
    return _repo_root() / "session_manifest.json"


def _apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    c_bg = QColor("#1e1e1e")
    c_panel = QColor("#252526")
    c_text = QColor("#e0e0e0")
    c_muted = QColor("#858585")
    c_accent = QColor("#569cd6")
    pal.setColor(QPalette.Window, c_bg)
    pal.setColor(QPalette.WindowText, c_text)
    pal.setColor(QPalette.Base, c_panel)
    pal.setColor(QPalette.AlternateBase, QColor("#2d2d30"))
    pal.setColor(QPalette.Text, c_text)
    pal.setColor(QPalette.Button, QColor("#3c3c3c"))
    pal.setColor(QPalette.ButtonText, c_text)
    pal.setColor(QPalette.Highlight, c_accent)
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, c_panel)
    pal.setColor(QPalette.ToolTipText, c_text)
    pal.setColor(QPalette.PlaceholderText, c_muted)
    app.setPalette(pal)
    app.setStyleSheet(
        """
        QGroupBox {
            border: 1px solid #3e3e42;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 8px;
            font-weight: bold;
            color: #e0e0e0;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
        }
        QLineEdit, QPlainTextEdit, QListWidget, QTableWidget {
            background-color: #252526;
            color: #e0e0e0;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            selection-background-color: #569cd6;
            selection-color: #ffffff;
        }
        QHeaderView::section {
            background-color: #2d2d30;
            color: #e0e0e0;
            border: 1px solid #3e3e42;
            padding: 4px;
        }
        QPushButton {
            background-color: #3c3c3c;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 14px;
            min-height: 22px;
        }
        QPushButton:hover { background-color: #4a4a4a; }
        QPushButton:pressed { background-color: #333333; }
        QPushButton:disabled { color: #656565; border-color: #444444; }
        QTabWidget::pane {
            border: 1px solid #3e3e42;
            border-radius: 4px;
            top: -1px;
        }
        QTabBar::tab {
            background: #2d2d30;
            color: #cccccc;
            padding: 8px 18px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: #1e1e1e;
            color: #ffffff;
            border-bottom: 2px solid #569cd6;
        }
        QTabBar::tab:!selected:hover { background: #383838; }
        QCheckBox { color: #e0e0e0; spacing: 8px; }
        QCheckBox::indicator { width: 16px; height: 16px; }
        QScrollBar:vertical {
            background: #252526;
            width: 12px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #5a5a5a;
            min-height: 24px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover { background: #6e6e6e; }
        QScrollBar:horizontal {
            background: #252526;
            height: 12px;
        }
        QScrollBar::handle:horizontal {
            background: #5a5a5a;
            min-width: 24px;
            border-radius: 4px;
        }
        QLabel { color: #e0e0e0; }
        QListWidget::item { padding: 6px 8px; }
        QListWidget::item:selected { background: #569cd6; color: #ffffff; }
        QListWidget::item:hover:!selected { background: #2d2d30; }
        """
    )


class MainWindow(QWidget):
    SESSION_ROLE = Qt.UserRole + 1

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"CV Zebrafish RERUM companion (offline) — v{__version__}")
        self.resize(920, 640)

        self._last_result = None
        self._watch_timer = QTimer(self)
        self._watch_timer.setSingleShot(True)
        self._watch_timer.timeout.connect(self._do_analyze_debounced)

        root_layout = QVBoxLayout(self)
        tabs = QTabWidget()
        root_layout.addWidget(tabs)

        tabs.addTab(self._build_ingest_tab(), "Ingest")
        tabs.addTab(self._build_local_bundle_tab(), "Local bundle")

        foot = QHBoxLayout()
        foot.addStretch()
        self.lbl_busy = QLabel("")
        self.lbl_busy.setStyleSheet("color: #569cd6; padding: 4px 10px; font-size: 12px;")
        self.lbl_busy.hide()
        foot.addWidget(self.lbl_busy)
        root_layout.addLayout(foot)

        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.fileChanged.connect(self._on_file_changed)

        startup = load_startup_cv_root(_repo_root())
        if startup:
            self.ed_cv_root.setText(startup)
            self._refresh_session_list()

    # --- Ingest tab ---
    def _build_ingest_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        paths = QGroupBox("CV Zebrafish app folder")
        gl = QGridLayout(paths)
        self.ed_cv_root = QLineEdit()
        self.ed_cv_root.setPlaceholderText("Folder that contains data/sessions/ …")
        self.ed_cv_root.editingFinished.connect(self._on_cv_root_editing_finished)
        bt_cv = QPushButton("Browse…")
        bt_cv.clicked.connect(self._pick_cv_root)
        bt_refresh = QPushButton("Refresh session list")
        bt_refresh.clicked.connect(self._refresh_session_list)
        gl.addWidget(QLabel("cv_zebrafish root"), 0, 0)
        gl.addWidget(self.ed_cv_root, 0, 1)
        gl.addWidget(bt_cv, 0, 2)
        gl.addWidget(bt_refresh, 0, 3)

        lbl_sess = QLabel("Sessions")
        lbl_sess.setAlignment(Qt.AlignTop)
        gl.addWidget(lbl_sess, 1, 0)
        self.list_sessions = QListWidget()
        self.list_sessions.setMinimumHeight(200)
        self.list_sessions.setAlternatingRowColors(True)
        self.list_sessions.itemSelectionChanged.connect(self._on_session_selected)
        self.list_sessions.itemDoubleClicked.connect(lambda _: self._do_analyze(quiet=False))
        gl.addWidget(self.list_sessions, 1, 1, 1, 3)

        hint = QLabel(
            "Pick the main app clone folder once. Sessions under data/sessions/ appear here; "
            "double-click a session or press Analyze. The selected session.json is watched automatically "
            "for saves (background refresh)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #858585; font-size: 11px;")
        gl.addWidget(hint, 2, 1, 1, 3)

        lay.addWidget(paths)

        man_hint = QLabel(f"Compatibility manifest (automatic): {_manifest_path()}")
        man_hint.setWordWrap(True)
        man_hint.setStyleSheet("color: #858585; font-size: 11px;")
        lay.addWidget(man_hint)

        row = QHBoxLayout()
        self.bt_analyze = QPushButton("Analyze (dry-run)")
        self.bt_analyze.clicked.connect(lambda: self._do_analyze(quiet=False))
        self.bt_emit = QPushButton("Write local bundle")
        self.bt_emit.setEnabled(False)
        self.bt_emit.clicked.connect(self._emit_shadow)
        self.chk_json_preview = QCheckBox("Show JSON-LD preview")
        self.chk_json_preview.setChecked(True)
        row.addWidget(self.bt_analyze)
        row.addWidget(self.bt_emit)
        row.addWidget(self.chk_json_preview)
        row.addStretch()
        lay.addLayout(row)

        self.lbl_stats = QLabel("Resolved: —  Unresolved: —  Orphans: —")
        lay.addWidget(self.lbl_stats)

        self.txt_compat = QPlainTextEdit()
        self.txt_compat.setReadOnly(True)
        self.txt_compat.setMaximumHeight(72)
        self.txt_compat.setPlaceholderText("Compatibility / manifest warnings …")
        lay.addWidget(self.txt_compat)

        self.txt_jsonld = QPlainTextEdit()
        self.txt_jsonld.setReadOnly(True)
        self.txt_jsonld.setPlaceholderText("JSON-LD preview …")
        lay.addWidget(self.txt_jsonld)
        return w

    def _build_local_bundle_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        intro = QLabel(
            "One offline tree under shadow_store/: runs/<id>/ holds JSON-LD, publication_preview.html "
            "(with embedded plot previews), leftover_report.json, and companion_carry_forward_devlog.txt when needed; "
            "staging/ holds copies for safe browser open. When a session is selected on Ingest, session.json is watched "
            "automatically — analysis re-runs in the background when the main app saves (see corner status).",
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #858585; font-size: 12px;")
        lay.addWidget(intro)
        row = QHBoxLayout()
        bt_refresh = QPushButton("Refresh index")
        bt_refresh.clicked.connect(self._refresh_shadow_index)
        row.addWidget(bt_refresh)
        row.addStretch()
        lay.addLayout(row)
        self.tbl_shadow = QTableWidget(0, 6)
        self.tbl_shadow.setHorizontalHeaderLabels(
            ["id", "resolved", "unresolved", "orphans", "bundle", "created"]
        )
        self.tbl_shadow.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl_shadow)
        row_bt = QHBoxLayout()
        bt_open = QPushButton("Open selected run folder")
        bt_open.clicked.connect(self._open_selected_run_folder)
        bt_prev = QPushButton("Open publication preview (browser)")
        bt_prev.clicked.connect(self._open_selected_publication_preview)
        row_bt.addWidget(bt_open)
        row_bt.addWidget(bt_prev)
        row_bt.addStretch()
        lay.addLayout(row_bt)

        lay.addWidget(QLabel("Stage any artifact for browser (same tree as bundles, not session paths):"))
        row_s = QHBoxLayout()
        self.ed_stage = QLineEdit()
        self.ed_stage.setPlaceholderText("Pick a plot HTML / PNG …")
        bt_pick = QPushButton("Browse file…")
        bt_pick.clicked.connect(self._pick_stage_file)
        row_s.addWidget(self.ed_stage)
        row_s.addWidget(bt_pick)
        lay.addLayout(row_s)
        row_s2 = QHBoxLayout()
        bt_copy = QPushButton("Copy to shadow_store/staging/")
        bt_copy.clicked.connect(self._stage_copy)
        self.chk_browser = QCheckBox("Open in default browser")
        self.chk_browser.setChecked(True)
        row_s2.addWidget(bt_copy)
        row_s2.addWidget(self.chk_browser)
        row_s2.addStretch()
        lay.addLayout(row_s2)
        self.lbl_staged = QLabel("")
        self.lbl_staged.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_staged.setStyleSheet("color: #858585; font-size: 11px;")
        lay.addWidget(self.lbl_staged)
        lay.addStretch()
        self._refresh_shadow_index()
        return w

    # --- paths ---
    def _cv_root_path(self) -> Path | None:
        raw = self.ed_cv_root.text().strip()
        if not raw:
            return None
        p = Path(raw)
        return p if p.is_dir() else None

    def _persist_cv_root(self) -> None:
        persist_cv_zebrafish_root(_repo_root(), self.ed_cv_root.text())

    def _on_cv_root_editing_finished(self) -> None:
        self._persist_cv_root()
        cv = self._cv_root_path()
        if cv is not None and (cv / "data" / "sessions").is_dir():
            self._refresh_session_list()

    def _selected_session_json(self) -> Path | None:
        items = self.list_sessions.selectedItems()
        if not items:
            return None
        data = items[0].data(self.SESSION_ROLE)
        if not data:
            return None
        return Path(str(data))

    def _pick_cv_root(self) -> None:
        start = self.ed_cv_root.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "cv_zebrafish repo root", start)
        if path:
            self.ed_cv_root.setText(path)
            self._persist_cv_root()
            self._refresh_session_list()

    def _refresh_session_list(self) -> None:
        self.list_sessions.clear()
        cv_root = self._cv_root_path()
        if cv_root is None:
            return
        self._persist_cv_root()
        sessions_dir = cv_root / "data" / "sessions"
        if not sessions_dir.is_dir():
            QMessageBox.warning(
                self,
                "Sessions",
                f"No folder data/sessions under:\n{cv_root}\n\nPick the CV Zebrafish clone root.",
            )
            return
        paths = iter_session_json_files(cv_root)
        for jp in paths:
            label = display_label_for_session_json(jp)
            it = QListWidgetItem(label)
            it.setData(self.SESSION_ROLE, str(jp.resolve()))
            it.setToolTip(str(jp.resolve()))
            self.list_sessions.addItem(it)
        if self.list_sessions.count():
            self.list_sessions.setCurrentRow(0)
        self._sync_session_file_watcher()

    def _sync_session_file_watcher(self) -> None:
        self._fs_watcher.removePaths(self._fs_watcher.files())
        p = self._selected_session_json()
        if p and p.is_file():
            self._fs_watcher.addPath(str(p.resolve()))

    def _on_session_selected(self) -> None:
        self._sync_session_file_watcher()

    def _pick_stage_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Artifact", str(Path.home()))
        if path:
            self.ed_stage.setText(path)

    def _do_analyze(self, *, quiet: bool = False) -> None:
        session_json = self._selected_session_json()
        manifest = _manifest_path()
        cv_root = self._cv_root_path()
        if cv_root is None:
            QMessageBox.warning(self, "Analyze", "Browse to your CV Zebrafish app folder first.")
            return
        if session_json is None or not session_json.is_file():
            QMessageBox.warning(self, "Analyze", "Select a session from the list.")
            return
        if not manifest.is_file():
            QMessageBox.warning(self, "Analyze", f"Missing companion manifest:\n{manifest}")
            return
        self.lbl_busy.setText("Refreshing session…")
        self.lbl_busy.show()
        QApplication.processEvents()
        try:
            result = analyze_session(
                session_json_path=session_json,
                cv_root=cv_root,
                manifest_path=manifest,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Analyze", str(e))
            return
        finally:
            self.lbl_busy.clear()
            self.lbl_busy.hide()

        self._last_result = result
        self.bt_emit.setEnabled(True)
        self.lbl_stats.setText(
            f"Resolved: {len(result.resolved)}  Unresolved: {len(result.unresolved)}  "
            f"Orphans: {len(result.orphans)}"
        )
        lr = result.leftover_report
        devlog_path = write_last_carry_forward_devlog(_repo_root(), lr)
        if devlog_path is not None and not quiet:
            QMessageBox.warning(
                self,
                "Carry-forward detected",
                "This session has uncategorized paths or orphan output files (not modeled as separate "
                "JSON-LD MediaObject nodes).\n\n"
                f"Human-readable detail:\n{devlog_path}\n\n"
                "After you write a local bundle, the same text is copied to:\n"
                "companion_carry_forward_devlog.txt next to leftover_report.json.",
            )

        lines = [result.compatibility_note]
        lines.extend(result.manifest_warnings)
        self.txt_compat.setPlainText("\n".join(lines))

        if self.chk_json_preview.isChecked():
            self.txt_jsonld.setPlainText(json.dumps(result.document, indent=2))
        else:
            self.txt_jsonld.clear()

        self._refresh_shadow_index()

    def _emit_shadow(self) -> None:
        if self._last_result is None:
            return
        session_json = self._selected_session_json()
        if session_json is None:
            return
        result = self._last_result
        try:
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
        except OSError as e:
            QMessageBox.critical(self, "Local bundle", str(e))
            return
        preview = dest.parent / "publication_preview.html"
        reply = QMessageBox.question(
            self,
            "Local bundle",
            f"Wrote offline bundle under:\n{dest.parent}\n\nOpen publication preview in browser?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes and preview.is_file():
            webbrowser.open(preview.resolve().as_uri())
        self._refresh_shadow_index()

    def _refresh_shadow_index(self) -> None:
        idx = load_index(_repo_root())
        runs = list(idx.get("runs") or [])
        self.tbl_shadow.setRowCount(0)
        for run in runs:
            r = self.tbl_shadow.rowCount()
            self.tbl_shadow.insertRow(r)
            self.tbl_shadow.setItem(r, 0, QTableWidgetItem(str(run.get("id", ""))))
            self.tbl_shadow.setItem(r, 1, QTableWidgetItem(str(run.get("resolved_count", ""))))
            self.tbl_shadow.setItem(r, 2, QTableWidgetItem(str(run.get("unresolved_count", ""))))
            self.tbl_shadow.setItem(r, 3, QTableWidgetItem(str(run.get("orphan_count", ""))))
            self.tbl_shadow.setItem(r, 4, QTableWidgetItem(str(run.get("bundle_jsonld", ""))))
            self.tbl_shadow.setItem(r, 5, QTableWidgetItem(str(run.get("created", ""))))

    def _open_selected_publication_preview(self) -> None:
        rows = self.tbl_shadow.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Local bundle", "Select a row first.")
            return
        row = rows[0].row()
        path_item = self.tbl_shadow.item(row, 4)
        if not path_item:
            return
        bundle = Path(path_item.text())
        preview = bundle.parent / "publication_preview.html"
        if not preview.is_file():
            QMessageBox.warning(
                self,
                "Local bundle",
                f"No publication_preview.html next to bundle:\n{preview}",
            )
            return
        webbrowser.open(preview.resolve().as_uri())

    def _open_selected_run_folder(self) -> None:
        rows = self.tbl_shadow.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Local bundle", "Select a row first.")
            return
        row = rows[0].row()
        path_item = self.tbl_shadow.item(row, 4)
        if not path_item:
            return
        bundle = Path(path_item.text())
        folder = bundle.parent
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)

    def _stage_copy(self) -> None:
        src = Path(self.ed_stage.text().strip())
        if not src.is_file():
            QMessageBox.warning(self, "Staging", "Pick an existing file.")
            return
        try:
            staged = stage_file(_repo_root(), src)
        except OSError as e:
            QMessageBox.critical(self, "Staging", str(e))
            return
        uri = staged.resolve().as_uri()
        self.lbl_staged.setText(f"Staged:\n{staged}\n{uri}")
        if self.chk_browser.isChecked():
            webbrowser.open(uri)

    def _on_file_changed(self, path: str) -> None:
        self._watch_timer.start(400)

    def _do_analyze_debounced(self) -> None:
        self._do_analyze(quiet=True)

    def closeEvent(self, event: QEvent) -> None:
        self._persist_cv_root()
        super().closeEvent(event)


def run_gui() -> int:
    app = QApplication(sys.argv)
    _apply_dark_theme(app)
    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(run_gui())
