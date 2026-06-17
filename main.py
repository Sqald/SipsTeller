#!/usr/bin/env python3
"""SipsTeller — baresip GUI client (PyQt6)"""

import argparse
import hashlib
import re
import sys
import threading
import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QFrame, QMessageBox, QDialogButtonBox,
)

from config_manager import ConfigManager
from baresip import BaresipManager


_DTMF_VALID = set("0123456789*#")
_NUMPAD_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]

_APP_STYLE = """
QWidget {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
}
QPushButton {
    border-radius: 6px;
    border: none;
    font-size: 11pt;
    min-height: 38px;
    padding: 2px 8px;
    background: #e2e8f0;
    color: #1e293b;
}
QPushButton:disabled {
    background: #f1f5f9;
    color: #b0bec5;
}
QLineEdit {
    border: 1.5px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12pt;
    background: white;
    color: #0f172a;
}
QLineEdit:focus {
    border-color: #3b82f6;
}
"""


def _make_uri(number: str, domain: str, port: str) -> str:
    if number.startswith("sip:"):
        return number
    if "@" in number:
        return f"sip:{number}"
    if port and port != "5060":
        return f"sip:{number}@{domain}:{port}"
    return f"sip:{number}@{domain}"


class CallState(Enum):
    IDLE      = "idle"
    INCOMING  = "incoming"
    DIALING   = "dialing"
    CONNECTED = "connected"
    ON_HOLD   = "on_hold"


class _Bridge(QObject):
    line_received = pyqtSignal(str)


# ── Dialogs ───────────────────────────────────────────────────────────────────

class NumpadDialog(QDialog):
    def __init__(self, parent, config, *, on_dial=None, on_hangup=None,
                 dtmf_mode=False, on_dtmf=None):
        super().__init__(parent)
        self._config    = config
        self._on_dial   = on_dial
        self._on_hangup = on_hangup
        self._dtmf      = dtmf_mode
        self._on_dtmf   = on_dtmf
        self._number    = ""

        self.setWindowTitle("DTMF" if dtmf_mode else "Numpad")
        w = max(config.getint("window", "width_numpad",  280), 260)
        h = max(config.getint("window", "height_numpad", 460), 420)
        self.resize(w, h)
        self.setMinimumSize(260, 420)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)

        disp_frame = QFrame()
        disp_frame.setStyleSheet("QFrame { background: #1e293b; border-radius: 8px; }")
        disp_layout = QHBoxLayout(disp_frame)
        disp_layout.setContentsMargins(12, 10, 12, 10)
        self._display = QLabel("")
        self._display.setFont(QFont("Courier New", 24, QFont.Weight.Bold))
        self._display.setStyleSheet("color: #f8fafc; background: transparent;")
        self._display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._display.setMinimumHeight(52)
        disp_layout.addWidget(self._display)
        layout.addWidget(disp_frame)

        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setSpacing(5)

        _key_style = (
            "QPushButton { background:#1e293b; color:#f8fafc; border-radius:8px; font-size:18pt; }"
            "QPushButton:hover { background:#334155; }"
            "QPushButton:pressed { background:#0f172a; }"
        )
        for idx, key in enumerate(_NUMPAD_KEYS):
            r, c = divmod(idx, 3)
            btn = QPushButton(key)
            btn.setFont(QFont("Helvetica", 18))
            btn.setMinimumHeight(56)
            btn.setStyleSheet(_key_style)
            btn.clicked.connect(lambda _, k=key: self._press(k))
            grid.addWidget(btn, r, c)

        back = QPushButton("⌫")
        back.setFont(QFont("Helvetica", 16))
        back.setMinimumHeight(52)
        back.setStyleSheet(
            "QPushButton { background:#334155; color:#94a3b8; border-radius:8px; font-size:16pt; }"
            "QPushButton:hover { background:#475569; }"
        )
        back.clicked.connect(self._back)
        grid.addWidget(back, 4, 0)

        if self._dtmf:
            close = QPushButton("閉じる")
            close.setFont(QFont("Helvetica", 13))
            close.setMinimumHeight(52)
            close.clicked.connect(self.close)
            grid.addWidget(close, 4, 1, 1, 2)
        else:
            call = QPushButton("発信")
            call.setFont(QFont("Helvetica", 15, QFont.Weight.Bold))
            call.setMinimumHeight(52)
            call.setStyleSheet(
                "QPushButton { background:#22c55e; color:white; border-radius:8px; font-size:15pt; }"
                "QPushButton:hover { background:#16a34a; }"
            )
            call.clicked.connect(self._call)
            grid.addWidget(call, 4, 1)

            hang = QPushButton("切断")
            hang.setFont(QFont("Helvetica", 13, QFont.Weight.Bold))
            hang.setMinimumHeight(52)
            hang.setStyleSheet(
                "QPushButton { background:#ef4444; color:white; border-radius:8px; font-size:13pt; }"
                "QPushButton:hover { background:#dc2626; }"
            )
            if self._on_hangup:
                hang.clicked.connect(self._on_hangup)
            grid.addWidget(hang, 4, 2)

        layout.addWidget(grid_w)

    def keyPressEvent(self, event):
        ch = event.text()
        if ch in _DTMF_VALID:
            self._press(ch)
        elif event.key() == Qt.Key.Key_Backspace:
            self._back()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not self._dtmf:
            self._call()
        else:
            super().keyPressEvent(event)

    def _press(self, key: str):
        self._number += key
        self._display.setText(self._number)
        if self._dtmf and self._on_dtmf:
            self._on_dtmf(key)

    def _back(self):
        self._number = self._number[:-1]
        self._display.setText(self._number)

    def _call(self):
        n = self._number.strip()
        if n and self._on_dial:
            self._on_dial(n)
            self.close()

    def closeEvent(self, event):
        try:
            self._config.set("window", "width_numpad",  self.width())
            self._config.set("window", "height_numpad", self.height())
            self._config.save()
        except Exception:
            pass
        super().closeEvent(event)


class TransferDialog(QDialog):
    def __init__(self, parent, config, on_blind, on_attended):
        super().__init__(parent)
        self._config      = config
        self._on_blind    = on_blind
        self._on_attended = on_attended
        self.setWindowTitle("通話転送")
        self.setModal(True)
        self._build()
        self.exec()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 16)

        layout.addWidget(QLabel("転送先（番号または SIP URI）:"))

        self._entry = QLineEdit()
        self._entry.setFont(QFont("Helvetica", 13))
        self._entry.setPlaceholderText("例: 1001 または sip:1001@example.com")
        layout.addWidget(self._entry)

        hint = QLabel("番号のみ入力すると SIP ドメインを自動付与します")
        hint.setStyleSheet("color: #64748b; font-size: 9pt;")
        layout.addWidget(hint)

        desc = QFrame()
        desc.setStyleSheet(
            "QFrame { background:#f1f5f9; border-radius:6px; border:1px solid #e2e8f0; }"
        )
        dl = QVBoxLayout(desc)
        dl.setContentsMargins(10, 8, 10, 8)
        dl.setSpacing(4)
        for txt in (
            "● ブラインド転送 — 相手をすぐに転送（現在の通話終了）",
            "● 代理転送 — 先に転送先へ発信し確認してから転送",
        ):
            lbl = QLabel(txt)
            lbl.setStyleSheet("color:#475569; font-size:10pt; background:transparent;")
            dl.addWidget(lbl)
        layout.addWidget(desc)

        layout.addSpacing(4)
        btns = QHBoxLayout()
        btns.setSpacing(6)

        b1 = QPushButton("ブラインド転送")
        b1.setStyleSheet(
            "QPushButton { background:#3b82f6; color:white; border-radius:6px; }"
            "QPushButton:hover { background:#2563eb; }"
        )
        b1.clicked.connect(lambda: self._do(self._on_blind))
        btns.addWidget(b1)

        b2 = QPushButton("代理転送（保留→発信）")
        b2.clicked.connect(lambda: self._do(self._on_attended))
        btns.addWidget(b2)

        bc = QPushButton("キャンセル")
        bc.clicked.connect(self.reject)
        btns.addWidget(bc)

        layout.addLayout(btns)
        self._entry.returnPressed.connect(lambda: self._do(self._on_blind))

    def _do(self, callback):
        t = self._entry.text().strip()
        if not t:
            return
        uri = _make_uri(t,
                        self._config.get("sip", "domain"),
                        self._config.get("sip", "port", "5060"))
        callback(uri)
        self.accept()


class ConfigDialog(QDialog):
    def __init__(self, parent, config, on_save=None):
        super().__init__(parent)
        self._config      = config
        self._on_save     = on_save
        self._fields      = {}
        self._admin_entry = None

        stored = config.get("admin", "password", "")
        if stored and not self._auth(stored):
            return

        self.setWindowTitle("設定")
        self.setModal(True)
        self._build()
        self.exec()

    def _auth(self, stored_hash: str) -> bool:
        dlg = QDialog(self)
        dlg.setWindowTitle("管理者認証")
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        layout.addWidget(QLabel("管理者パスワード:"))
        entry = QLineEdit()
        entry.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(entry)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        entry.returnPressed.connect(dlg.accept)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        if hashlib.sha256(entry.text().encode()).hexdigest() != stored_hash:
            QMessageBox.critical(self, "エラー", "パスワードが違います。")
            return False
        return True

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(20, 16, 20, 16)

        def section(text):
            layout.addSpacing(10)
            lbl = QLabel(text)
            lbl.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
            lbl.setStyleSheet(
                "color:#0f172a; padding-bottom:4px; "
                "border-bottom: 1px solid #e2e8f0;"
            )
            layout.addWidget(lbl)

        def field(label, sec, key, password=False, placeholder=""):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(185)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet("color:#475569;")
            row.addWidget(lbl)
            entry = QLineEdit(self._config.get(sec, key))
            entry.setMinimumWidth(220)
            if password:
                entry.setEchoMode(QLineEdit.EchoMode.Password)
            if placeholder:
                entry.setPlaceholderText(placeholder)
            self._fields[(sec, key)] = entry
            row.addWidget(entry)
            layout.addLayout(row)

        section("SIP アカウント")
        field("ドメイン / IP アドレス", "sip", "domain")
        field("ポート",                  "sip", "port")
        field("ユーザー名 / 内線番号",   "sip", "username")
        field("パスワード",              "sip", "password", password=True)
        field("認証ユーザー名",          "sip", "auth_user",
              placeholder="空白でユーザー名と同じ")
        field("トランスポート",          "sip", "transport",
              placeholder="udp / tcp / tls")
        field("パーク番号 (park_ext)",   "sip", "park_ext",
              placeholder="例: 700")

        section("外観")
        field("背景色 (#RRGGBB)",        "appearance", "bgcolor")

        section("管理者パスワード変更")
        row = QHBoxLayout()
        lbl = QLabel("新しいパスワード")
        lbl.setFixedWidth(185)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet("color:#475569;")
        row.addWidget(lbl)
        self._admin_entry = QLineEdit()
        self._admin_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self._admin_entry.setPlaceholderText("空白で変更なし")
        self._admin_entry.setMinimumWidth(220)
        row.addWidget(self._admin_entry)
        layout.addLayout(row)

        layout.addSpacing(12)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e2e8f0;")
        layout.addWidget(line)

        btn_row = QHBoxLayout()
        save = QPushButton("保存して閉じる")
        save.setDefault(True)
        save.setStyleSheet(
            "QPushButton { background:#3b82f6; color:white; border-radius:6px; }"
            "QPushButton:hover { background:#2563eb; }"
        )
        save.clicked.connect(self._save)
        btn_row.addWidget(save)
        cancel = QPushButton("キャンセル")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _save(self):
        for (sec, key), entry in self._fields.items():
            self._config.set(sec, key, entry.text().strip())
        p = self._admin_entry.text() if self._admin_entry else ""
        if p:
            self._config.set("admin", "password",
                             hashlib.sha256(p.encode()).hexdigest())
        self._config.save()
        if self._on_save:
            self._on_save()
        self.accept()


# ── Main Window ───────────────────────────────────────────────────────────────

class App(QMainWindow):

    _LOG_COLORS = {
        "info":     "#334155",
        "ok":       "#15803d",
        "warn":     "#b45309",
        "error":    "#dc2626",
        "incoming": "#1d4ed8",
        "hint":     "#7c3aed",
        "dtmf":     "#0e7490",
    }

    _LOG_PREFIX = {
        "ok":       "✓ ",
        "error":    "✗ ",
        "warn":     "⚠ ",
        "incoming": "☎ ",
        "dtmf":     "# ",
        "hint":     "→ ",
        "info":     "  ",
    }

    def __init__(self):
        super().__init__()
        config_dir    = self._parse_args()
        self._config  = ConfigManager(config_dir)
        self._bridge  = _Bridge()
        self._bridge.line_received.connect(self._handle)
        self._baresip = BaresipManager(
            str(self._config.config_dir),
            on_output=lambda line: self._bridge.line_received.emit(line),
        )
        self._state      = CallState.IDLE
        self._caller_id  = ""
        self._call_start = 0.0
        self._muted      = False
        self._buttons    = {}
        self._numpad     = None
        self._dtmf_win   = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_on = False

        self._build()
        self._setup_shortcuts()
        QTimer.singleShot(300, self._start_baresip)

    @staticmethod
    def _parse_args():
        p = argparse.ArgumentParser(add_help=False)
        p.add_argument("-f", "--folder", default=None)
        args, _ = p.parse_known_args()
        if args.folder:
            d = Path(args.folder).expanduser().resolve()
            if d.is_dir():
                return d
        return None

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F8"),     self).activated.connect(self._answer)
        QShortcut(QKeySequence("F9"),     self).activated.connect(self._maybe_hangup)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._maybe_hangup)
        QShortcut(QKeySequence("F10"),    self).activated.connect(self._hold)
        QShortcut(QKeySequence("F11"),    self).activated.connect(self._resume)
        QShortcut(QKeySequence("F12"),    self).activated.connect(self._mute)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._open_numpad)

    def _maybe_hangup(self):
        if self._state != CallState.IDLE:
            self._hangup()

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build(self):
        self.setWindowTitle("SIPTELLER")
        w = max(self._config.getint("window", "width_main",  460), 400)
        h = max(self._config.getint("window", "height_main", 760), 640)
        self.resize(w, h)
        self.setMinimumSize(400, 640)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._apply_bg(central)
        layout.addWidget(self._make_status_bar())
        layout.addWidget(self._make_call_panel())
        layout.addWidget(self._make_dial_bar())
        layout.addWidget(self._make_btn_row1())
        layout.addWidget(self._make_btn_row2())
        layout.addWidget(self._make_log(), stretch=1)
        layout.addWidget(self._make_toolbar())

        self._refresh_buttons()

    def _apply_bg(self, widget):
        bg = self._config.get("appearance", "bgcolor", "#FFFFFF")
        widget.setStyleSheet(f"background: {bg};")

    def _make_status_bar(self):
        bar = QFrame()
        bar.setStyleSheet("QFrame { background: #0f172a; }")
        bar.setFixedHeight(42)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 10, 0)
        lay.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setFont(QFont("Helvetica", 14))
        self._dot.setStyleSheet("color: #475569; background: transparent;")
        lay.addWidget(self._dot)

        self._status_lbl = QLabel("起動中...")
        self._status_lbl.setFont(QFont("Helvetica", 11))
        self._status_lbl.setStyleSheet("color: #94a3b8; background: transparent;")
        lay.addWidget(self._status_lbl, stretch=1)

        self._acct_lbl = QLabel("")
        self._acct_lbl.setFont(QFont("Helvetica", 10))
        self._acct_lbl.setStyleSheet("color: #475569; background: transparent;")
        lay.addWidget(self._acct_lbl)

        rereg = QPushButton("再登録")
        rereg.setFont(QFont("Helvetica", 9))
        rereg.setFixedHeight(26)
        rereg.setStyleSheet(
            "QPushButton { background:#1e293b; color:#64748b; border-radius:4px; "
            "padding:0 8px; min-height:26px; font-size:9pt; }"
            "QPushButton:hover { background:#334155; color:#94a3b8; }"
        )
        rereg.clicked.connect(self._reregister)
        lay.addWidget(rereg)

        return bar

    def _make_call_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: #1e293b; }")
        panel.setFixedHeight(60)
        lay = QHBoxLayout(panel)
        lay.setContentsMargins(12, 0, 14, 0)
        lay.setSpacing(8)

        self._call_state_lbl = QLabel("  待機中")
        self._call_state_lbl.setFont(QFont("Helvetica", 11))
        self._call_state_lbl.setStyleSheet("color: #475569; background: transparent;")
        self._call_state_lbl.setFixedWidth(90)
        lay.addWidget(self._call_state_lbl)

        self._caller_lbl = QLabel("")
        self._caller_lbl.setFont(QFont("Helvetica", 12))
        self._caller_lbl.setStyleSheet("color: #94a3b8; background: transparent;")
        self._caller_lbl.setToolTip("クリックでコピー")
        self._caller_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._caller_lbl.mousePressEvent = self._copy_caller
        lay.addWidget(self._caller_lbl, stretch=1)

        self._duration_lbl = QLabel("")
        self._duration_lbl.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        self._duration_lbl.setStyleSheet("color: #22c55e; background: transparent;")
        self._duration_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._duration_lbl)

        return panel

    def _make_dial_bar(self):
        f = QFrame()
        f.setStyleSheet(
            "QFrame { background: #f8fafc; "
            "border-top: 1px solid #e2e8f0; "
            "border-bottom: 1px solid #e2e8f0; }"
        )
        lay = QHBoxLayout(f)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)

        self._dial_entry = QLineEdit()
        self._dial_entry.setPlaceholderText("番号を入力して Enter で発信")
        self._dial_entry.setFont(QFont("Courier New", 13))
        self._dial_entry.returnPressed.connect(self._dial_from_bar)
        lay.addWidget(self._dial_entry, stretch=1)

        call_btn = QPushButton("発信")
        call_btn.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        call_btn.setFixedWidth(72)
        call_btn.setStyleSheet(
            "QPushButton { background:#22c55e; color:white; border-radius:6px; font-size:12pt; }"
            "QPushButton:hover { background:#16a34a; }"
            "QPushButton:pressed { background:#15803d; }"
        )
        call_btn.clicked.connect(self._dial_from_bar)
        lay.addWidget(call_btn)

        return f

    def _btn(self, name, text, cb, active_style=""):
        b = QPushButton(text)
        b.setFont(QFont("Helvetica", 11))
        b.setMinimumHeight(40)
        if active_style:
            b.setStyleSheet(
                f"QPushButton {{ {active_style} border-radius:6px; }}"
                f"QPushButton:disabled {{ background:#e2e8f0; color:#b0bec5; border-radius:6px; }}"
            )
        b.clicked.connect(cb)
        self._buttons[name] = b
        return b

    def _make_btn_row1(self):
        f = QFrame()
        f.setStyleSheet("QFrame { background: transparent; }")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(6, 6, 6, 3)
        lay.setSpacing(5)
        lay.addWidget(self._btn("answer", "Answer",  self._answer,
                                "background:#22c55e; color:white;"))
        lay.addWidget(self._btn("hangup", "Hang up", self._hangup,
                                "background:#ef4444; color:white;"))
        lay.addWidget(self._btn("hold",   "Hold",    self._hold,
                                "background:#f59e0b; color:white;"))
        lay.addWidget(self._btn("resume", "Resume",  self._resume,
                                "background:#3b82f6; color:white;"))
        return f

    def _make_btn_row2(self):
        f = QFrame()
        f.setStyleSheet("QFrame { background: transparent; }")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(6, 3, 6, 6)
        lay.setSpacing(5)
        lay.addWidget(self._btn("transfer", "Transfer", self._transfer,
                                "background:#6366f1; color:white;"))
        lay.addWidget(self._btn("dtmf",     "DTMF",     self._dtmf_open))
        lay.addWidget(self._btn("mute",     "Mute",     self._mute))
        lay.addWidget(self._btn("park",     "Park",     self._park))
        return f

    def _make_log(self):
        container = QFrame()
        container.setStyleSheet(
            "QFrame { background: #f8fafc; border-top: 1px solid #e2e8f0; }"
        )
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background:#f1f5f9; border-bottom:1px solid #e2e8f0; }"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 3, 8, 3)
        hl.setSpacing(0)

        log_lbl = QLabel("ログ")
        log_lbl.setFont(QFont("Helvetica", 9))
        log_lbl.setStyleSheet("color:#64748b; background:transparent;")
        hl.addWidget(log_lbl)

        hl.addStretch()

        hint_lbl = QLabel("F8=応答  F9=切断  F10=保留  F11=解除  F12=ミュート")
        hint_lbl.setFont(QFont("Helvetica", 8))
        hint_lbl.setStyleSheet("color:#94a3b8; background:transparent;")
        hl.addWidget(hint_lbl)

        clear_btn = QPushButton("クリア")
        clear_btn.setFont(QFont("Helvetica", 8))
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#94a3b8; border:none; "
            "min-height:22px; padding:0 8px; font-size:8pt; }"
            "QPushButton:hover { color:#475569; }"
        )
        clear_btn.clicked.connect(lambda: self._log.clear())
        hl.addWidget(clear_btn)

        lay.addWidget(header)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier New", 10))
        self._log.setStyleSheet(
            "QTextEdit { background:#f8fafc; border:none; padding:8px; }"
        )
        lay.addWidget(self._log, stretch=1)
        return container

    def _make_toolbar(self):
        f = QFrame()
        f.setStyleSheet(
            "QFrame { background:#f1f5f9; border-top:1px solid #e2e8f0; }"
        )
        lay = QHBoxLayout(f)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(6)

        nb = QPushButton("Numpad")
        nb.setFont(QFont("Helvetica", 11))
        nb.setStyleSheet(
            "QPushButton { background:#e2e8f0; color:#334155; border-radius:6px; }"
            "QPushButton:hover { background:#cbd5e1; }"
        )
        nb.clicked.connect(self._open_numpad)
        lay.addWidget(nb)

        lay.addStretch()

        kl = QLabel("Ctrl+D: Numpad")
        kl.setFont(QFont("Helvetica", 8))
        kl.setStyleSheet("color:#94a3b8; background:transparent;")
        lay.addWidget(kl)

        lay.addStretch()

        cb = QPushButton("設定")
        cb.setFont(QFont("Helvetica", 11))
        cb.setStyleSheet(
            "QPushButton { background:#e2e8f0; color:#334155; border-radius:6px; }"
            "QPushButton:hover { background:#cbd5e1; }"
        )
        cb.clicked.connect(self._open_config)
        lay.addWidget(cb)

        return f

    # ── State ─────────────────────────────────────────────────────────────────

    def _set_state(self, state: CallState, caller_id: str = ""):
        prev = self._state
        self._state = state
        if caller_id:
            self._caller_id = caller_id

        if state == CallState.INCOMING:
            self._blink_timer.start(500)
        else:
            self._blink_timer.stop()
            self._blink_on = False

        if state == CallState.CONNECTED and prev != CallState.CONNECTED:
            self._call_start = time.time()
            self._timer.start(1000)
        elif state == CallState.IDLE:
            self._timer.stop()
            self._call_start = 0.0
            self._caller_id  = ""
            self._muted      = False
            self._duration_lbl.setText("")

        self._refresh_buttons()
        self._refresh_call_panel()

    def _refresh_buttons(self):
        s = self._state
        en = {
            "answer":   s == CallState.INCOMING,
            "hangup":   s in (CallState.INCOMING, CallState.DIALING,
                               CallState.CONNECTED, CallState.ON_HOLD),
            "hold":     s == CallState.CONNECTED,
            "resume":   s == CallState.ON_HOLD,
            "transfer": s in (CallState.CONNECTED, CallState.ON_HOLD),
            "dtmf":     s == CallState.CONNECTED,
            "mute":     s in (CallState.CONNECTED, CallState.ON_HOLD),
            "park":     s == CallState.CONNECTED,
        }
        for name, btn in self._buttons.items():
            btn.setEnabled(en.get(name, False))

        mute_btn = self._buttons.get("mute")
        if mute_btn:
            if self._muted:
                mute_btn.setText("Unmute")
                mute_btn.setStyleSheet(
                    "QPushButton { background:#ef4444; color:white; border-radius:6px; }"
                    "QPushButton:disabled { background:#e2e8f0; color:#b0bec5; border-radius:6px; }"
                )
            else:
                mute_btn.setText("Mute")
                mute_btn.setStyleSheet(
                    "QPushButton { background:#e2e8f0; color:#334155; border-radius:6px; }"
                    "QPushButton:disabled { background:#e2e8f0; color:#b0bec5; border-radius:6px; }"
                )

    def _refresh_call_panel(self):
        info = {
            CallState.IDLE:      ("  待機中",  "",              "#475569"),
            CallState.INCOMING:  ("[着信中]",  self._caller_id, "#3b82f6"),
            CallState.DIALING:   ("[発信中]",  self._caller_id, "#f59e0b"),
            CallState.CONNECTED: ("[通話中]",  self._caller_id, "#22c55e"),
            CallState.ON_HOLD:   ("[保留中]",  self._caller_id, "#f59e0b"),
        }
        text, caller, color = info[self._state]
        self._call_state_lbl.setText(text)
        self._call_state_lbl.setStyleSheet(f"color:{color}; background:transparent;")
        self._caller_lbl.setText(caller)
        self._caller_lbl.setStyleSheet(f"color:{color}; background:transparent;")

    def _blink(self):
        self._blink_on = not self._blink_on
        color = "#3b82f6" if self._blink_on else "#93c5fd"
        self._call_state_lbl.setStyleSheet(f"color:{color}; background:transparent;")

    def _tick(self):
        if self._state != CallState.CONNECTED or not self._call_start:
            return
        elapsed = int(time.time() - self._call_start)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._duration_lbl.setText(
            f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        )

    def _copy_caller(self, _event):
        if self._caller_id:
            QApplication.clipboard().setText(self._caller_id)
            self._log_line(f"クリップボードにコピーしました: {self._caller_id}", "hint")

    # ── Log ───────────────────────────────────────────────────────────────────

    def _log_line(self, text: str, tag: str = "info"):
        ts     = datetime.now().strftime("%H:%M:%S")
        color  = self._LOG_COLORS.get(tag, "#334155")
        prefix = self._LOG_PREFIX.get(tag, "  ")
        cur    = self._log.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if tag == "incoming":
            fmt.setFontWeight(QFont.Weight.Bold)
        elif tag == "hint":
            fmt.setFontItalic(True)
        elif tag in ("ok", "error"):
            fmt.setFontWeight(QFont.Weight.DemiBold)
        cur.setCharFormat(fmt)
        cur.insertText(f"[{ts}] {prefix}{text}\n")
        self._log.setTextCursor(cur)
        self._log.ensureCursorVisible()

    def _set_status(self, text: str, color: str):
        self._dot.setStyleSheet(f"color:{color}; background:transparent;")
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"color:{color}; background:transparent;")

    # ── baresip ───────────────────────────────────────────────────────────────

    def _start_baresip(self):
        if not self._config.is_sip_configured():
            self._set_status("未設定", "#f59e0b")
            self._log_line("SIP アカウントが未設定です。", "warn")
            self._log_line("「設定」ボタンから設定してください。", "hint")
            return
        self._config.write_baresip_accounts()
        self._log_line("baresip を起動しています...", "info")
        if not self._baresip.start():
            self._set_status("起動失敗", "#dc2626")

    def _reregister(self):
        self._baresip.send("/reg")
        self._log_line("再登録を要求しました。", "info")

    _CMD_ECHO = re.compile(r'^/[a-zA-Z]')

    def _handle(self, line: str):
        s = line.strip()
        if s == "/" or self._CMD_ECHO.match(s):
            return

        low = line.lower()

        if re.search(r'register.*\bok\b|re-register.*200|registr.*success', low):
            self._set_status("登録済み", "#22c55e")
            u = self._config.get("sip", "username")
            d = self._config.get("sip", "domain")
            self._acct_lbl.setText(f"{u}@{d}")
            self._acct_lbl.setStyleSheet("color:#22c55e; background:transparent;")
            self._log_line(f"登録完了: {u}@{d}", "ok")
            return

        if "401 unauthorized" in low:
            self._set_status("認証失敗", "#dc2626")
            self._log_line("認証エラー: SIP パスワードを確認してください。", "error")
            return

        if "403 forbidden" in low:
            if self._state in (CallState.CONNECTED, CallState.ON_HOLD):
                self._log_line("転送が拒否されました (403 Forbidden)。", "warn")
            else:
                self._set_status("認証失敗", "#dc2626")
                self._log_line("認証エラー (403): パスワードを確認してください。", "error")
            return

        if "unregistered" in low or ("register" in low and "fail" in low):
            self._set_status("未登録", "#f59e0b")
            self._acct_lbl.setStyleSheet("color:#64748b; background:transparent;")
            self._log_line("SIP 登録が解除されました。", "warn")
            return

        if "incoming call" in low:
            caller  = self._extract_caller(line)
            display = self._extract_display(line) or caller
            self._set_state(CallState.INCOMING, display)
            self._log_line(f"着信: {display}", "incoming")
            self._log_line("F8 で応答 / F9 で切断", "hint")
            return

        if "call established" in low or "call: established" in low:
            self._set_state(CallState.CONNECTED)
            self._log_line("通話が確立されました。", "ok")
            return

        if "call: hold" in low or ": hold" in low:
            self._set_state(CallState.ON_HOLD)
            self._log_line("通話を保留しました。", "warn")
            return

        if "call: resume" in low or "resumed" in low:
            self._set_state(CallState.CONNECTED)
            self._log_line("保留を解除しました。", "ok")
            return

        if any(k in low for k in ("call closed", "call: terminated", "call: closed",
                                   "call: hungup", "call hangup", "call: bye",
                                   "call terminated", "session closed")):
            if "session closed" in low and self._state == CallState.ON_HOLD:
                self._log_line(line, "info")
            else:
                self._set_state(CallState.IDLE)
                self._log_line("通話が終了しました。", "info")
            return

        if "error" in low:
            self._log_line(line, "error")
        else:
            self._log_line(line, "info")

    @staticmethod
    def _extract_caller(line: str) -> str:
        m = re.search(r'from\s+<?sip:([^>;\s]+)', line, re.IGNORECASE)
        if m:
            return m.group(1).rstrip(':')
        m = re.search(r'sip:([^>;\s]+)', line, re.IGNORECASE)
        if m:
            return m.group(1).rstrip(':')
        return ""

    @staticmethod
    def _extract_display(line: str) -> str:
        m = re.search(r'"([^"]+)"\s+<sip:', line)
        if m:
            return m.group(1)
        m = re.search(r'([A-Za-z][^\s<]{1,30})\s+<sip:', line)
        if m:
            return m.group(1).strip()
        return ""

    # ── Button handlers ───────────────────────────────────────────────────────

    def _answer(self):
        if self._state != CallState.INCOMING:
            return
        self._baresip.answer()
        self._set_state(CallState.CONNECTED)
        self._log_line("応答しました。", "ok")

    def _hangup(self):
        if self._state == CallState.IDLE:
            return
        self._baresip.hangup()
        self._set_state(CallState.IDLE)
        self._log_line("切断しました。", "info")

    def _hold(self):
        self._baresip.hold()
        self._set_state(CallState.ON_HOLD)
        self._log_line("保留しました。", "warn")

    def _resume(self):
        self._baresip.resume()
        self._set_state(CallState.CONNECTED)
        self._log_line("保留を解除しました。", "ok")

    def _transfer(self):
        TransferDialog(self, self._config,
                       on_blind=self._blind_transfer,
                       on_attended=self._attended_transfer)

    def _blind_transfer(self, uri: str):
        self._baresip.transfer(uri)
        self._log_line(f"ブラインド転送: {uri}", "info")
        self._set_state(CallState.IDLE)

    def _attended_transfer(self, uri: str):
        self._baresip.hold()
        self._set_state(CallState.ON_HOLD)
        self._log_line(f"代理転送: {uri} へ発信します", "info")
        self._baresip.dial(uri)
        self._log_line("転送先と接続後、Transfer ボタンで転送を完了します。", "hint")

    def _dtmf_open(self):
        if self._dtmf_win and self._dtmf_win.isVisible():
            self._dtmf_win.raise_()
            return
        self._dtmf_win = NumpadDialog(self, self._config,
                                      dtmf_mode=True, on_dtmf=self._send_dtmf)
        self._dtmf_win.show()

    def _send_dtmf(self, digit: str):
        self._baresip.dtmf(digit)
        self._log_line(f"DTMF: {digit}", "dtmf")

    def _mute(self):
        if self._state not in (CallState.CONNECTED, CallState.ON_HOLD):
            return
        self._muted = not self._muted
        self._baresip.mute()
        if self._muted:
            self._log_line("マイクをミュートしました。", "warn")
        else:
            self._log_line("ミュートを解除しました。", "ok")
        self._refresh_buttons()

    def _park(self):
        ext = self._config.get("sip", "park_ext", "").strip()
        if not ext:
            self._log_line("パーク番号が未設定です。「設定」から park_ext を設定してください。", "warn")
            return
        uri = _make_uri(ext,
                        self._config.get("sip", "domain"),
                        self._config.get("sip", "port", "5060"))
        self._baresip.transfer(uri)
        self._log_line(f"パーク: {uri} へ転送しました。", "info")
        self._set_state(CallState.IDLE)

    def _dial_from_bar(self):
        n = self._dial_entry.text().strip()
        if not n:
            return
        self._dial(n)
        self._dial_entry.clear()

    def _open_numpad(self):
        if self._numpad and self._numpad.isVisible():
            self._numpad.raise_()
            return
        self._numpad = NumpadDialog(self, self._config,
                                    on_dial=self._dial, on_hangup=self._hangup)
        self._numpad.show()

    def _dial(self, number: str):
        if not self._config.is_sip_configured():
            self._log_line("SIP が未設定です。「設定」から設定してください。", "error")
            return
        uri = _make_uri(number,
                        self._config.get("sip", "domain"),
                        self._config.get("sip", "port", "5060"))
        self._baresip.dial(uri)
        self._set_state(CallState.DIALING, uri)
        self._log_line(f"発信: {uri}", "info")

    def _open_config(self):
        ConfigDialog(self, self._config, on_save=self._on_config_saved)

    def _on_config_saved(self):
        self._apply_bg(self.centralWidget())
        self._log_line("設定を保存しました。", "ok")
        if self._config.is_sip_configured():
            self._config.write_baresip_accounts()
            self._log_line("baresip を再起動しています...", "info")
            self._set_status("再起動中...", "#64748b")
            threading.Thread(target=self._baresip.restart, daemon=True).start()
        else:
            self._baresip.stop()
            self._set_status("未設定", "#f59e0b")

    def closeEvent(self, event):
        w, h = self.width(), self.height()
        if w >= 200 and h >= 200:
            self._config.set("window", "width_main",  w)
            self._config.set("window", "height_main", h)
        self._config.save()
        self._baresip.stop()
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SipsTeller")
    app.setStyleSheet(_APP_STYLE)
    window = App()
    window.show()
    sys.exit(app.exec())
