#!/usr/bin/env python3
# cineFlow -- degraining small-gauge film scans
#
# Copyright (C) 2026 Dr. R. Henkel
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Commercial licences are available for use cases the GPL does not cover.
# Enquiries: license@pixelcircus.com


import os
import sys
import time

try:
    import importlib
    importlib.import_module("torch")
except Exception:
    pass

try:
    import PyQt5
except ImportError:
    sys.exit(
        "\n[flowQt] PyQt5 is not installed.\n"
        "         pip install PyQt5\n"
    )

_PQ_PLUGINS = ""
for _sub in ("Qt5", "Qt"):
    _plug = os.path.join(os.path.dirname(PyQt5.__file__), _sub, "plugins")
    if os.path.isdir(_plug):
        _PQ_PLUGINS = _plug
        os.environ["QT_PLUGIN_PATH"] = _plug
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(_plug, "platforms")
        break

from PyQt5.QtCore import (QEvent, QObject, QPoint, QRect, QRectF,
                          Qt, QThread, QTimer, pyqtSignal, pyqtSlot)
from PyQt5.QtGui import (QColor, QCursor, QImage, QPainter,
                         QPalette, QPen)
from PyQt5.QtWidgets import (QApplication, QComboBox,
                             QDialog, QDoubleSpinBox, QFileDialog,
                             QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMainWindow,
                             QMessageBox,
                             QPushButton, QSizePolicy, QSlider, QSpinBox,
                             QStatusBar, QStyle, QStyleOptionSlider,
                             QTabWidget, QVBoxLayout, QWidget)

import flowcore as fcore

import cv2
import numpy as np

if _PQ_PLUGINS:
    os.environ["QT_PLUGIN_PATH"] = _PQ_PLUGINS
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(_PQ_PLUGINS, "platforms")
else:
    os.environ.pop("QT_PLUGIN_PATH", None)
    os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)

from cineflow_defaults import SCENE_PARAMS, VERSION
from cineio import scene_config_path, safe_name, imwrite_unicode

_SCRIPT = os.path.basename(__file__)

__version__ = VERSION

def _u8(x):
    return np.clip(x * 255.0, 0, 255).astype(np.uint8)

def _rgb(d):
    return cv2.cvtColor(_u8(d), cv2.COLOR_RGB2BGR)

RESULT_VIEW = "output"

VIRTUAL_VIEWS = {
    "flow_fw_rel":        "flow_fw",
    "warped_flow_bw_rel": "warped_flow_bw",
}

def data_key(view):
    return VIRTUAL_VIEWS.get(view, view)

MODE_DEPENDENT_VIEWS = ("trust_mean", "tex_weight", "sharp_gate")

def _unit(d):
    return fcore.norm(d, 0, 1)

DISPLAY = {
    RESULT_VIEW:         _rgb,
    "output_best":      _rgb,
    "output_dustA":   _rgb,
    "input":                 _rgb,
    "nbr_warped":      _rgb,
    "nbr_warped_trust": _rgb,
    "trust_geo":         _unit,
    "trust_photo":       _unit,
    "trust_mean":        _unit,
    "trust_mean_best":   _unit,
    "trust_mean_dustA":  _unit,
    "trust_mean_dustB":  _unit,
    "tex_weight":        _unit,
    "sharp_gate":  _unit,
    "flow_fw":           lambda d: fcore.flow_hsv(d),
    "warped_flow_bw":    lambda d: fcore.flow_hsv(d),
    "flow_fw_rel":       lambda d: fcore.flow_hsv_rel(d),
    "warped_flow_bw_rel": lambda d: fcore.flow_hsv_rel(d),
    "output_dustB":         _rgb,
}

FLOW_DT_SIGN = {
    "flow_fw":            +1,
    "flow_fw_rel":        +1,
    "warped_flow_bw":     -1,
    "warped_flow_bw_rel": -1,
}

def display_fn(key, cfg):
    fn = DISPLAY.get(key, _rgb)
    sign = FLOW_DT_SIGN.get(key)
    if sign is None:
        return fn
    dt = sign * int(cfg.get("_neighbor_offset", 1))
    if dt == 0:
        return fn
    hue = fcore._FLOW_HUE_OFFSET + (90.0 if dt < 0 else 0.0)
    scale = abs(dt)
    if key.endswith("_rel"):
        return lambda d: fcore.flow_hsv_rel(
            d, maxmag=fcore.FLOW_MAXMAG_REL * scale, hue_offset=hue)
    return lambda d: fcore.flow_hsv(
        d, maxmag=fcore.FLOW_MAXMAG * scale, hue_offset=hue)

VIEW_LABEL = {
    RESULT_VIEW:          "Output",
    "output_best":       "Output (best)",
    "output_dustA":    "Output (dustA)",
    "output_dustB":   "Output (dustB)",
    "input":             "Input",
    "nbr_warped":         "Neighbour (warped)",
    "nbr_warped_trust":   "Neighbour \u00d7 trust",
    "trust_geo":          "Trust geo",
    "trust_photo":        "Trust photo",
    "trust_mean":         "Trust",
    "trust_mean_best":    "Trust (best)",
    "trust_mean_dustA":   "Trust (dustA)",
    "trust_mean_dustB":   "Trust (dustB)",
    "tex_weight":         "Texture weight",
    "sharp_gate":   "Sharp gate",
    "flow_fw":            "Flow fw (HSV)",
    "warped_flow_bw":     "Warped flow bw (HSV)",
    "flow_fw_rel":        "Flow fw relative (HSVz)",
    "warped_flow_bw_rel": "Warped flow bw relative (HSVz)",
}

def view_label(key):
    return VIEW_LABEL.get(key, key)

VIEW_GROUPS = [
    ("Output",          [RESULT_VIEW]),
    ("Input",           ["input"]),
    ("Neighbour (diag)", ["nbr_warped", "nbr_warped_trust"]),
    ("Trust",           ["trust_mean", "trust_geo", "trust_photo"]),
    ("Sharpening",      ["tex_weight", "sharp_gate"]),
    ("Flow",            ["flow_fw", "flow_fw_rel",
                         "warped_flow_bw", "warped_flow_bw_rel"]),
]

VIEW_ORDER = [k for _grp, keys in VIEW_GROUPS for k in keys]

TIER_NAMES = {0: "Flow+Warp", 1: "Trust", 2: "Fusion", 3: "Sharpening"}

class Job:
    def __init__(self, tier, idx, files, cfg, backend, view, data=None,
                 serial=0):
        self.tier = tier
        self.idx = idx
        self.files = files
        self.cfg = dict(cfg)
        self.backend = backend
        self.view = view
        self.data = data
        self.serial = serial

_SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "flowQt_settings.json")

def _platform_key():
    if sys.platform.startswith("win"):
        return "win"
    try:
        with open("/proc/version") as f:
            if "microsoft" in f.read().lower():
                return "wsl"
    except Exception:
        pass
    return "linux"

_PLAT = _platform_key()
_DIR_KEY = f"input_dir_{_PLAT}"

def _sidebar_urls():
    from PyQt5.QtCore import QUrl
    urls = [QUrl.fromLocalFile(os.path.expanduser("~"))]
    if _PLAT in ("wsl", "linux"):
        if os.path.isdir("/mnt"):
            urls.insert(0, QUrl.fromLocalFile("/mnt"))
    else:
        import string
        for d in string.ascii_uppercase:
            p = f"{d}:\\"
            if os.path.isdir(p):
                urls.append(QUrl.fromLocalFile(p))
    return urls

DEFAULT_CYCLE = [
    "input",
    RESULT_VIEW,
    "nbr_warped_trust",
    "nbr_warped",
    "flow_fw_rel",
    "warped_flow_bw_rel",
    "trust_geo",
    "trust_photo",
    "sharp_gate",
]

_bad_offset = sorted(k for k in fcore._OFFSET_DEPENDENT_KEYS if k not in DISPLAY)
_bad_cycle = sorted(k for k in DEFAULT_CYCLE
                    if k != RESULT_VIEW and k not in DISPLAY)
_bad_order = sorted(k for k in VIEW_ORDER if k not in DISPLAY)
_bad_label = sorted(k for k in DISPLAY if k not in VIEW_LABEL)
if _bad_offset or _bad_cycle or _bad_order or _bad_label:
    raise KeyError(
        "view keys and DISPLAY do not agree -- "
        f"offset-abhaengig: {_bad_offset}, Zyklus: {_bad_cycle}, "
        f"Reihenfolge: {_bad_order}, ohne Beschriftung: {_bad_label}")

def _load_settings():
    s = {_DIR_KEY: "", "start_frame": 0, "cycle": list(DEFAULT_CYCLE),
         "slots": {}}
    if os.path.isfile(_SETTINGS):
        try:
            import json
            with open(_SETTINGS) as f:
                s.update(json.load(f))
        except Exception as e:
            fcore.log("settings", f"{_SETTINGS} not readable ({e!r}) -- using defaults")
    _RENAMED = {
        "center":             "input",
        "result":             "output",
        "result_best":        "output_best",
        "result_dustA":       "output_dustA",
        "result_dustB":       "output_dustB",
        "trust_center_dustA": "trust_input_dustA",
        "trust_center_dustB": "trust_input_dustB",
    }
    _raw = list(s.get("cycle", []))
    _moved = sorted({v for v in _raw if v in _RENAMED})
    if _moved:
        s["cycle"] = [_RENAMED.get(v, v) for v in _raw]
        fcore.log("settings", "cycle keys migrated to the Input/Output names: "
                              + ", ".join(f"{v} -> {_RENAMED[v]}" for v in _moved))

    cyc = [v for v in s.get("cycle", []) if v in DISPLAY]
    dropped = [v for v in s.get("cycle", []) if v not in DISPLAY]
    if dropped:
        fcore.log("settings", f"unknown view keys dropped from cycle: "
                              f"{', '.join(dropped)}")
    cyc = [k for i, k in enumerate(cyc) if i == 0 or k != cyc[i - 1]]
    s["cycle"] = cyc or list(DEFAULT_CYCLE)
    if not isinstance(s.get("slots"), dict):
        s["slots"] = {}
    return s

def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    import json
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)

def _save_settings(s):
    try:
        _atomic_write_json(_SETTINGS, s)
    except Exception as e:
        fcore.log("settings", f"could not write: {e!r}")

class SlotButton(QPushButton):
    leftClicked = pyqtSignal()
    rightClicked = pyqtSignal()
    shiftRightClicked = pyqtSignal()
    ctrlRightClicked = pyqtSignal()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            mods = ev.modifiers()
            if mods & Qt.ShiftModifier:
                self.shiftRightClicked.emit()
            elif mods & Qt.ControlModifier:
                self.ctrlRightClicked.emit()
            else:
                self.rightClicked.emit()
        elif ev.button() == Qt.LeftButton:
            self.leftClicked.emit()
        else:
            super().mousePressEvent(ev)

class CycleEditor(QDialog):
    changed = pyqtSignal(list)

    def __init__(self, cycle, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit views")
        self.resize(600, 440)
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(
            "<span style='color:#9aa0a6'>The order is the control: "
            "Up/Down steps through this sequence.<br>"
            "Views may appear more than once &mdash; e.g. 'N' between "
            "several pairs, to keep flipping back to the reference.</span>"))
        inner = QWidget()
        outer.addWidget(inner, 1)
        lay = QHBoxLayout(inner)

        lv = QVBoxLayout()
        lv.addWidget(QLabel("sequence (up/down to reorder):"))
        self.lst = QListWidget()
        for i, v in enumerate(cycle):
            self.lst.addItem(self._mk_item(v, num=i + 1))
        lv.addWidget(self.lst, 1)
        bl = QHBoxLayout()
        for txt, fn in (("up", self._up), ("down", self._down),
                        ("remove", self._rm)):
            b = QPushButton(txt); b.clicked.connect(fn); bl.addWidget(b)
        lv.addLayout(bl)
        lay.addLayout(lv, 1)

        rv = QVBoxLayout()
        rv.addWidget(QLabel("available (double-click to append):"))
        self.avail = QListWidget()
        for grp, keys in VIEW_GROUPS:
            self.avail.addItem(self._mk_header(grp))
            for v in keys:
                self.avail.addItem(self._mk_item(v))
        self.avail.itemDoubleClicked.connect(self._add)
        rv.addWidget(self.avail, 1)
        b = QPushButton("add \u2192")
        b.clicked.connect(lambda: self._add(self.avail.currentItem()))
        rv.addWidget(b)
        lay.addLayout(rv, 1)

        close = QPushButton("done")
        close.clicked.connect(self.accept)
        outer.addWidget(close)

    def _emit(self):
        self._renumber()
        self.changed.emit([(self.lst.item(i).data(Qt.UserRole)
                            or self.lst.item(i).text())
                           for i in range(self.lst.count())])

    @staticmethod
    def _mk_header(text):
        it = QListWidgetItem(text.upper())
        it.setFlags(Qt.NoItemFlags)
        f = it.font(); f.setBold(True); f.setPointSize(max(7, f.pointSize() - 1))
        it.setFont(f)
        it.setForeground(QColor("#7d838b"))
        return it

    @staticmethod
    def _mk_item(key, num=None):
        label = view_label(key)
        if num is not None:
            label = f"{num}. {label}" if num <= 9 else f"    {label}"
        it = QListWidgetItem(label)
        it.setData(Qt.UserRole, key)
        it.setToolTip(key)
        return it

    def _renumber(self):
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            key = it.data(Qt.UserRole)
            label = view_label(key)
            it.setText(f"{i+1}. {label}" if i < 9 else f"    {label}")

    def _add(self, item):
        if item:
            key = item.data(Qt.UserRole)
            if not key:
                return
            self.lst.addItem(self._mk_item(key))
            self._emit()

    def _rm(self):
        r = self.lst.currentRow()
        if r >= 0 and self.lst.count() > 1:
            self.lst.takeItem(r)
            self._emit()

    def _move(self, d):
        r = self.lst.currentRow()
        n = r + d
        if 0 <= r < self.lst.count() and 0 <= n < self.lst.count():
            it = self.lst.takeItem(r)
            self.lst.insertItem(n, it)
            self.lst.setCurrentRow(n)
            self._emit()

    def _up(self):   self._move(-1)
    def _down(self): self._move(+1)

class Status(QWidget):
    def __init__(self):
        super().__init__()
        self._t0 = None
        self._what = ""
        self._phase = 0.0
        self.last_what = None
        self.last_ms = None
        self.last_reason = ""
        self.backend = ""
        self.backend_warn = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._relayout()

    def _relayout(self):
        fm = self.fontMetrics()
        self._row = fm.height()
        self._gap = max(2, fm.height() // 5)
        self._pad = max(4, fm.height() // 3)
        self._lab_w = fm.horizontalAdvance("Flow") + fm.height()
        self._bar_h = max(3, fm.height() // 5)
        rows = 1
        need = (self._pad
                + 2 * (self._row + self._gap)
                + self._bar_h + self._gap
                + self._row
                + rows * (self._row + self._gap)
                + self._pad)
        self.setMinimumHeight(need)

    def changeEvent(self, ev):
        if ev.type() == QEvent.FontChange:
            self._relayout()
        super().changeEvent(ev)

    def start(self, what):
        self._what = what
        self._t0 = time.time()
        self._timer.start(60)
        self.update()

    def finish(self, what, msec, reason):
        self._timer.stop()
        self._t0 = None
        self.last_what = what
        self.last_ms = msec
        self.last_reason = reason
        self.update()

    def stop(self):
        self._timer.stop()
        self._t0 = None
        self.update()

    def set_state(self, backend=None, backend_warn=False):
        if backend is not None: self.backend = backend
        self.backend_warn = backend_warn
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.06) % 1.0
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        row, gap, pad = self._row, self._gap, self._pad
        y = pad

        if self._t0 is not None:
            el = time.time() - self._t0
            p.setPen(QPen(QColor(205, 210, 216)))
            p.drawText(QRect(pad, y, w - 2 * pad, row), Qt.AlignLeft,
                       f"computing {self._what} \u2026")
            p.setPen(QPen(QColor(140, 145, 152)))
            p.drawText(QRect(pad, y, w - 2 * pad, row), Qt.AlignRight,
                       f"{el:.1f} s")
            y += row + gap
            bw = int(w * 0.28)
            x = int((w + bw) * self._phase) - bw
            p.fillRect(pad, y, w - 2 * pad, self._bar_h, QColor(44, 45, 49))
            p.fillRect(max(pad, x), y,
                       min(bw, w - pad - max(pad, x)), self._bar_h,
                       QColor(78, 132, 190))
            y += self._bar_h + gap
        elif self.last_what is not None:
            p.setPen(QPen(QColor(205, 210, 216)))
            p.drawText(QRect(pad, y, w - 2 * pad, row), Qt.AlignLeft,
                       self.last_what)
            ms = self.last_ms
            txt = f"{ms/1000:.2f} s" if ms >= 1000 else f"{ms:.0f} ms"
            p.setPen(QPen(QColor(216, 154, 60) if ms >= 1000
                          else QColor(150, 200, 150)))
            p.drawText(QRect(pad, y, w - 2 * pad, row), Qt.AlignRight, txt)
            y += row + gap
            if self.last_reason:
                p.setPen(QPen(QColor(125, 131, 139)))
                p.drawText(QRect(pad, y, w - 2 * pad, row), Qt.AlignLeft,
                           f"\u2190 {self.last_reason}")
                y += row + gap
        else:
            p.setPen(QPen(QColor(110, 115, 122)))
            p.drawText(QRect(pad, y, w - 2 * pad, row), Qt.AlignLeft, "ready")
            y += row + gap

        y += gap
        p.fillRect(pad, y, w - 2 * pad, 1, QColor(58, 58, 62))
        y += gap + gap

        rows = []
        if self.backend:
            rows.append(("Flow", self.backend, self.backend_warn))
        lw = self._lab_w
        for label, val, warn in rows:
            p.setPen(QPen(QColor(125, 131, 139)))
            p.drawText(QRect(pad, y, lw, row), Qt.AlignLeft, label)
            p.setPen(QPen(QColor(255, 122, 69) if warn else QColor(190, 196, 203)))
            p.drawText(QRect(pad + lw, y, w - pad - lw - pad, row),
                       Qt.AlignLeft, val)
            y += row + gap

class Worker(QObject):
    done = pyqtSignal(object, object, int)
    started_job = pyqtSignal(str, int)
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._latest = 0

    def set_latest(self, serial):
        self._latest = serial

    @pyqtSlot(object)
    def run(self, job):
        if job.serial < self._latest:
            return
        try:
            t0 = time.time()
            _name = TIER_NAMES[job.tier]
            if job.tier == fcore._TIER_FLOW and job.view == "input":
                _name = "Load image"
            self.started_job.emit(_name, job.tier)

            if job.tier == fcore._TIER_FLOW:
                data = fcore.compute_flow_trust(job.idx, job.files, job.cfg,
                                                job.backend, active_view=job.view)
            elif job.tier == fcore._TIER_TRUST:
                data = fcore.compute_trust(job.data, job.cfg)
            elif job.tier == fcore._TIER_FUSION:
                data = fcore.compute_fusion(job.data, job.cfg)
            else:
                data = fcore.compute_e(job.data, job.cfg)

            if job.serial < self._latest:
                return
            job.msec = (time.time() - t0) * 1000.0
            self.done.emit(data, job, job.serial)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.failed.emit(f"{type(e).__name__}: {e}")

_FOREIGN_VIDEO = (".m4v", ".mxf", ".mts", ".webm", ".wmv", ".mpg", ".mpeg")

class Canvas(QLabel):
    panned = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(480, 360)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#0a0a0b;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._img = None
        self._ref = None
        self.view_key = ""
        self.zoom_i = 0
        self._last_zoom_i = 2
        self.split_mode = 0
        self.split_x = 0.5
        self._pan = QPoint(0, 0)
        self._drag = None
        self._drag_split = False
        self._drop_hint = False
        self._message = None

    dropped = pyqtSignal(str)
    droppedConfig = pyqtSignal(str)
    toggleZoom = pyqtSignal()
    zoomStep = pyqtSignal(int)
    zoomInfo = pyqtSignal()

    ZOOM_LEVELS = [0.0, 1.0, 2.0, 4.0, 8.0]
    ZOOM_NAMES  = ["Fit", "1x", "2x", "4x", "8x"]

    @staticmethod
    def _config_from_mime(mime):
        if not mime.hasUrls():
            return None
        for u in mime.urls():
            p = u.toLocalFile()
            if p and os.path.isfile(p) and p.lower().endswith(".json"):
                return p
        return None

    @staticmethod
    def _dir_from_mime(mime):
        if not mime.hasUrls():
            return None
        for u in mime.urls():
            p = u.toLocalFile()
            if not p:
                continue
            if os.path.isdir(p):
                return p
            if fcore.is_video(p):
                return p
            if os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                if ext in _FOREIGN_VIDEO:
                    return None
                return os.path.dirname(p)
        return None

    @staticmethod
    def classify_drop(mime):
        c = Canvas._config_from_mime(mime)
        if c:
            return "config", c
        p = Canvas._dir_from_mime(mime)
        if p:
            return "scene", p
        return None, None

    def dragEnterEvent(self, ev):
        if self.classify_drop(ev.mimeData())[0]:
            ev.setDropAction(Qt.CopyAction)
            ev.accept()
            self.set_drop_hint(True)
        else:
            ev.ignore()

    def dragMoveEvent(self, ev):
        if self.classify_drop(ev.mimeData())[0]:
            ev.setDropAction(Qt.CopyAction)
            ev.accept()
        else:
            ev.ignore()

    def dragLeaveEvent(self, ev):
        self.set_drop_hint(False)

    def dropEvent(self, ev):
        self.set_drop_hint(False)
        kind, p = self.classify_drop(ev.mimeData())
        if kind == "config":
            ev.acceptProposedAction()
            self.droppedConfig.emit(p)
        elif kind == "scene":
            ev.acceptProposedAction()
            self.dropped.emit(p)
        else:
            ev.ignore()

    def set_drop_hint(self, on):
        self._drop_hint = bool(on)
        self.update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        box = getattr(self, "_overlay_box", None)
        if box is not None and not box.isHidden():
            box.move(12, max(12, self.height() - box.height() - 12))
        if self.is_fit():
            self.zoomInfo.emit()

    def set_overlay(self, box):
        self._overlay_box = box

    def set_images(self, img, ref=None, view_key="", clear_ref=False):
        self._img = img
        self._message = None
        if ref is not None:
            self._ref = ref
        elif clear_ref:
            self._ref = None
        if view_key:
            self.view_key = view_key
        if self.is_fit():
            self.zoomInfo.emit()
        self.update()

    def show_message(self, text):
        self._img = None
        self._message = text
        self.update()

    def is_fit(self):
        return self.ZOOM_LEVELS[self.zoom_i] == 0.0

    def dpr(self):
        try:
            return float(self.devicePixelRatioF())
        except Exception:
            return 1.0

    def scale(self):
        if self._img is None:
            return 1.0
        h, w = self._img.shape[:2]
        z = self.ZOOM_LEVELS[self.zoom_i]
        if z == 0.0:
            if w <= 0 or h <= 0:
                return 1.0
            return min(self.width() / w, self.height() / h)
        return z / self.dpr()

    def effective_zoom(self):
        return self.scale() * self.dpr()

    def _view_origin(self):
        if self._img is None or self.is_fit():
            return 0.0, 0.0
        h, w = self._img.shape[:2]
        s = self.scale()
        vis_w, vis_h = self.width() / s, self.height() / s
        x = min(max(self._pan.x(), 0.0), max(0.0, w - vis_w))
        y = min(max(self._pan.y(), 0.0), max(0.0, h - vis_h))
        return x, y

    def _fit_offset(self):
        if self._img is None:
            return 0.0, 0.0
        h, w = self._img.shape[:2]
        s = self.scale()
        return (max(0.0, self.width() - w * s) / 2.0,
                max(0.0, self.height() - h * s) / 2.0)

    def img_from_screen(self, x, y):
        if self._img is None:
            return 0.0, 0.0
        s = self.scale()
        ox, oy = self._view_origin()
        fx, fy = self._fit_offset()
        return ox + (x - fx) / s, oy + (y - fy) / s

    def screen_from_img(self, x, y):
        if self._img is None:
            return 0.0, 0.0
        s = self.scale()
        ox, oy = self._view_origin()
        fx, fy = self._fit_offset()
        return (x - ox) * s + fx, (y - oy) * s + fy

    def zoom_to(self, i, anchor=None):
        i = max(0, min(len(self.ZOOM_LEVELS) - 1, int(i)))
        if i == self.zoom_i:
            return
        if anchor is not None and self._img is not None:
            ax, ay = self.img_from_screen(anchor.x(), anchor.y())
            self.zoom_i = i
            if not self.is_fit():
                s = self.scale()
                self._pan = QPoint(int(round(ax - anchor.x() / s)),
                                   int(round(ay - anchor.y() / s)))
        else:
            self.zoom_i = i
        if not self.is_fit():
            self._last_zoom_i = self.zoom_i
        self.update()

    def _compose(self):
        if self._img is None:
            return None
        img = self._img
        if self.split_mode and self._ref is not None:
            ref = self._ref
            if ref.shape[:2] != img.shape[:2]:
                ref = cv2.resize(ref, (img.shape[1], img.shape[0]))
            out = img.copy()
            xs = int(np.clip(self.split_x, 0.02, 0.98) * img.shape[1])
            if self.split_mode == 1:
                out[:, :xs] = ref[:, :xs]
            else:
                out[:, xs:] = ref[:, xs:]
            cv2.line(out, (xs, 0), (xs, img.shape[0]), (0, 220, 255), 2)
            return out
        return img

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        if self._drop_hint:
            pen = QPen(QColor(78, 132, 190), 3, Qt.DashLine)
            p.setPen(pen)
            p.drawRect(self.rect().adjusted(6, 6, -7, -7))
        img = self._compose()
        if img is None:
            if self._message:
                p.setPen(QPen(QColor(216, 154, 60)))
                f = p.font(); f.setPointSize(12); p.setFont(f)
                p.drawText(self.rect(), Qt.AlignCenter, self._message)
            else:
                p.setPen(QPen(QColor(120, 126, 134)))
                f = p.font(); f.setPointSize(13); p.setFont(f)
                p.drawText(self.rect().adjusted(0, -18, 0, -18), Qt.AlignCenter,
                           "Drag a scene folder into this area")
                p.setPen(QPen(QColor(84, 89, 96)))
                f.setPointSize(10); p.setFont(f)
                p.drawText(self.rect().adjusted(0, 18, 0, 18), Qt.AlignCenter,
                           "... or use the Load buttons above")
            return

        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qim = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)

        s = self.scale()
        ox, oy = self._view_origin()
        if not self.is_fit():
            self._pan = QPoint(int(round(ox)), int(round(oy)))
        sw = min(w - ox, self.width() / s)
        sh = min(h - oy, self.height() / s)
        fx, fy = self._fit_offset()
        srect = QRectF(ox, oy, sw, sh)
        drect = QRectF(fx, fy, sw * s, sh * s)

        hard = (not self.is_fit()) and self.ZOOM_LEVELS[self.zoom_i] >= 2.0
        p.setRenderHint(QPainter.SmoothPixmapTransform, not hard)
        p.drawImage(drect, qim, srect)

    SPLIT_GRAB = 12

    def _split_screen_x(self):
        if self._img is None:
            return None
        h, w = self._img.shape[:2]
        sx, _ = self.screen_from_img(self.split_x * w, 0.0)
        return int(round(sx))

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        if self.split_mode:
            sx = self._split_screen_x()
            if sx is not None and abs(ev.x() - sx) <= self.SPLIT_GRAB:
                self._drag_split = True
                self._set_split_from_x(ev.x())
                return
        if not self.is_fit():
            self._drag = ev.pos()

    def mouseMoveEvent(self, ev):
        if self._drag_split:
            self._set_split_from_x(ev.x())
        elif self._drag is not None:
            d = ev.pos() - self._drag
            s = self.scale() or 1.0
            self._pan -= QPoint(int(round(d.x() / s)), int(round(d.y() / s)))
            self._drag = ev.pos()
            self.update()
        elif self.split_mode:
            sx = self._split_screen_x()
            near = sx is not None and abs(ev.x() - sx) <= self.SPLIT_GRAB
            self.setCursor(Qt.SplitHCursor if near else
                           (Qt.OpenHandCursor if not self.is_fit()
                            else Qt.ArrowCursor))

    def mouseReleaseEvent(self, ev):
        self._drag = None
        self._drag_split = False

    def mouseDoubleClickEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            super().mouseDoubleClickEvent(ev)
            return
        self._drag = None
        self._drag_split = False
        self.toggleZoom.emit()

    def wheelEvent(self, ev):
        dy = ev.angleDelta().y()
        if dy == 0:
            return
        self.zoomStep.emit(1 if dy > 0 else -1)
        ev.accept()

    def _set_split_from_x(self, x):
        if self._img is None:
            return
        w = self._img.shape[1]
        xi, _ = self.img_from_screen(x, 0.0)
        self.split_x = float(np.clip(xi / max(w, 1), 0.02, 0.98))
        self.update()

class TextureHistogram(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(90)
        self._hist = None
        self._pcts = {}
        self._texref = None

    def set_texture(self, tex):
        if tex is None:
            self._hist = None
            self._pcts = {}
        else:
            t = np.asarray(tex, dtype=np.float32).ravel()
            t = t[np.isfinite(t)]
            if t.size == 0:
                self._hist = None
                self._pcts = {}
            else:
                hi = float(np.percentile(t, 99.5)) or 1e-6
                counts, edges = np.histogram(t, bins=64, range=(0.0, hi))
                self._hist = (counts.astype(np.float64), edges)
                self._pcts = {p: float(np.percentile(t, p))
                              for p in (50, 90, 99)}
        self.update()

    def set_texref(self, v):
        self._texref = float(v) if v is not None else None
        self.update()

    def percentile(self, p):
        return self._pcts.get(p)

    def paintEvent(self, ev):
        from PyQt5.QtGui import QPainter, QColor, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#232327"))
        if self._hist is None:
            p.setPen(QColor("#7d838b"))
            p.drawText(6, h // 2, "no texture data (compute first)")
            return
        counts, edges = self._hist
        lo, hi = float(edges[0]), float(edges[-1])
        span = max(hi - lo, 1e-9)
        mx = float(counts.max()) or 1.0
        n = len(counts)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4a6d8c"))
        for i, c in enumerate(counts):
            bh = int(round((c / mx) * (h - 16)))
            x0 = int(round(i * w / n))
            x1 = int(round((i + 1) * w / n))
            p.drawRect(x0, h - bh, max(1, x1 - x0 - 1), bh)

        def xof(val):
            return int(round((float(val) - lo) / span * w))

        for pc, col in ((50, "#7d838b"), (90, "#c8a45c"), (99, "#8c6a4a")):
            v = self._pcts.get(pc)
            if v is None or not (lo <= v <= hi):
                continue
            x = xof(v)
            p.setPen(QPen(QColor(col), 1, Qt.DashLine))
            p.drawLine(x, 0, x, h)
            p.setPen(QColor(col))
            p.drawText(min(x + 3, w - 26), 11, f"p{pc}")

        if self._texref is not None:
            x = xof(self._texref)
            if 0 <= x <= w:
                p.setPen(QPen(QColor("#e0554a"), 2))
                p.drawLine(x, 0, x, h)
                p.setPen(QColor("#e0554a"))
                lbl = f"full {self._texref:.3f}"
                p.drawText(max(2, min(x + 4, w - 78)), h - 3, lbl)
            else:
                p.setPen(QColor("#e0554a"))
                side = "-->" if self._texref > hi else "<--"
                p.drawText(w - 96 if self._texref > hi else 4, h - 3,
                           f"full {side} {self._texref:.3f}")

class CurvePlot(QWidget):
    def __init__(self, xlabel="", ylabel=""):
        super().__init__()
        self.setMinimumHeight(110)
        self._fn = None
        self._xr = (0.0, 1.0)
        self._marks = []
        self._xlabel = xlabel
        self._ylabel = ylabel
        self._title = ""

    def set_title(self, text):
        if text != self._title:
            self._title = text
            self.update()

    def set_xlabel(self, text):
        self._xlabel = text
        self.update()

    def set_curve(self, fn, xmin, xmax, marks=None):
        self._fn = fn
        self._xr = (float(xmin), float(xmax))
        self._marks = list(marks or [])
        self.update()

    def paintEvent(self, ev):
        from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#232327"))
        ml, mr, mt, mb = 30, 8, 8, 18
        if self._title:
            p.setPen(QColor("#c8ccd2"))
            p.drawText(ml, 14, self._title)
            mt = 22
        pw, ph = max(1, w - ml - mr), max(1, h - mt - mb)
        p.setPen(QPen(QColor("#3a3a3e"), 1))
        for fy, lab in ((0.0, "0"), (0.5, ""), (1.0, "1")):
            y = mt + int(round((1.0 - fy) * ph))
            p.drawLine(ml, y, ml + pw, y)
            if lab:
                p.setPen(QColor("#7d838b"))
                p.drawText(6, y + 4, lab)
                p.setPen(QPen(QColor("#3a3a3e"), 1))
        if self._fn is None:
            return
        x0, x1 = self._xr
        span = max(x1 - x0, 1e-12)
        path = QPainterPath()
        for i in range(pw + 1):
            xv = x0 + span * (i / pw)
            try:
                yv = float(self._fn(xv))
            except Exception:
                return
            yv = 0.0 if yv != yv else max(0.0, min(1.0, yv))
            px = ml + i
            py = mt + (1.0 - yv) * ph
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)
        p.setPen(QPen(QColor("#6fa8dc"), 2))
        p.drawPath(path)
        for mx, col, txt in self._marks:
            if not (x0 <= mx <= x1):
                continue
            px = ml + int(round((mx - x0) / span * pw))
            p.setPen(QPen(QColor(col), 1, Qt.DashLine))
            p.drawLine(px, mt, px, mt + ph)
            if txt:
                p.setPen(QColor(col))
                p.drawText(min(px + 3, w - 40), mt + 11, txt)
        p.setPen(QColor("#7d838b"))
        if self._xlabel:
            p.drawText(ml, h - 4, self._xlabel)
        p.drawText(ml + pw - 34, h - 4, f"{x1:g}")

def _compact(lay, spacing=2, margins=(8, 6, 8, 4)):
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    return lay

def _indent_row(lay, widget, px=18):
    from PyQt5.QtWidgets import QHBoxLayout
    row = QHBoxLayout()
    row.setContentsMargins(px, 0, 0, 0)
    row.addWidget(widget)
    lay.addLayout(row)

class CenterSlider(QSlider):
    MARK = QColor("#5fd3d8")

    def paintEvent(self, ev):
        super().paintEvent(ev)
        lo, hi = self.minimum(), self.maximum()
        if lo >= 0 or hi <= 0:
            return
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        handle = self.style().subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        span = groove.width() - handle.width()
        x = QStyle.sliderPositionFromValue(lo, hi, 0, span,
                                           opt.upsideDown)
        x += groove.left() + handle.width() // 2
        pn = QPainter(self)
        pn.setPen(QPen(self.MARK, 1))
        pn.drawLine(x, groove.top(), x, groove.bottom())
        pn.end()

class IntChoice(QWidget):
    changed = pyqtSignal(str, object)
    released = pyqtSignal(str)

    def __init__(self, key, label, lo, hi, value, expensive=False,
                 default=None, tip="", prefix="", postfix=""):
        super().__init__()
        self.key = key
        self.integer = True
        self.lo, self.hi, self.step = int(lo), int(hi), 1
        self.default = default
        self.log = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.lbl = QLabel(label)
        self.lbl.setMinimumWidth(96)
        if default is not None:
            self.setToolTip(f"Double-click = back to default ({default})")
        if expensive:
            self.lbl.setStyleSheet("color:#b9935a;")
            self.lbl.setToolTip("Changes the flow -> recomputation takes seconds")
        if tip:
            self.lbl.setToolTip(tip)
        lay.addWidget(self.lbl)

        if prefix:
            lp = QLabel(prefix)
            lay.addWidget(lp)
            lay.setSpacing(3)

        self.box = QComboBox()
        self.box.setFocusPolicy(Qt.NoFocus)
        self.box.addItems([str(v) for v in range(self.lo, self.hi + 1)])
        self.box.setMinimumWidth(76)
        self.box.setMaximumWidth(110)
        self.box.currentIndexChanged.connect(self._pick_index)
        lay.addWidget(self.box)

        if postfix:
            lay.addSpacing(4)
            lay.addWidget(QLabel(postfix))
        lay.addStretch(1)
        self.set_value(value)

    def _pick_index(self, i):
        v = self.lo + int(i)
        self._value = v
        self.changed.emit(self.key, v)
        self.released.emit(self.key)

    def mouseDoubleClickEvent(self, ev):
        if self.default is None or self.box.geometry().contains(ev.pos()):
            super().mouseDoubleClickEvent(ev)
            return
        self.set_value(int(self.default))
        self.changed.emit(self.key, self.value())
        self.released.emit(self.key)
        ev.accept()

    def set_value(self, v):
        self._value = int(min(max(int(v), self.lo), self.hi))
        self.box.blockSignals(True)
        self.box.setCurrentIndex(self._value - self.lo)
        self.box.blockSignals(False)

    def value(self):
        return self._value

class Param(QWidget):
    changed = pyqtSignal(str, object)
    released = pyqtSignal(str)

    def __init__(self, key, label, lo, hi, step, value, decimals=2,
                 expensive=False, integer=False, log=False, default=None):
        super().__init__()
        self.key = key
        self.integer = integer
        self.lo, self.hi, self.step = lo, hi, step
        self.default = default

        self.log = bool(log) and not integer and lo > 0

        if self.log:
            self._ticks = 1000
            self._mult = None
        else:
            self._mult = 1 if integer else int(round(1.0 / step))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.lbl = QLabel(label)
        self.lbl.setMinimumWidth(96)
        if default is not None:
            self.setToolTip(f"Double-click = back to default ({default})")
        if expensive:
            self.lbl.setStyleSheet("color:#b9935a;")
            self.lbl.setToolTip("Changes the flow -> recomputation takes seconds")
        lay.addWidget(self.lbl)

        self.sld = QSlider(Qt.Horizontal)
        if self.log:
            self.sld.setMinimum(0)
            self.sld.setMaximum(self._ticks)
        else:
            self.sld.setMinimum(int(round(lo * self._mult)))
            self.sld.setMaximum(int(round(hi * self._mult)))
        self.sld.setSingleStep(1)
        self.sld.setValue(self._to_tick(value))
        self.sld.installEventFilter(self)
        lay.addWidget(self.sld, 1)

        if integer:
            self.box = QSpinBox()
            self.box.setRange(int(lo), int(hi))
            self.box.setValue(int(value))
        else:
            self.box = QDoubleSpinBox()
            self.box.setDecimals(decimals)
            self.box.setRange(lo, hi)
            self.box.setSingleStep(step)
            self.box.setValue(value)
        self.box.setKeyboardTracking(False)
        self.box.setMinimumWidth(76)
        lay.addWidget(self.box)

        self.sld.valueChanged.connect(self._from_slider)
        self.sld.sliderReleased.connect(lambda: self.released.emit(self.key))
        self.box.valueChanged.connect(self._from_box)

    def _to_tick(self, v):
        v = min(max(float(v), self.lo), self.hi)
        if self.log:
            import math
            f = (math.log(v) - math.log(self.lo)) / \
                (math.log(self.hi) - math.log(self.lo))
            return int(round(f * self._ticks))
        return int(round(v * self._mult))

    def _from_tick(self, t):
        if self.log:
            import math
            f = t / self._ticks
            v = math.exp(math.log(self.lo) +
                         f * (math.log(self.hi) - math.log(self.lo)))
            v = round(v / self.step) * self.step
            return float(min(max(v, self.lo), self.hi))
        v = t / self._mult
        return int(v) if self.integer else float(v)

    def _val(self):
        return self._from_tick(self.sld.value())

    def _from_slider(self, _):
        v = self._val()
        self.box.blockSignals(True)
        self.box.setValue(v)
        self.box.blockSignals(False)
        self.changed.emit(self.key, v)
        if not self.sld.isSliderDown():
            self.released.emit(self.key)

    def _from_box(self, v):
        self.sld.blockSignals(True)
        self.sld.setValue(self._to_tick(v))
        self.sld.blockSignals(False)
        self.changed.emit(self.key, int(v) if self.integer else float(v))
        self.released.emit(self.key)

    def mouseDoubleClickEvent(self, ev):
        if self.box.geometry().contains(ev.pos()):
            super().mouseDoubleClickEvent(ev)
            return
        if not self._reset_to_default():
            super().mouseDoubleClickEvent(ev)
        else:
            ev.accept()

    def eventFilter(self, obj, ev):
        if obj is self.sld and ev.type() == QEvent.MouseButtonDblClick:
            if self._reset_to_default():
                return True
        return super().eventFilter(obj, ev)

    def _reset_to_default(self):
        if self.default is None:
            return False
        v = int(self.default) if self.integer else float(self.default)
        self.set_value(v)
        self.changed.emit(self.key, v)
        self.released.emit(self.key)
        return True

    def set_lo(self, lo):
        lo = float(lo)
        if abs(lo - float(self.lo)) < 1e-9:
            return
        if self.log:
            keep = float(self.box.value())
            self.lo = lo
            self.sld.blockSignals(True)
            self.sld.setValue(self._to_tick(keep))
            self.sld.blockSignals(False)
        else:
            self.lo = lo
            self.sld.setMinimum(int(round(lo * self._mult)))
        self.box.setMinimum(int(lo) if self.integer else lo)

    def set_value(self, v):
        self.sld.blockSignals(True); self.box.blockSignals(True)
        self.sld.setValue(self._to_tick(v))
        self.box.setValue(v)
        self.sld.blockSignals(False); self.box.blockSignals(False)

    def value(self):
        return self._val()

class _TiffSeqWriter:
    def __init__(self, dir_path, prefix):
        self._dir = dir_path
        self._prefix = prefix
        self._n = 0
        self._ok = True
        self._tiff = None
        try:
            import tifffile
            self._tiff = tifffile
        except Exception:
            self._tiff = None
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError:
            self._ok = False

    def isOpened(self):
        return self._ok

    def write(self, frame_bgr):
        self._n += 1
        path = os.path.join(self._dir, f"{self._prefix}_{self._n:06d}.tiff")
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        if self._tiff is not None:
            with open(path, "wb") as fh:
                self._tiff.imwrite(fh, rgb, compression=None, photometric="rgb")
        else:
            imwrite_unicode(path, frame_bgr,
                            [cv2.IMWRITE_TIFF_COMPRESSION, 1])

    def release(self):
        pass

class AutoplayRecorder:

    def __init__(self, m):
        self.m = m
        self.direction = 0
        self.step = 1
        self.writer = None
        self.path = None
        self.count = 0
        self.size = None
        self.fmt = "mp4"
        self.written_idx = None
        self.b_play_fwd = None
        self.b_play_bwd = None
        self.b_record = None
        self.cb_rec_mode = None

    def build_box(self):
        gAP = QGroupBox("Autoplay | Record")
        lAP = QHBoxLayout(gAP)
        self.b_play_bwd = QPushButton("\u25c0")
        self.b_play_bwd.setCheckable(True)
        self.b_play_bwd.setToolTip("Autoplay backwards (key y). Press again to stop.")
        self.b_play_bwd.clicked.connect(lambda: self.toggle(-1))
        self.b_play_fwd = QPushButton("\u25b6")
        self.b_play_fwd.setCheckable(True)
        self.b_play_fwd.setToolTip("Autoplay forwards (key x or space).\n"
                                   "Press again to stop.")
        self.b_play_fwd.clicked.connect(lambda: self.toggle(+1))
        lAP.addWidget(self.b_play_bwd)
        lAP.addWidget(self.b_play_fwd)
        lAP.addWidget(QLabel("Step"))
        self.cb_step = QComboBox()
        self.cb_step.setFocusPolicy(Qt.NoFocus)
        self._step_values = [1, 2, 5, 10, 20, 50, 100, 200]
        self.cb_step.addItems([str(v) for v in self._step_values])
        self.cb_step.setToolTip("Frames per autoplay step. 1 = every frame\n"
                                "(usually right for judging grain).")
        self.cb_step.currentTextChanged.connect(
            lambda t: setattr(self, "step", int(t)))
        lAP.addWidget(self.cb_step)
        self.b_record = QPushButton("\u25cf REC")
        self.b_record.setCheckable(True)
        self.b_record.setToolTip("Start/stop recording (key u).\n"
                                 "mp4: <scene>/_clips/clip_NNN.mp4 (18 fps).\n"
                                 "tif: <scene>/_clips/clip_NNN/<scene>_NNNNNN.tiff\n"
                                 "     (image sequence, lossless, cineFlow layout).\n"
                                 "With autoplay = the whole sequence.")
        self.b_record.setStyleSheet(
            "QPushButton:checked { background:#c0392b; color:white; "
            "font-weight:bold; }")
        self.b_record.clicked.connect(self.toggle_record)
        lAP.addWidget(self.b_record)
        self.cb_rec_mode = QComboBox()
        self.cb_rec_mode.setFocusPolicy(Qt.NoFocus)
        self.cb_rec_mode.addItems(["tif", "mp4"])
        self.cb_rec_mode.setToolTip(
            "Recording format:\n"
            "mp4 = one video (18 fps, mp4v) -- fast, compressed.\n"
            "tif = folder clip_NNN/ with single TIFF frames --\n"
            "      lossless, for visual comparison.")
        lAP.addWidget(self.cb_rec_mode)
        return gAP

    def close(self):
        if self.writer is not None:
            self.stop_record()

    def tick(self):
        if self.writer is not None:
            self._record_current()
        if self.direction == 0:
            return
        nxt = self.m.idx + self.direction * self.step
        if not (0 <= nxt < len(self.m.files)):
            self.stop("end of scene")
            return
        self.m._goto(nxt)

    def toggle(self, direction):
        if not self.m.files:
            return
        if self.direction == direction:
            self.stop("stopped")
            return
        self.direction = direction
        self._sync_play_ui()
        if self.m._busy:
            return
        if self.m.data is not None:
            self.tick()
        else:
            self.m._dispatch(fcore._TIER_FLOW, f"Frame {self.m.idx+1}")

    def play_pause(self):
        if self.direction != 0:
            self.stop("stopped")
        else:
            self.toggle(+1)

    def stop(self, why=""):
        self.direction = 0
        self._sync_play_ui()
        if self.writer is not None:
            self.stop_record()
        if why:
            self.m.statusBar().showMessage(f"Autoplay {why}", 4000)

    def _sync_play_ui(self):
        if self.b_play_fwd is not None:
            fwd = self.direction == 1
            bwd = self.direction == -1
            self.b_play_fwd.setChecked(fwd)
            self.b_play_bwd.setChecked(bwd)
            self.b_play_fwd.setText("\u25a0" if fwd else "\u25b6")
            self.b_play_bwd.setText("\u25a0" if bwd else "\u25c0")

    def toggle_record(self):
        if self.writer is not None:
            self.stop_record()
            return
        if self.m.data is None:
            self.m.statusBar().showMessage("Nothing to record -- load a scene first.", 4000)
            return
        frame = self._compose_frame()
        if frame is None:
            self.m.statusBar().showMessage("Current view cannot be recorded.", 4000)
            return
        h, w = frame.shape[:2]
        base = self.m.folder if os.path.isdir(self.m.folder) \
            else os.path.splitext(self.m.folder)[0]
        d = base if os.path.isdir(base) else os.path.dirname(base)
        out = os.path.join(d, "_clips")
        os.makedirs(out, exist_ok=True)
        self.fmt = self.cb_rec_mode.currentText()

        if self.fmt == "tif":
            scene = safe_name(os.path.basename(os.path.normpath(base)))
            n = 1
            while os.path.exists(os.path.join(out, f"clip_{n:03d}")):
                n += 1
            self.path = os.path.join(out, f"clip_{n:03d}")
            self.writer = _TiffSeqWriter(self.path, scene)
            if not self.writer.isOpened():
                self.m.statusBar().showMessage(
                    f"Recording failed (folder?): {self.path}", 6000)
                self.writer = None
                return
            fps_note = "TIFF-Sequenz"
        else:
            n = 1
            while os.path.exists(os.path.join(out, f"clip_{n:03d}.mp4")):
                n += 1
            self.path = os.path.join(out, f"clip_{n:03d}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.writer = cv2.VideoWriter(self.path, fourcc, 18.0, (w, h))
            if not self.writer.isOpened():
                self.m.statusBar().showMessage(
                    f"recording failed (codec?): {self.path}", 6000)
                self.writer = None
                return
            fps_note = "18fps"
        self.size = (w, h)
        self.writer.write(frame)
        self.count = 1
        self.written_idx = self.m.idx
        self._sync_rec_ui()
        self.m.statusBar().showMessage(
            f"recording: {os.path.basename(self.path)} "
            f"({w}x{h} @ {fps_note}) -- 'u' stops", 6000)

    def _record_current(self):
        if self.m.idx == self.written_idx:
            return
        frame = self._compose_frame()
        if frame is None:
            return
        if (frame.shape[1], frame.shape[0]) != self.size:
            frame = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA)
        self.writer.write(frame)
        self.count += 1
        self.written_idx = self.m.idx

    def stop_record(self):
        if self.writer is None:
            return
        self.writer.release()
        self.written_idx = None
        self.m.statusBar().showMessage(
            f"recording finished: {self.count} frames -> "
            f"{os.path.basename(self.path)}", 8000)
        self.writer = None
        self._sync_rec_ui()
        if self.direction != 0:
            self.direction = 0
            self._sync_play_ui()
            self.m.statusBar().showMessage(
                f"recording finished ({self.count} frames) & autoplay "
                f"stopped -> {os.path.basename(self.path)}", 8000)

    def _sync_rec_ui(self):
        if self.b_record is not None:
            self.b_record.setChecked(self.writer is not None)

    def _compose_frame(self):
        if self.m.data is None:
            return None
        key = self.m._current_view()
        if data_key(key) not in self.m.data:
            return None
        img = self.m.canvas._compose()
        if img is None:
            return None
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return np.ascontiguousarray(img)

class SlotManager:

    def __init__(self, m):
        self.m = m
        self.names = []
        self.buttons = {}
        self.btn_default = None

    def build_box(self):
        gP = QGroupBox("Slots  (Shift+right = clear \u00b7 Ctrl+right = note)")
        lP = QGridLayout(gP)
        self.names = ["A", "B", "C", "D", "E", "F"]
        self.buttons = {}

        b_def = QPushButton("Default")
        self.btn_default = b_def
        _dvals = "<br>".join(
            f"&nbsp;&nbsp;{k} = {fcore.DEFAULT_CONFIG[k]}" for k in
            ("mode", "context", "sharp_amount", "sharp_full", "sharp_base",
             "sharp_gamma", "detail_sigma", "detail_eps", "detail_filter")
            if k in fcore.DEFAULT_CONFIG)
        b_def.setToolTip("<b>Default</b> (load only)<br><br>" + _dvals)
        b_def.clicked.connect(self.m._reset_defaults)
        lP.addWidget(b_def, 0, 0)

        b_load = QPushButton("Load \u2026")
        b_load.setToolTip(
            "Load a recipe from a cineflow.json (or a cineFlow run log).\n"
            "Only known parameters are taken; anything else is ignored,\n"
            "and what the file does not mention stays as it is.")
        b_load.clicked.connect(self.m._choose_config)
        lP.addWidget(b_load, 1, 0)

        per_row = 3
        for i, nm in enumerate(self.names):
            row, col = divmod(i, per_row)
            b = SlotButton(f"Slot {nm}")
            b.leftClicked.connect(lambda n=nm: self.load(n))
            b.rightClicked.connect(lambda n=nm: self.save(n))
            b.shiftRightClicked.connect(lambda n=nm: self.delete(n))
            b.ctrlRightClicked.connect(lambda n=nm: self.edit_note(n))
            self.buttons[nm] = b
            lP.addWidget(b, row, col + 1)
        self.refresh()
        return gP

    def load(self, name):
        slot = self.m._settings["slots"].get(name)
        if not slot:
            self.m.statusBar().showMessage(
                f"Slot {name} is empty -- right-click stores the current "
                f"set.", 5000)
            return
        clean = {k: v for k, v in slot.items() if k in SCENE_PARAMS}
        self.m._apply_preset(clean, f"Slot {name}")
        self.m.cfg["_note"] = slot.get("_note", "")

    def save(self, name):
        snap = {k: self.m.cfg[k] for k in SCENE_PARAMS if k in self.m.cfg}
        note = str(self.m.cfg.get("_note", "")).strip()
        if note:
            snap["_note"] = note[:80]
        self.m._settings["slots"][name] = snap
        _save_settings(self.m._settings)
        self.refresh()
        btn = self.buttons.get(name)
        if btn is not None:
            self._style_button(
                btn, occupied=True,
                active=self.matches_current(snap), flash=True)
            QTimer.singleShot(180, self.refresh)
        head = f"'{note}' " if note else ""
        self.m.statusBar().showMessage(
            f"Slot {name} saved: {head}mode={snap.get('mode')}, "
            f"context={snap.get('context')}, amt={snap.get('sharp_amount')}, "
            f"full={snap.get('sharp_full')}", 6000)

    def delete(self, name):
        slot = self.m._settings["slots"].get(name)
        if not slot:
            self.m.statusBar().showMessage(f"Slot {name} is already empty.", 4000)
            return
        note = slot.get("_note", "")
        head = f"\u201e{note}\u201c\n\n" if note else ""
        details = ", ".join(f"{k}={slot[k]}" for k in
                            ("mode", "context", "sharp_amount", "sharp_full")
                            if k in slot)
        from PyQt5.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self.m, f"Clear slot {name}?",
            f"Clear slot {name}?\n\n{head}{details}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            del self.m._settings["slots"][name]
            _save_settings(self.m._settings)
            self.refresh()
            self.m.statusBar().showMessage(f"Slot {name} cleared.", 4000)

    def edit_note(self, name):
        slot = self.m._settings["slots"].get(name)
        if not slot:
            self.m.statusBar().showMessage(
                f"Slot {name} is empty -- store a set first "
                f"(right-click), then annotate it.", 5000)
            return
        from PyQt5.QtWidgets import QInputDialog
        cur = slot.get("_note", "")
        text, ok = QInputDialog.getText(
            self.m, f"Slot {name} -- note",
            "Short note (one line, e.g. 'dusty, slow pan'):",
            text=cur)
        if not ok:
            return
        text = text.strip()[:80]
        if text:
            slot["_note"] = text
        else:
            slot.pop("_note", None)
        self.m._settings["slots"][name] = slot
        _save_settings(self.m._settings)
        self.refresh()
        self.m.cfg["_note"] = text

    def matches_current(self, slot):
        cur = self.m.cfg
        for k in SCENE_PARAMS:
            if k not in slot or k not in cur:
                return False
            a, b = slot[k], cur[k]
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if abs(float(a) - float(b)) > 1e-9:
                    return False
            elif a != b:
                return False
        return True

    def _style_button(self, button, *, occupied, active, flash=False):
        f = button.font()
        f.setBold(bool(active))
        button.setFont(f)
        button.setStyleSheet("color:#e0554a;" if flash else "")

    def refresh(self):
        if self.btn_default is not None:
            def_snap = {k: fcore.DEFAULT_CONFIG[k]
                        for k in SCENE_PARAMS if k in fcore.DEFAULT_CONFIG}
            self._style_button(
                self.btn_default, occupied=True,
                active=self.matches_current(def_snap))

        for nm, b in self.buttons.items():
            slot = self.m._settings["slots"].get(nm)
            if slot:
                b.setText(f"Slot {nm} \u25cf")
                note = slot.get("_note", "")
                head = f"<b>{note}</b><br>" if note else ""
                vals = "<br>".join(f"&nbsp;&nbsp;{k} = {slot[k]}" for k in
                                   ("mode", "context", "sharp_amount",
                                    "sharp_full", "sharp_base", "sharp_gamma",
                                    "detail_sigma", "detail_eps",
                                    "detail_filter")
                                   if k in slot)
                tip = (f"{head}Shift+right clears \u00b7 Ctrl+right note"
                       f"<br><br>{vals}")
                active = self.matches_current(slot)
                self._style_button(b, occupied=True, active=active)
            else:
                b.setText(f"Slot {nm}")
                tip = ("empty -- right-click stores the current set.<br>"
                       "(Ctrl+right for a note only after storing.)")
                self._style_button(b, occupied=False, active=False)
            b.setToolTip(tip)

class Main(QMainWindow):

    submit = pyqtSignal(object)

    def __init__(self, folder=None):
        super().__init__()
        self.setWindowTitle(f"flowQt {__version__} -- cineFlow Parameter-Werkbank")
        self.resize(1500, 950)

        self.files = []
        self.idx = 0
        self.data = None
        self.cfg = fcore.make_cfg()
        self._serial = 0
        self._busy = False
        self._last_off = 1
        self._slider_moved = False
        self._split_unavailable = None
        self._hf_cache_key = None
        self._hf_cache_txt = ""
        self.cfg["_neighbor_offset"] = 1
        self._saved_cfg = None

        self.ar = AutoplayRecorder(self)
        self.slots = SlotManager(self)
        self._dirty = False
        self._frame_size = None
        self._settings = _load_settings()
        self.cycle = list(self._settings["cycle"])
        self.cyc_i = 0
        self._peek_key = None

        self._build_ui()
        self._sync_backend_ui()
        self._sync_e_enabled()
        self._refresh_plot()
        self._center_on_screen()
        self._start_worker()
        QApplication.instance().installEventFilter(self)

        self.setAcceptDrops(True)

        if folder and (os.path.isdir(folder) or fcore.is_video(folder)):
            self._load_folder(folder)

    def _center_on_screen(self):
        scr = QApplication.primaryScreen()
        if scr is None:
            return
        av = scr.availableGeometry()
        w = min(self.width(), av.width())
        h = min(self.height(), av.height())
        self.resize(w, h)
        self.move(av.x() + (av.width() - w) // 2,
                  av.y() + (av.height() - h) // 2)

    def _sync_filter_params(self):
        self._sync_e_enabled()

    def _toggle_hist(self):
        if not hasattr(self, "_hist_box"):
            return
        self._hist_on = not getattr(self, "_hist_on", False)
        show = self._hist_on
        self._hist_box.setVisible(show)
        if show:
            self._update_texture_hist()
            self._hist_box.adjustSize()
            self._hist_box.move(
                12, max(12, self.canvas.height() - self._hist_box.height() - 12))
            self._hist_box.raise_()
        self.statusBar().showMessage(
            "texture histogram " + ("on" if show else "off"), 2000)

    SPLITREF_IN = 0
    SPLITREF_OUT = 1
    SPLITREF_BEST = 2

    def _split_ref_key(self):
        if getattr(self, "cb_splitref", None) is None:
            return "input"
        key = self._current_view()
        i = self.cb_splitref.currentIndex()
        if i == self.SPLITREF_OUT:
            ref_key = self._result_key()
        elif i == self.SPLITREF_BEST:
            ref_key = "output_best"
        else:
            ref_key = "input"
        return None if key == ref_key else ref_key

    def _sync_split_labels(self):
        if not hasattr(self, "cb_split") or not hasattr(self, "cb_splitref"):
            return
        ref = self.cb_splitref.currentText()
        self.cb_split.blockSignals(True)
        keep = self.cb_split.currentIndex()
        self.cb_split.setItemText(1, f"{ref} | View")
        self.cb_split.setItemText(2, f"View | {ref}")
        self.cb_split.setCurrentIndex(keep)
        self.cb_split.blockSignals(False)

        same = (self._split_ref_key() is None)
        missing = self._split_unavailable is not None
        grund = ("\n\nNo comparison right now: view and reference are the "
                 "same image." if same else
                 "\n\nNo comparison right now: the reference is not computed "
                 "for this state." if missing else "")
        self.cb_split.setToolTip(
            "Compare against the reference selected next to it.\n"
            "\u201cView\u201d = the view you are on; the word order says\n"
            "which side is which. Drag the divider with the mouse.\n"
            "Key l = mode, key k = reference." + grund)

    def _splitref_changed(self, _text=None):
        self._sync_split_labels()
        if self._ensure_split_ref():
            return
        self._redraw()
        if self.cb_split.currentIndex():
            self._warn_if_split_impossible()

    def _texref_to_p90(self):
        p90 = self._hist_tex.percentile(90)
        if p90 is None:
            self.statusBar().showMessage(
                "No texture data yet -- compute a frame first.", 4000)
            return
        w = self.params.get("sharp_full")
        if w is not None:
            w.set_value(float(p90))
            self._param_changed("sharp_full", float(p90))
            self._param_released("sharp_full")

    def _mk_param(self, key, label, lo, hi, step, dec=3, tip="", log=False,
                  expensive=False, integer=False):
        w = Param(key, label, lo, hi, step, self.cfg[key], decimals=dec,
                  log=log, expensive=expensive, integer=integer,
                  default=fcore.DEFAULT_CONFIG.get(key))
        w.changed.connect(self._param_changed)
        w.released.connect(self._param_released)
        if tip:
            w.lbl.setToolTip(tip)
        self.params[key] = w
        return w

    def _mk_int(self, key, label, lo, hi, expensive=False, tip="",
                prefix="", postfix=""):
        w = IntChoice(key, label, lo, hi, self.cfg[key], expensive=expensive,
                      default=fcore.DEFAULT_CONFIG.get(key), tip=tip,
                      prefix=prefix, postfix=postfix)
        w.changed.connect(self._param_changed)
        w.released.connect(self._param_released)
        self.params[key] = w
        return w

    _TRUST_MISMATCH_TIP = {
        "geo":
            "Forward-backward inconsistency of the flow, in px, at which\n"
            "trust drops to 0.5. A neighbour that lands more than this many\n"
            "pixels off the round-trip is distrusted.\n"
            "Smaller = stricter. Normalised: error 0 -> trust 1.",
        "pho":
            "Smoothed brightness difference at which trust drops to 0.5.\n"
            "Catches exposure and appearance changes where the geometry\n"
            "is still correct.\n"
            "Smaller = stricter. Normalised: error 0 -> trust 1.",
        "dustA":
            "Deviation from the group median, in MAD, at which trust drops\n"
            "to 0.5. Flags a neighbour whose contribution sits far outside\n"
            "the committee -- the classic dust/scratch case.\n"
            "Smaller = stricter. Normalised: error 0 -> trust 1.",
        "dustB":
            "Residual against the committee spread, at which trust drops to\n"
            "0.5. The committee EXCLUDES the input frame.\n\n"
            "Unlike dustA, the input frame is judged against its neighbours\n"
            "only -- so a defect ON the input frame can be caught too.\n"
            "Smaller = stricter. Normalised: error 0 -> trust 1.",
    }
    _TRUST_SOFTNESS_TIP = {
        "dustB":
            "Transition width around the mismatch point. Small = hard\n"
            "cut-off (trusted or not), large = soft roll-off from 1 to 0.",
    }

    TRUST_TABS = (
        ("geo", "geo", "geo_mismatch", "geo_softness", "px",
         (0.5, 12.0, 0.1), (0.1, 6.0, 0.1), False, "[px]", 15.0),
        ("pho", "photo", "photo_mismatch", "photo_softness", "0..1",
         (0.01, 1.0, 0.005), (0.002, 0.5, 0.002), True,
         "[0..1]", None),
        ("dustA", "dustA", "dustA_mismatch", "dustA_softness", "MAD",
         (0.5, 10.0, 0.1), (0.1, 5.0, 0.1), False, "[MAD]", 10.0),
        ("dustB", "dustB", "dustB_mismatch", "dustB_softness", "spread",
         (0.5, 10.0, 0.1), (0.1, 5.0, 0.1), False,
         "[spread]", 10.0),
    )

    def _build_trust_tab(self, tabs, mkParam, spec):
        kurz, reiter, kd, ks, einheit, drange, srange, log, xlabel, _xmax = spec
        w = QWidget()
        lay = _compact(QVBoxLayout(w))
        dlo, dhi, dstep = drange
        slo, shi, sstep = srange
        dec = 3 if log else 2
        tip_d = self._TRUST_MISMATCH_TIP[kurz]
        tip_s = self._TRUST_SOFTNESS_TIP.get(
            kurz,
            f"Transition width in {einheit} around the mismatch point.\n"
            "Small = hard cut-off (trusted or not), large = soft\n"
            "roll-off from 1 to 0.")
        p_d = self._mk_param(kd, f"mismatch [{einheit}]", dlo, dhi, dstep, dec,
                      log=log, expensive=True, tip=tip_d)
        p_s = self._mk_param(ks, f"softness [{einheit}]", slo, shi, sstep, dec,
                      log=log, expensive=True, tip=tip_s)
        lay.addWidget(p_d)
        _indent_row(lay, p_s)
        setattr(self, f"_p_{kurz}_delta", p_d)
        setattr(self, f"_p_{kurz}_sens", p_s)

        if kurz == "pho":
            self._p_pho_radius = self._mk_int(
                "photo_radius", "smooth [px]", 1, 15, expensive=True,
                tip="Smoothing radius of the deviation map before the curve.\n"
                    "Larger = flatter, more area-based trust map "
                    "(less grain flicker).")
            lay.addWidget(self._p_pho_radius)
        elif kurz == "dustA":
            self._p_votes = self._mk_int(
                "center_weight", "center_weight", 1, 8,
                tip="How many votes the CENTRE FRAME gets in the median committee.\n"
                    "1 = plain median (it counts like any neighbour),\n"
                    "higher = the consensus stays closer to the input frame.\n"
                    "Only has an effect in mode 'dustA'.")
            lay.addWidget(self._p_votes)
        elif kurz == "dustB":
            self._p_d2_disp = self._mk_param(
                "dustB_disagreement", "disagreement [0..1]", 0.0001, 0.2, 0.0001, 4,
                log=True, expensive=True,
                tip="Disagreement (committee spread) at which the committee\n"
                    "stops being believed. Above it the input frame is kept,\n"
                    "no matter how large the residual -- that is the\n"
                    "fast-motion case where the flow estimator, not the film,\n"
                    "is at fault.\n"
                    "Smaller = trust the committee less often. Too low and\n"
                    "fast motion smears; too high and real dust survives --\n"
                    "set it by watching the result, not a number.")
            self._p_d2_disp_s = self._mk_param(
                "dustB_disagreement_softness", "softness [0..1]", 0.00005, 0.1, 0.00005, 5,
                log=True, expensive=True,
                tip="Transition width of the disagreement limit. Small = hard\n"
                    "cut-off (believe the committee or not), large = soft\n"
                    "roll-off.")
            lay.addWidget(self._p_d2_disp)
            _indent_row(lay, self._p_d2_disp_s)

        lay.addStretch(1)
        tabs.addTab(w, reiter)
        tabs.setTabToolTip(tabs.count() - 1, f"Curve \u2014 x axis in {xlabel}")
        return w

    PLOT_OF_PARAM = {
        "geo_mismatch": "geo", "geo_softness": "geo",
        "photo_mismatch": "pho", "photo_softness": "pho", "photo_radius": "pho",
        "dustA_mismatch": "dustA", "dustA_softness": "dustA", "center_weight": "dustA",
        "dustB_mismatch": "dustB", "dustB_softness": "dustB",
        "dustB_disagreement": "dustB", "dustB_disagreement_softness": "dustB",

        "sharp_full": "tex", "sharp_gamma": "tex", "sharp_base": "tex",
    }
    PEEK_VIEW = {
        "geo":  "trust_geo",
        "pho":  "trust_photo",
        "dustA": "trust_mean",
        "dustB": "trust_mean",
        "tex":  "tex_weight",
    }

    def _refresh_plot(self):
        if not hasattr(self, "_plot"):
            return
        c = self.cfg
        which = getattr(self, "_plot_id", "tex")

        for kurz, _reiter, kd, ks, einheit, _dr, _sr, _log, xl, xmax in \
                self.TRUST_TABS:
            if kurz != which:
                continue
            d = float(c[kd])
            sv = max(float(c[ks]), 1e-6)
            xhi = xmax if xmax is not None else max(0.3, min(1.0, d * 3.0))
            fmt = f"{d:.3f}" if einheit == "0..1" else f"{d:g}"
            self._plot.set_xlabel(xl)
            unit = "" if einheit == "0..1" else f" {einheit}"
            self._plot.set_curve(
                (lambda dd, ss: (lambda x: fcore.sigmoid_trust(x, dd, ss)))(d, sv),
                0.0, xhi,
                marks=[(d, "#e0554a", f"mismatch {fmt}{unit}")])
            self._plot.set_title(f"Trust {_reiter}")
            break

        tr = max(float(c["sharp_full"]), 1e-9)
        if which == "tex":
            gm, bs = float(c["sharp_gamma"]), float(c["sharp_base"])
            p_tex = self.params.get("sharp_full")
            x_max = float(getattr(p_tex, "hi", 0.10)) if p_tex is not None else 0.10
            self._plot.set_xlabel("[std]")
            self._plot.set_curve(
                lambda x: bs + (1.0 - bs) * (min(max(x / tr, 0.0), 1.0) ** gm),
                0.0, x_max,
                marks=[(tr, "#e0554a", f"full {tr:.3f}")])
            self._plot.set_title("Texture weight")
        self._hist_tex.set_texref(tr)

    def _show_plot_for(self, key):
        pid = self.PLOT_OF_PARAM.get(key)
        if pid is None or pid == getattr(self, "_plot_id", None):
            return
        self._plot_id = pid
        self._refresh_plot()

    def _tab_selected(self, which):
        self._plot_id = which
        self._refresh_plot()
        if getattr(self, "_ui_ready", False):
            self._peek_view(which)

    def _update_texture_hist(self):
        if not hasattr(self, "_hist_tex"):
            return
        if not getattr(self, "_hist_on", False):
            return
        tex = None
        if isinstance(self.data, dict):
            tex = self.data.get("texture")
        self._hist_tex.set_texture(tex)
        p50 = self._hist_tex.percentile(50)
        p90 = self._hist_tex.percentile(90)
        p99 = self._hist_tex.percentile(99)
        if p50 is None:
            self._lbl_pct.setText("p50/p90/p99: --")
        else:
            self._lbl_pct.setText(
                f"p50 {p50:.3f} \u00b7 p90 {p90:.3f} \u00b7 p99 {p99:.3f}")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        left = QVBoxLayout()
        self._build_view_bar(left)
        self.canvas = Canvas()
        self.canvas.dropped.connect(self._load_folder)
        self.canvas.droppedConfig.connect(self._load_config_file)
        self.canvas.toggleZoom.connect(self._toggle_zoom)
        self.canvas.zoomStep.connect(
            lambda d: self._zoom_step(
                d, anchor=self.canvas.mapFromGlobal(QCursor.pos())))
        self.canvas.zoomInfo.connect(self._sync_zoom_ui)
        left.addWidget(self.canvas, 1)
        self._build_stats_row(left)
        self._build_nav_row(left)
        root.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(8)
        self._build_scene_buttons(right)
        self.params = {}

        self._build_status_box(right)
        right.addWidget(self.slots.build_box())

        self._build_flow_fusion(right)
        self._build_trust_box(right)
        self._build_stage_e(right)
        self._build_plot_box(right)
        right.addWidget(self.ar.build_box())
        right.addStretch(1)

        lbl_help = QLabel("<span style='color:#7d838b'>"
                          "<b>h</b>&nbsp; shortcuts</span>")
        lbl_help.setTextFormat(Qt.RichText)
        right.addWidget(lbl_help)

        root.addLayout(right, 1)

        self._refresh_cycle_combo()

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("ready")
        self._ui_ready = True

    def _build_view_bar(self, left):
        top = QHBoxLayout()
        self.cb_view = QComboBox()
        self.cb_view.setFocusPolicy(Qt.NoFocus)
        self.cb_view.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_view.setMinimumContentsLength(18)
        self.cb_view.setMaximumWidth(210)
        self.cb_view.setToolTip(
            "Current view in the browsing cycle.\n"
            "Up/Down steps through it, keys 1-9 select directly\n"
            "(the number is shown before each entry).\n"
            "\u25c6 = depends on the test neighbour (keys n/m).\n\n"
            "Flow views share ONE scale: hue is the direction the scene\n"
            "moves, brightness the movement per frame. fw and bw, and\n"
            "neighbours at any distance, are directly comparable --\n"
            "same colour means same direction, same brightness means\n"
            "same speed.")
        self.cb_view.currentTextChanged.connect(self._view_changed)
        self.lbl_cyc = QLabel("")
        self.lbl_cyc.setStyleSheet("color:#7d838b;")
        b_cyc = QPushButton("Cyclic View Editor")
        b_cyc.setToolTip("Edit the browsing sequence: which views, in what\n"
                         "order, with repeats (key: c)")
        b_cyc.clicked.connect(self._edit_cycle)
        self.cb_peek = QComboBox()
        self.cb_peek.setFocusPolicy(Qt.NoFocus)
        self.cb_peek.addItems(["off", "on-edit"])
        self.cb_peek.setToolTip(
            "Peek: when you edit a trust/gate parameter,\n"
            "  off     -- keep the current view; watch the change on the\n"
            "             result itself.\n"
            "  on-edit -- briefly show that parameter's map, ESC returns.")

        top.addWidget(QLabel("View:"))
        top.addWidget(self.cb_view)
        top.addWidget(self.lbl_cyc)
        top.addSpacing(12)
        top.addWidget(QLabel("peek"))
        top.addWidget(self.cb_peek)
        top.addSpacing(12)
        top.addWidget(b_cyc)
        top.addStretch(1)

        self.cb_splitref = QComboBox()
        self.cb_splitref.setFocusPolicy(Qt.NoFocus)
        self.cb_splitref.addItems(["In", "Out", "best"])
        self.cb_splitref.setToolTip(
            "What to compare against (key k cycles):\n\n"
            "In    the Input view -- the unprocessed frame.\n"
            "Out   output -- the final result of the selected mode.\n"
            "best  the blend without dedusting.\n\n"
            "With 'Out' you hold an intermediate view against what\n"
            "comes out in the end. With 'best' you lay the dedusted\n"
            "result over the plain one and drag the divider across a\n"
            "detail -- that is how you see what the dedust costs you.\n"
            "In best mode it is the same image, so the split stays off.")
        self.cb_splitref.currentTextChanged.connect(self._splitref_changed)

        self.cb_backend = QComboBox()
        self.cb_backend.setFocusPolicy(Qt.NoFocus)
        for k in fcore.ALL_BACKENDS:
            self.cb_backend.addItem(fcore.backend_label(k), k)
        i = self.cb_backend.findData(str(self.cfg.get("flow_backend",
                                                      fcore.DEFAULT_BACKEND)))
        self.cb_backend.setCurrentIndex(max(0, i))
        self.cb_backend.currentIndexChanged.connect(self._backend_changed)

        self.sp_off = CenterSlider(Qt.Horizontal)
        self.sp_off.setRange(-30, 30)
        self.sp_off.setInvertedAppearance(False)
        self.sp_off.setInvertedControls(False)
        self.sp_off.setValue(1)
        self.sp_off.setFixedWidth(190)
        self.sp_off.setTickPosition(QSlider.TicksBelow)
        self.sp_off.setTickInterval(5)
        self.lbl_off = QLabel("In+1")
        self.lbl_off.setFixedWidth(46)
        self.lbl_off.setStyleSheet("font-family:monospace;")
        self.sp_off.setToolTip(
            "Time offset of the test neighbour for the single frame\n"
            "views. Keys n/m step it too.\n\n"
            "0 is skipped -- the input frame is not its own neighbour.")
        self.sp_off.valueChanged.connect(self._offset_changed)
        top.addWidget(self.sp_off)
        top.addWidget(self.lbl_off)

        self.cb_split = QComboBox()
        self.cb_split.setFocusPolicy(Qt.NoFocus)
        self.cb_split.addItems(["Off", "In | View", "View | In"])
        self.cb_split.currentIndexChanged.connect(self._split_changed)
        top.addWidget(self.cb_split)
        top.addWidget(self.cb_splitref)

        self.cb_zoom = QComboBox()
        self.cb_zoom.addItems(Canvas.ZOOM_NAMES)
        self.cb_zoom.setFocusPolicy(Qt.NoFocus)
        self.cb_zoom.setToolTip(
            "Display size.\n"
            "Fit = fit the whole image (enlarges too, if there is room).\n"
            "1x/2x/4x/8x = image pixels per physical screen pixel; from 2x\n"
            "on it draws unsmoothed, so you can see the grain.\n\n"
            "z / Shift+z = step up/down, mouse wheel = zoom,\n"
            "double-click = Fit <-> last step. Drag to pan.")
        self.cb_zoom.currentIndexChanged.connect(self._zoom_changed)
        top.addWidget(self.cb_zoom)
        self.lbl_zoom = QLabel("")
        self.lbl_zoom.setStyleSheet("color:#8a9099;")
        self.lbl_zoom.setToolTip("Real display scale (image pixels per "
                                 "physical screen pixel)")
        top.addWidget(self.lbl_zoom)

        self._sync_split_labels()
        left.addLayout(top)

    def _build_stats_row(self, left):
        stats = QHBoxLayout()
        stats.setSpacing(18)
        mono = "font-family:monospace; padding:3px;"

        self.st_texw = QLabel("")
        self.st_texw.setStyleSheet(f"color:#8fb8d8; {mono}")
        self._tip_texw = (
            "<b>Adaption</b> \u2014 how much of the possible texture-driven "
            "sharpening is actually in use right now, as a percentage. Low "
            "means the image is being sharpened almost flatly (base only); "
            "high means the sharpening is following the texture \u2014 "
            "strong on structure, gentle on smooth areas.<br><br>"
            "Roughly 30\u201390&#37; is fine. Values below indicate that the "
            "whole image is basically getting only the flat base "
            "treatment.<br><br>"
            "To improve it, adjust the parameters on the texture tab. Guide "
            "value for 'full': the p90 from the texture histogram (key t).")
        self.st_texw.setToolTip(self._tip_texw)

        self.st_tex = QLabel("")
        self.st_tex.setStyleSheet(f"color:#8fb8d8; {mono}")
        self.st_tex.setToolTip(
            "<b>Tex p90 vs. ref</b> \u2014 the measured texture of the "
            "material (p90) against the configured reference ('full').<br><br>"
            "When 'full' sits close to the p90, most of the image is "
            "processed adaptively. Set it far above (e.g. 0.30 against 0.03) "
            "and the curve stays near its base \u2014 almost nothing gets "
            "the adaptive treatment. Set it too far below, down into the "
            "grain, and even flat areas reach full strength \u2014 that is "
            "where grain gets sharpened as if it were structure.<br><br>"
            "<b>Remedy:</b> bring 'full' close to the p90. The right value "
            "depends on the material (fine K25 vs. coarse AGFA).")

        self.st_trust = QLabel("")
        self.st_trust.setStyleSheet(f"color:#8fb8d8; {mono}")
        self.st_trust.setToolTip(
            "<b>Trust by distance</b> \u2014 how much a neighbour at this "
            "distance still contributes on average (0\u20131).<br><br>"
            "Read off how far the window is worth widening: if trust is "
            "still high a few frames out (e.g. \u00b11:0.75, \u00b13:0.70), "
            "every further neighbour pays in and a larger <b>context</b> "
            "helps. If it has already fallen off close in (e.g. "
            "\u00b11:0.60, \u00b13:0.25), the distant neighbours are "
            "discarded anyway \u2014 \u00b15 buys flow calls and nothing "
            "else.<br><br>"
            "<b>Remedy:</b> raise <b>context</b> only up to where trust "
            "stops paying in. Cost grows linearly, benefit only with "
            "\u221aN.")

        self.st_hf = QLabel("")
        self.st_hf.setStyleSheet(f"color:#8fb8d8; {mono}")
        self.st_hf.setToolTip(
            "<b>HF balance</b> \u2014 high-frequency energy at three points of "
            "the chain, each as the change against the step before.<br>"
            "Measured as the spread of the luma residual after a 5\u00d75 box "
            "\u2014 crude, but the same at every point.<br><br>"
            "<b>Fusion</b>: what the neighbour averaging takes away. Negative "
            "is the normal case (grain). Strongly negative means structure is "
            "going with it.<br>"
            "<b>Sharpening</b>: what stage E gives back \u2014 follows "
            "<b>'amount'</b> directly.<br>"
            "<b>net</b>: result against the input frame. The two factors "
            "multiply.<br><br>"
            "Only filled on the <b>Result</b> view \u2014 the diagnostic views "
            "have no blends at all, and the raw frame needs no balance.<br><br>"
            "<b>Not a quality measure.</b> Grain and detail are both high "
            "frequency \u2014 this number does not tell them apart. It shows "
            "where the energy goes, not whether it looks good. A net well "
            "above zero on clean material is plausible; very high values hint "
            "at oversharpening.")

        for wdg in (self.st_texw, self.st_tex, self.st_trust, self.st_hf):
            stats.addWidget(wdg)
        stats.addStretch(1)
        left.addLayout(stats)

    def _build_nav_row(self, left):
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("<")
        self.btn_next = QPushButton(">")
        self.btn_prev.clicked.connect(lambda: self._goto(self.idx - 1))
        self.btn_next.clicked.connect(lambda: self._goto(self.idx + 1))
        self.sld_frame = QSlider(Qt.Horizontal)
        self.sld_frame.setMinimum(0)
        self.sld_frame.valueChanged.connect(self._frame_slider)
        self.sld_frame.sliderReleased.connect(self._frame_released)
        self.sld_frame.sliderPressed.connect(
            lambda: setattr(self, "_slider_moved", False))
        self.lbl_frame = QLabel("- / -")
        self.lbl_frame.setMinimumWidth(110)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.sld_frame, 1)
        nav.addWidget(self.btn_next)
        nav.addWidget(self.lbl_frame)
        left.addLayout(nav)

    def _build_scene_buttons(self, right):
        btns = QHBoxLayout()
        b_open = QPushButton("Load Tif")
        b_open.setToolTip("Open a folder of TIFF frames (one scene).\n\n"
                          "Video files use the button next to it -- a\n"
                          "QFileDialog can offer folders OR files, not both.")
        b_open.clicked.connect(self._choose_folder)
        b_video = QPushButton("Load Video")
        b_video.setToolTip("Open a video file (.mov/.mkv/.mp4/.avi).\n\n"
                           "Separate from the folder button because a\n"
                           "QFileDialog can offer folders OR files, not both.\n"
                           "Under WSL2 (no drag and drop) this is the only\n"
                           "way to load a video.")
        b_video.clicked.connect(self._choose_video)

        self.b_export = SlotButton("Save recipe")
        self.b_export.setToolTip(
            "Left: write the current recipe to the scene folder\n"
            "      (<scene>/cineflow.json) -- this is what cineFlow reads\n"
            "      on its own.\n"
            "Right: save as \u2026 -- anywhere you like")
        self.b_export.leftClicked.connect(self._export)
        self.b_export.rightClicked.connect(self._export_as)
        b_export = self.b_export
        btns.addWidget(b_open); btns.addWidget(b_video); btns.addWidget(b_export)
        right.addLayout(btns)

    def _build_flow_fusion(self, right):
        gA = QGroupBox("Engine")
        lA = _compact(QVBoxLayout(gA), spacing=4)

        frow = QHBoxLayout()
        frow.addWidget(QLabel("flow"))
        frow.addWidget(self.cb_backend, 1)
        lA.addLayout(frow)

        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("mode"))
        self.cb_mode = QComboBox()
        self.cb_mode.setFocusPolicy(Qt.NoFocus)
        self.cb_mode.addItems(["best", "dustA", "dustB"])
        self.cb_mode.setCurrentText(self.cfg.get("mode", "best"))
        self.cb_mode.setToolTip(
            "best  = trust-weighted fusion (the normal case).\n"
            "dustA = group median/MAD consensus. The input frame is a MEMBER\n"
            "        of the committee that judges it.\n"
            "dustB = committee WITHOUT the input frame. The input can no\n"
            "        longer vote on itself, and committee disagreement\n"
            "        protects it where the flow estimator struggles.\n\n"
            "dustA is generally the slightly better performer; dustB is the\n"
            "alternative for scenes where A removes too much. Try and test.")
        self.cb_mode.currentTextChanged.connect(self._mode_changed)
        mrow.addWidget(self.cb_mode, 1)
        lA.addLayout(mrow)

        self._add(lA, "downscale", "downscale", 1.2, 8.0, 0.1,
                  self.cfg["downscale"], expensive=True,
                  tip="DIVISOR of the flow input (not a scale!): 2.0 = half the\n"
                      "edge length, 1.2 = 83%, 1.0 would be full resolution.\n"
                      "Larger = smaller image, less VRAM. Also less grain\n"
                      "(which RAFT should not lock onto) at the cost of less\n"
                      "structure.\n\n"
                      "Cost grows QUADRATICALLY: 2.0 -> 1.2 is ~2.8x the\n"
                      "pixels. The lower bound depends on the backend and the\n"
                      "scan size: GPU flow is capped by VRAM, CPU flow allows\n"
                      "full resolution (1.0).")

        self._p_radius = self._mk_int(
            "context", "context", 1, 8, expensive=True,
            prefix="\u00b1", postfix="neighbors",
            tip="Window of attention: +-N neighbour frames considered before\n"
                "fusion (best) or committee (dust). Each costs 2 flow calls --\n"
                "cost grows linearly, benefit only with sqrt(N).")
        lA.addWidget(self._p_radius)

        right.addWidget(gA)

    def _build_trust_box(self, right):
        gT = QGroupBox("Trust")
        lT = _compact(QVBoxLayout(gT), spacing=4)

        tabsT = QTabWidget()
        tabsT.setFocusPolicy(Qt.NoFocus)
        lT.addWidget(tabsT)
        self._tabsTrust = tabsT

        for _spec in self.TRUST_TABS:
            self._build_trust_tab(tabsT, self._mk_param, _spec)
        tabsT.currentChanged.connect(
            lambda i: self._tab_selected(self.TRUST_TABS[i][0]))
        tabsT.tabBarClicked.connect(
            lambda i: self._tab_selected(self.TRUST_TABS[i][0]))
        _idx = {spec[0]: i for i, spec in enumerate(self.TRUST_TABS)}
        self._tab_dustA = _idx["dustA"]
        self._tab_dustB = _idx["dustB"]
        self._tab_pho = _idx["pho"]

        right.addWidget(gT)

    def _build_stage_e(self, right):
        gE = QGroupBox("Enhance")
        lE = _compact(QVBoxLayout(gE), spacing=4)

        self._p_amount = self._mk_param(
            "sharp_amount", "amount (0=off)", 0.0, 12.0, 0.25, 2,
            tip="Master control for the whole enhancement stage. 0 = off\n"
                "(skipped entirely). Above 0 it sets the overall sharpening\n"
                "level; where and how strongly the stage acts is set by the\n"
                "trust tabs and the texture transfer curve.")
        lE.addWidget(self._p_amount)

        tabsE = QTabWidget()
        tabsE.setFocusPolicy(Qt.NoFocus)
        lE.addWidget(tabsE)
        tabsE.currentChanged.connect(
            lambda i: self._tab_selected("tex") if i == 0 else None)
        tabsE.tabBarClicked.connect(
            lambda i: self._tab_selected("tex") if i == 0 else None)
        self._tabsE = tabsE

        tCur = QWidget()
        lCur = _compact(QVBoxLayout(tCur))
        self._p_texref = self._mk_param(
            "sharp_full", "full", 0.005, 0.10, 0.001, 3, log=True,
            tip="Texture level at which sharpening reaches full strength\n"
                "(unit: local std of luma, r=4). At or above 'full', a\n"
                "pixel gets the complete amount; below, the curve rolls it\n"
                "back toward base.\n"
                "Set 'full' high and the adaptive part is effectively off\n"
                "-- then only trust gates.\n\n"
                "Key t overlays the texture histogram on the image -- that\n"
                "shows where the texture of the material actually lies\n"
                "(p90 is the usual starting point).")
        lCur.addWidget(self._p_texref)
        self._p_gamma = self._mk_param(
            "sharp_gamma", "gamma", 0.1, 6.0, 0.1, 2,
            tip="Shape of the curve below 'full'. >1 separates confirmed\n"
                "structure from ambiguous grain, <1 lifts mid textures.")
        self._p_base = self._mk_param(
            "sharp_base", "base", 0.0, 1.0, 0.05, 2,
            tip="Weight in textureless areas -- the floor the texture curve\n"
                "holds to when 'full' sits far above the actual texture.\n"
                "base = 0 means flat areas get no sharpening at all; small\n"
                "values keep grain from being lifted there.")
        lCur.addWidget(self._p_gamma)
        lCur.addWidget(self._p_base)
        lCur.addStretch(1)
        tabsE.addTab(tCur, "texture")

        tFil = QWidget()
        lFil = _compact(QVBoxLayout(tFil))
        frow2 = QHBoxLayout()
        frow2.addWidget(QLabel("algo"))
        self.cb_filter = QComboBox()
        self.cb_filter.setFocusPolicy(Qt.NoFocus)
        self.cb_filter.addItems(["guided", "gauss"])
        self.cb_filter.setCurrentText(self.cfg["detail_filter"])
        self.cb_filter.setToolTip(
            "guided = edge-aware (eps active). gauss = edge-blind,\n"
            "sigma is then the frequency cutoff and eps has no effect.")
        self.cb_filter.currentTextChanged.connect(
            lambda v: (self._param_changed("detail_filter", v),
                       self._param_released("detail_filter"),
                       self._sync_filter_params()))
        frow2.addWidget(self.cb_filter, 1)
        lFil.addLayout(frow2)
        self._p_sigma = self._mk_param(
            "detail_sigma", "sigma", 0.2, 3.0, 0.05, 2,
            tip="guided: sets the window radius r = ceil(3*sigma) -- and thus\n"
                "what eps is compared against (pin sigma down first, then\n"
                "sweep eps).\n"
                "gauss: frequency cutoff in pixels. Match it to the finest\n"
                "real film detail you want to keep.\n\n"
                "Example: at a scan resolution of 268 px/mm the finest real\n"
                "film detail is about 3 px wide; sigma 0.5 puts the cutoff\n"
                "right there. Work out the equivalent for your own scan\n"
                "resolution.")
        self._p_eps = self._mk_param(
            "detail_eps", "eps", 0.001, 0.10, 0.001, 3, log=True,
            tip="Edge threshold of the guided filter (only active there).\n"
                "Small (0.01): strongly edge-preserving.\n"
                "Large (>0.1): approaches a box filter and loses exactly the\n"
                "property guided is chosen for.")
        lFil.addWidget(self._p_sigma)
        lFil.addWidget(self._p_eps)
        lFil.addStretch(1)
        tabsE.addTab(tFil, "filter")

        right.addWidget(gE)

        self._hist_box = QWidget(self.canvas)
        self._hist_box.setStyleSheet(
            "background:#1b1b1e; border:1px solid #3a3a3e; border-radius:4px;")
        _hl = QVBoxLayout(self._hist_box)
        _hl.setContentsMargins(8, 6, 8, 6)
        _hl.setSpacing(4)
        _cap = QLabel("Texture distribution  (t closes)")
        _cap.setStyleSheet("color:#9aa0a6; border:none;")
        _hl.addWidget(_cap)
        self._hist_tex = TextureHistogram()
        self._hist_tex.setMinimumWidth(320)
        self._hist_tex.setStyleSheet("border:none;")
        _hl.addWidget(self._hist_tex)
        hrow = QHBoxLayout()
        self._lbl_pct = QLabel("p50/p90/p99: --")
        self._lbl_pct.setStyleSheet("color:#7d838b; border:none;")
        b_p90 = QPushButton("full = p90")
        b_p90.setStyleSheet(
            "QPushButton { border:1px solid #4e84be; border-radius:3px; "
            "padding:2px 8px; color:#8fb8d8; background:transparent; }"
            "QPushButton:hover { background:#4e84be; color:#161618; }")
        b_p90.setToolTip("Sets 'full' to the 90th percentile of the current\n"
                         "texture map -- the usual starting point.")
        b_p90.clicked.connect(self._texref_to_p90)
        hrow.addWidget(self._lbl_pct, 1)
        hrow.addWidget(b_p90)
        _hl.addLayout(hrow)
        self._hist_box.hide()
        self._hist_on = False
        self._hist_box.adjustSize()
        self.canvas.set_overlay(self._hist_box)
        self._sync_filter_params()
        self._refresh_plot()

    def _build_plot_box(self, right):
        self._plot = CurvePlot()
        self._plot.setMinimumHeight(124)
        self._plot_id = "tex"
        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 8, 0, 8)
        wrap.addWidget(self._plot)
        right.addLayout(wrap)

    def _build_status_box(self, right):
        gB = QGroupBox("Status")
        lB = QVBoxLayout(gB)
        self.busy = Status()
        lB.addWidget(self.busy)
        right.addWidget(gB)

    def _add(self, lay, key, label, lo, hi, step, val, integer=False,
             expensive=False, tip=""):
        w = Param(key, label, lo, hi, step, val, expensive=expensive,
                  integer=integer, decimals=2,
                  default=fcore.DEFAULT_CONFIG.get(key))
        w.changed.connect(self._param_changed)
        w.released.connect(self._param_released)
        if tip:
            w.lbl.setToolTip(tip)
        self.params[key] = w
        lay.addWidget(w)

    def _start_worker(self):
        self.thread = QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.submit.connect(self.worker.run)
        self.worker.done.connect(self._on_done)
        self.worker.started_job.connect(self._on_started)
        self.worker.failed.connect(self._on_failed)
        self.thread.start()

    def _refresh_cycle_combo(self):
        self.cb_view.blockSignals(True)
        self.cb_view.clear()
        for i, v in enumerate(self.cycle):
            key = self._mode_key(v)
            mark = ("\u25c6 " if data_key(key) in fcore._OFFSET_DEPENDENT_KEYS
                    else "   ")
            self.cb_view.addItem(f"{mark}{i+1}. {self._view_label_dyn(v)}")
        self.cyc_i = min(self.cyc_i, len(self.cycle) - 1)
        self.cb_view.setCurrentIndex(self.cyc_i)
        self.cb_view.blockSignals(False)
        self.lbl_cyc.setText(f"{self.cyc_i+1}/{len(self.cycle)}")

    def _view_label_dyn(self, key):
        mode = str(self.cfg.get("mode", "best"))
        if key == RESULT_VIEW:
            return f"Output ({mode})"
        if key in MODE_DEPENDENT_VIEWS:
            return f"{view_label(key)} ({mode})"
        return view_label(key)

    def _save_view(self):
        if not self.data or not getattr(self, "folder", None):
            self.statusBar().showMessage("Nothing to save.", 4000)
            return
        key = self._current_view()
        if data_key(key) not in self.data:
            self.statusBar().showMessage(
                f"View \u201c{key}\u201d is not computed.", 4000)
            return

        fn = display_fn(key, self.cfg)
        img = fn(self.data[data_key(key)])
        if img.ndim == 2:
            img = np.stack([img] * 3, axis=-1)

        base = self.folder if os.path.isdir(self.folder) \
            else os.path.splitext(self.folder)[0]
        d = base if os.path.isdir(base) else os.path.dirname(base)
        out = os.path.join(d, "_snapshots")
        try:
            os.makedirs(out, exist_ok=True)
            eff, _want = fcore.resolve_backend(self.cfg, None)
            tag = (f"f{self.idx+1:05d}_{key}"
                   f"_{eff}_{self.cfg.get('mode', 'best')}"
                   f"_sc{self.cfg['downscale']:g}"
                   f"_ctx{self.cfg['context']}"
                   f"_sx{self.cfg['sharp_amount']:g}")
            p = os.path.join(out, tag + ".png")
            n = 1
            while os.path.exists(p):
                p = os.path.join(out, f"{tag}_{n}.png")
                n += 1
            if not imwrite_unicode(p, img):
                self.statusBar().showMessage(
                    f"could not write {p}", 8000)
                return
            self.statusBar().showMessage(
                f"saved: {os.path.basename(p)}", 6000)
        except Exception as e:
            self.statusBar().showMessage(
                f"saving failed: {e!r}", 8000)

    def _cycle_entry(self):
        if self._peek_key is not None:
            return self._peek_key
        return self.cycle[self.cyc_i] if self.cycle else RESULT_VIEW

    def _mode_key(self, view):
        if view == RESULT_VIEW:
            return self._result_key()
        if view in MODE_DEPENDENT_VIEWS:
            return f"{view}_{self.cfg.get('mode', 'best')}"
        return view

    def _result_key(self):
        return {"dustA": "output_dustA",
                "dustB": "output_dustB"}.get(
                    self.cfg.get("mode", "best"), "output_best")

    def _needs_dustA(self):
        return self.cfg.get("mode", "best") == "dustA"

    def _needs_dustB(self):
        return self.cfg.get("mode", "best") == "dustB"

    def _current_view(self):
        return self._mode_key(self._cycle_entry())

    def _goto_view(self, i):
        if not self.cycle:
            return
        self._peek_key = None
        self.cyc_i = max(0, min(int(i), len(self.cycle) - 1))
        self.cb_view.blockSignals(True)
        self.cb_view.setCurrentIndex(self.cyc_i)
        self.cb_view.blockSignals(False)
        self._sync_peek_label()
        self._view_changed(None)

    def _peek_view(self, plot_id):
        if self.cb_peek.currentText() != "on-edit":
            return
        key = self.PEEK_VIEW.get(plot_id)
        if key is None or key == self._peek_key:
            return
        if self._peek_key is None and self._cycle_entry() == key:
            return
        if self.data is None or data_key(self._mode_key(key)) not in self.data:
            return
        self._peek_key = key
        self._sync_peek_label()
        self._apply_view_change()
        self.statusBar().showMessage(
            f"preview: {view_label(key)} \u2014 ESC to go back", 4000)

    def _peek_end(self, silent=False):
        if self._peek_key is None:
            return False
        self._peek_key = None
        self._sync_peek_label()
        self._apply_view_change()
        if not silent:
            self.statusBar().showMessage("preview ended", 2000)
        return True

    def _sync_peek_label(self):
        if self._peek_key is None:
            self.lbl_cyc.setStyleSheet("color:#7d838b;")
            self.lbl_cyc.setText(f"{self.cyc_i+1}/{len(self.cycle)}")
            self.lbl_cyc.setToolTip("")
        else:
            self.lbl_cyc.setStyleSheet("color:#5fd3d8;")
            self.lbl_cyc.setText(
                f"\u25b8 {view_label(self._peek_key)}")
            self.lbl_cyc.setToolTip(
                "Curve preview. The cycle is unchanged \u2014\n"
                "ESC (or Up/Down, 1-9) returns to it.")

    def _apply_view_change(self):
        v = self._current_view()
        self._sync_diag_enabled(v)
        if self.data is not None and data_key(v) in self.data:
            self._redraw()
        else:
            self._dispatch(fcore._TIER_FLOW, "view")

    def _step_view(self, d):
        if not self.cycle:
            return
        self._goto_view((self.cyc_i + d) % len(self.cycle))

    def _read_scene_cfg(self, path):
        try:
            import json
            with open(path) as f:
                doc = json.load(f)
            if not isinstance(doc, dict):
                return None
            return {k: v for k, v in doc.items() if k in SCENE_PARAMS}
        except Exception:
            return None

    def _sync_dirty(self):
        hat_datei = bool(getattr(self, "folder", None)) and \
            os.path.isfile(scene_config_path(self.folder))
        self._dirty = bool(
            getattr(self, "folder", None)) and (
                not hat_datei
                or (self._saved_cfg is not None
                    and self._recipe_dict() != self._saved_cfg))
        self.slots.refresh()
        if self._dirty:
            self.b_export.setStyleSheet(
                "background:#2f5c8a; border:1px solid #4e84be; color:#e8f0f8;")
            self.b_export.setToolTip(
                "no cineflow.json for this scene yet \u2014 click to write it"
                if not hat_datei else
                "unsaved changes \u2014 click to write the cineflow.json")
        else:
            self.b_export.setStyleSheet("")
            self.b_export.setToolTip(
                "Write the current parameters to the scene folder")

    def _sync_diag_enabled(self, view):
        on = data_key(view) in fcore._OFFSET_DEPENDENT_KEYS
        for wdg in (self.sp_off, self.lbl_off):
            wdg.setEnabled(on)
        self.lbl_off.setToolTip(
            "" if on else
            f"View \u201c{view}\u201d does not use the test neighbour.\n"
            f"Views marked \u25c6 in the list do.")

    def _edit_cycle(self):
        self._ed = CycleEditor(self.cycle, self)
        self._ed.changed.connect(self._cycle_edited)
        self._ed.exec_()

    def _cycle_edited(self, cyc):
        self.cycle = list(cyc)
        self._settings["cycle"] = list(cyc)
        _save_settings(self._settings)
        self._refresh_cycle_combo()
        self._view_changed(None)

    def eventFilter(self, obj, ev):
        if ev.type() != QEvent.KeyPress:
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit,)) or (
                isinstance(fw, (QSpinBox, QDoubleSpinBox)) and fw.hasFocus()):
            return False
        if self._handle_key(ev.key(), ev.modifiers()):
            return True
        return False

    def dragEnterEvent(self, ev):
        if Canvas.classify_drop(ev.mimeData())[0]:
            ev.setDropAction(Qt.CopyAction)
            ev.accept()
            self.canvas.set_drop_hint(True)
        else:
            ev.ignore()

    def dragMoveEvent(self, ev):
        if Canvas.classify_drop(ev.mimeData())[0]:
            ev.setDropAction(Qt.CopyAction)
            ev.accept()
        else:
            ev.ignore()

    def dragLeaveEvent(self, ev):
        self.canvas.set_drop_hint(False)

    def dropEvent(self, ev):
        self.canvas.set_drop_hint(False)
        kind, p = Canvas.classify_drop(ev.mimeData())
        if kind == "config":
            ev.acceptProposedAction()
            self._load_config_file(p)
        elif kind == "scene":
            ev.acceptProposedAction()
            self._load_folder(p)
        else:
            ev.ignore()

    NAV_STEP = {
        Qt.NoModifier:          1,
        Qt.ShiftModifier:      10,
        Qt.ControlModifier:   100,
    }

    def _handle_key(self, k, mods=Qt.NoModifier):
        _autoplay_safe = (Qt.Key_X, Qt.Key_Y, Qt.Key_U, Qt.Key_Space,
                          Qt.Key_Up, Qt.Key_Down)
        if (self.ar.direction != 0
                and k not in _autoplay_safe
                and not (Qt.Key_1 <= k <= Qt.Key_9)):
            self.ar.stop("stopped")
        nav = mods & (Qt.ShiftModifier | Qt.ControlModifier)
        step = self.NAV_STEP.get(nav)

        if k in (Qt.Key_Left, Qt.Key_Right) and step is not None:
            d = -step if k == Qt.Key_Left else step
            self._goto(self.idx + d)
            return True

        if k == Qt.Key_Escape:
            return self._peek_end()

        if   k == Qt.Key_Up:    self._step_view(-1)
        elif k == Qt.Key_Down:  self._step_view(+1)
        elif k == Qt.Key_PageUp:   self._goto(self.idx - 10)
        elif k == Qt.Key_PageDown: self._goto(self.idx + 10)
        elif k == Qt.Key_Home:  self._goto(0)
        elif k == Qt.Key_End:   self._goto(len(self.files) - 1)
        elif k == Qt.Key_N:     self._nudge_diag(-1)
        elif k == Qt.Key_M:     self._nudge_diag(+1)
        elif k == Qt.Key_Z:
            self._zoom_step(-1 if (mods & Qt.ShiftModifier) else +1)
        elif k == Qt.Key_L:
            self.cb_split.setCurrentIndex(
                (self.cb_split.currentIndex() + 1) % 3)
        elif k == Qt.Key_K:
            self.cb_splitref.setCurrentIndex(
                (self.cb_splitref.currentIndex() + 1)
                % self.cb_splitref.count())
        elif k == Qt.Key_G:
            self.cb_filter.setCurrentIndex(1 - self.cb_filter.currentIndex())
        elif k == Qt.Key_R:
            n = self.cb_backend.count()
            if n > 1:
                self.cb_backend.setCurrentIndex(
                    (self.cb_backend.currentIndex() + 1) % n)
        elif k == Qt.Key_D:     self._reset_defaults()
        elif k == Qt.Key_E:     self._export()
        elif k == Qt.Key_C:     self._edit_cycle()
        elif k == Qt.Key_H:     self._show_help()
        elif k == Qt.Key_Space: self.ar.play_pause()
        elif k == Qt.Key_X:     self.ar.toggle(+1)
        elif k == Qt.Key_Y:     self.ar.toggle(-1)
        elif k == Qt.Key_U:     self.ar.toggle_record()
        elif k == Qt.Key_P:     self._save_view()
        elif k == Qt.Key_T:     self._toggle_hist()
        elif Qt.Key_1 <= k <= Qt.Key_9:
            i = k - Qt.Key_1
            if i < len(self.cycle):
                self._goto_view(i)
            else:
                self.statusBar().showMessage(
                    f"the cycle has only {len(self.cycle)} views", 2000)
        else:
            return False
        return True

    def _dispatch(self, tier, reason):
        if not self.files:
            return
        if tier != fcore._TIER_FLOW and self.data is None:
            tier = fcore._TIER_FLOW
        self._serial += 1
        self.worker.set_latest(self._serial)

        cfg = dict(self.cfg)
        cfg["_need_dustA"] = self._needs_dustA()
        cfg["_need_dustB"] = self._needs_dustB()
        data = dict(self.data) if tier != fcore._TIER_FLOW else None
        eff_backend, _want = fcore.resolve_backend(cfg, None)
        active = data_key(self._current_view())
        if (getattr(self, "cb_split", None) is not None
                and self.cb_split.currentIndex()
                and self._split_ref_key() is not None):
            active = None
        job = Job(tier, self.idx, self.files, cfg, eff_backend,
                  active, data=data, serial=self._serial)
        job.reason = reason
        self.submit.emit(job)

    @pyqtSlot(str, int)
    def _on_started(self, tier_name, tier):
        self._busy = True
        if tier in (fcore._TIER_FLOW, fcore._TIER_TRUST, fcore._TIER_FUSION):
            self.busy.start(tier_name)
            self.statusBar().showMessage(f"computing {tier_name} ...")

    @pyqtSlot(object, object, int)
    def _on_done(self, data, job, serial):
        if serial < self._serial:
            return
        self._busy = False
        self.data = data
        self.busy.finish(TIER_NAMES[job.tier], job.msec,
                         getattr(job, "reason", ""))
        self._redraw()
        self._update_status_state()
        self._sync_flow_div_range()
        self._update_texture_hist()
        self.statusBar().showMessage(
            f"{getattr(job,'reason','')}  --  {job.msec:.0f} ms", 4000)
        self.ar.tick()

    @pyqtSlot(str)
    def _on_failed(self, msg):
        self._busy = False
        self.busy.stop()
        self.statusBar().showMessage("ERROR: " + msg, 8000)

    def _param_changed(self, key, value):
        self.cfg[key] = value
        self._sync_dirty()
        if key == "sharp_amount":
            self._sync_e_enabled()
        if key in self.PLOT_OF_PARAM:
            self._show_plot_for(key)
            self._refresh_plot()
            self._peek_view(self.PLOT_OF_PARAM[key])

    def _param_released(self, key):
        tier = fcore.dirty_tier([key])
        if tier is None:
            return
        self._dispatch(tier, key)

    def _view_changed(self, _):
        self._peek_key = None
        i = self.cb_view.currentIndex()
        if 0 <= i < len(self.cycle):
            self.cyc_i = i
        self._sync_peek_label()
        self._apply_view_change()

    def _nudge_diag(self, d):
        if self.sp_off.isEnabled():
            self.sp_off.setValue(self.sp_off.value() + d)
        else:
            self.statusBar().showMessage(
                f"View \u201c{self._current_view()}\u201d does not use the "
                f"test neighbour (\u25c6 views do).", 3000)

    def _offset_changed(self, v):
        if v == 0:
            v = 1 if self._last_off < 0 else -1
            self.sp_off.blockSignals(True)
            self.sp_off.setValue(v)
            self.sp_off.blockSignals(False)
        self._last_off = v
        self.lbl_off.setText(f"In{v:+d}")
        col = "#b48ce0" if v < 0 else "#5fd3d8"
        self.lbl_off.setStyleSheet(f"font-family:monospace; color:{col};")
        self.cfg["_neighbor_offset"] = v
        self._dispatch(fcore._TIER_FLOW, f"test neighbour {v:+d}")

    def _show_help(self):
        rows = [
            ("Navigation", ""),
            ("Left / Right", "frame \u00b11"),
            ("Shift + Left/Right", "frame \u00b110"),
            ("Ctrl + Left/Right", "frame \u00b1100"),
            ("Home / End", "first / last frame of the scene"),
            ("Up / Down", "step through views"),
            ("1 \u2026 9", "select a view directly (number shown in the list)"),
            ("n / m", "test neighbour \u2213 / \u00b1"),
            ("", ""),
            ("View", ""),
            ("z / Shift+z", "zoom step up / down (Fit, 1x, 2x, 4x, 8x)"),
            ("Mouse wheel", "zoom around the pointer"),
            ("Click + drag", "pan"),
            ("l", "split on/off"),
            ("k", "split reference: In / Out / best"),
            ("", "  (what does the dedust cost: split on +"),
            ("", "   reference 'best', then drag the divider)"),
            ("", "  drop a config .json on the canvas to apply it"),
            ("t", "texture histogram overlay on/off"),
            ("g", "detail filter (guided/gauss)"),
            ("r", "Backend (RAFT/DIS)"),
            ("", ""),
            ("Autoplay & recording", ""),
            ("x / y", "autoplay forward / back (again stops)"),
            ("space", "play/pause: start forward autostep, or stop"),
            ("", "  during autoplay: Up/Down and 1-9 change the"),
            ("", "  view WITHOUT stopping the run"),
            ("u", "start/stop recording"),
            ("", ""),
            ("Parameters & files", ""),
            ("d", "load defaults (all parameters)"),
            ("Double-click", "on a slider: its default "
                            "(label or slider, not the number field);"),
            ("", "  on the canvas: Fit <-> last zoom step"),
            ("e", "export cineflow.json"),
            ("p", "save current view as PNG"),
            ("c", "edit the view sequence"),
            ("h", "this help"),
            ("", ""),
            ("Slots (buttons)", "L=load  R=store  Shift+R=clear  Ctrl+R=note"),
        ]
        w = max(len(k) for k, _ in rows)
        lines = []
        for k, v in rows:
            if not k and not v:
                lines.append("")
            elif not v:
                lines.append(f"{k}")
            else:
                lines.append(f"  {k.ljust(w)}   {v}")
        from PyQt5.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setWindowTitle("Keyboard shortcuts")
        box.setTextFormat(Qt.PlainText)
        box.setText("\n".join(lines))
        box.setStyleSheet("QLabel{font-family:monospace;}")
        box.exec_()

    def _sync_mode_labels(self):
        self._refresh_cycle_combo()
        self._sync_split_labels()

    def _backend_changed(self, _idx=None):
        key = self.cb_backend.currentData() or fcore.DEFAULT_BACKEND
        self._param_changed("flow_backend", key)
        self._sync_backend_ui()
        self._sync_flow_div_range()
        self._dispatch(fcore._TIER_FLOW, f"backend={key}")

    def _sync_flow_div_range(self):
        p = self.params.get("downscale")
        if p is None:
            return
        key = str(self.cfg.get("flow_backend", fcore.DEFAULT_BACKEND))
        w = h = 0
        if self.data is not None and self.data.get("input") is not None:
            h, w = self.data["input"].shape[:2]
        lo = fcore.min_flow_div(key, w, h)
        p.set_lo(lo)
        if float(self.cfg.get("downscale", 2.0)) < lo:
            self.cfg["downscale"] = lo
            p.set_value(lo)
            self.statusBar().showMessage(
                f"downscale raised to {lo:g} \u2014 {fcore.backend_label(key)} "
                f"at {w}x{h} does not fit below that", 8000)

    def _sync_backend_ui(self):
        eff, want = fcore.resolve_backend(self.cfg, None)
        if eff != want:
            self.cb_backend.setStyleSheet("color:#e08a3a; font-weight:600;")
            need = ("PyTorch" if fcore.backend_is_gpu(want)
                    else "opencv-python")
            self.cb_backend.setToolTip(
                f"{fcore.backend_label(want)} does not run on this machine "
                f"({need} missing).\nThe preview computes "
                f"{fcore.backend_label(eff)}; the recipe still gets {want}.")
        else:
            self.cb_backend.setStyleSheet("")
            self.cb_backend.setToolTip(
                "Optical flow method. Affects the image and is part of\n"
                "the recipe:\n"
                "RAFT   torch/GPU, accurate, but invents smooth flow where\n"
                "       there is no correspondence.\n"
                "DIS    OpenCV/CPU, fast, fails loudly instead.")

    def _sync_derived_ui(self):
        if hasattr(self, "cb_filter"):
            self.cb_filter.blockSignals(True)
            self.cb_filter.setCurrentText(str(self.cfg["detail_filter"]))
            self.cb_filter.blockSignals(False)
        self._sync_mode_labels()
        self._sync_e_enabled()
        self._refresh_plot()

    def _choose_config(self):
        start = (scene_config_path(self.folder)
                 if getattr(self, "folder", None) else "")
        path, _f = QFileDialog.getOpenFileName(
            self, "Load recipe", start, "JSON (*.json);;All files (*)")
        if path:
            self._load_config_file(path)

    def _load_config_file(self, path):
        import json
        try:
            with open(path) as f:
                doc = json.load(f)
        except Exception as e:
            self.statusBar().showMessage(f"{os.path.basename(path)} "
                                         f"not readable: {e!r}", 8000)
            return
        if not isinstance(doc, dict):
            self.statusBar().showMessage(
                f"{os.path.basename(path)}: not a parameter set.", 6000)
            return

        vals = {k: v for k, v in doc.items() if not str(k).startswith("_")}
        if not vals:
            self.statusBar().showMessage(
                f"{os.path.basename(path)}: no parameters in it.", 6000)
            return
        self._apply_preset(vals, f"Config {os.path.basename(path)}")

        run = doc.get("_run") if isinstance(doc.get("_run"), dict) else None
        if run:
            origin = run.get("origin") or run.get("source") or "?"
            nr = run.get("run", "?")
            self.statusBar().showMessage(
                f"run log (run {nr}) applied \u2014 "
                f"source was: {origin}", 10000)

    def _apply_recipe(self, d, label, dispatch=True):
        unknown = []
        expert = []
        applied = 0
        for k, v in d.items():
            if k == "mode":
                continue
            if k in SCENE_PARAMS:
                self.cfg[k] = v
                applied += 1
                w = self.params.get(k)
                if w is not None:
                    w.set_value(v)
                elif k == "flow_backend":
                    self.cb_backend.blockSignals(True)
                    i = self.cb_backend.findData(str(v))
                    if i >= 0:
                        self.cb_backend.setCurrentIndex(i)
                    else:
                        unknown.append(f"flow_backend={v!r}")
                    self.cb_backend.blockSignals(False)
            elif k in fcore.DEFAULT_CONFIG:
                self.cfg[k] = v
                applied += 1
                expert.append(f"{k}={v}")
            else:
                unknown.append(str(k))
        if "mode" in d:
            m = str(d["mode"])
            i = self.cb_mode.findText(m)
            if i >= 0:
                self.cb_mode.blockSignals(True)
                self.cb_mode.setCurrentIndex(i)
                self.cb_mode.blockSignals(False)
                self.cfg["mode"] = m
                applied += 1
            else:
                unknown.append(f"mode={m!r}")
        if expert:
            fcore.log("recipe", "expert runtime override: "
                      + ", ".join(expert))
        if unknown:
            msg = f"{label}: unknown values IGNORED: {', '.join(unknown)}"
            fcore.log("recipe", msg)
            self.statusBar().showMessage(msg, 8000)
        self._sync_mode_labels()
        self._sync_backend_ui()
        self._sync_derived_ui()
        self._sync_dirty()
        if dispatch:
            self._dispatch(fcore._TIER_FLOW, label)
        return applied, unknown

    def _apply_preset(self, preset, label):
        _applied, unknown = self._apply_recipe(preset, label)
        if not unknown:
            self.statusBar().showMessage(
                f"{label}: mode={self.cfg.get('mode', '?')}, "
                f"context={preset.get('context')}, "
                f"sharp_amount={preset.get('sharp_amount')}, "
                f"full={preset.get('sharp_full')}", 6000)

    def _reset_defaults(self):
        self._apply_preset(
            {k: fcore.DEFAULT_CONFIG[k] for k in SCENE_PARAMS}, "Default")

    def _mode_changed(self, mode):
        self.cfg["mode"] = mode
        self._sync_mode_labels()

        have = (self.data is not None
                and self._mode_key(RESULT_VIEW) in self.data
                and self._mode_key("sharp_gate") in self.data)
        if self.data is None:
            pass
        elif have:
            self._redraw()
        elif "_warped_neighbors" not in self.data:
            self._dispatch(fcore._TIER_FLOW, f"mode={mode}")
        elif self._has_neighbors():
            self._dispatch(fcore._TIER_FUSION, f"mode={mode}")
        else:
            self._redraw()
            self.statusBar().showMessage(
                f"{mode} needs neighbours -- this frame has none "
                "(no committee can be formed).", 6000)

        self._sync_e_enabled()
        self._sync_dirty()

    def _has_neighbors(self):
        if not self.data:
            return False
        return bool(self.data.get("_warped_neighbors"))

    def _sync_e_enabled(self):
        e_on = float(self.cfg.get("sharp_amount", 0.0)) > 0.0
        for k in ("sharp_base", "sharp_full", "sharp_gamma", "detail_sigma"):
            w = self.params.get(k)
            if w is not None:
                w.setEnabled(e_on)
        if hasattr(self, "cb_filter"):
            self.cb_filter.setEnabled(e_on)
        w = self.params.get("detail_eps")
        if w is not None:
            guided = (getattr(self, "cb_filter", None) is not None
                      and self.cb_filter.currentText() == "guided")
            w.setEnabled(e_on and guided)
        mode_now = str(self.cfg.get("mode", "best"))
        is_dustA = mode_now == "dustA"
        is_dustB = mode_now == "dustB"
        w = self.params.get("center_weight")
        if w is not None:
            w.setEnabled(is_dustA)
        for k in ("dustA_mismatch", "dustA_softness"):
            w = self.params.get(k)
            if w is not None:
                w.setEnabled(is_dustA)
        for k in ("dustB_mismatch", "dustB_softness",
                  "dustB_disagreement", "dustB_disagreement_softness"):
            w = self.params.get(k)
            if w is not None:
                w.setEnabled(is_dustB)
        is_dust = is_dustA or is_dustB
        for k in ("photo_mismatch", "photo_softness", "photo_radius"):
            w = self.params.get(k)
            if w is not None:
                w.setEnabled(not is_dust)
        if getattr(self, "_tabsTrust", None) is not None:
            self._tabsTrust.tabBar().setTabTextColor(
                self._tab_dustA,
                QColor() if is_dustA else QColor("#7a7f87"))
            self._tabsTrust.setTabToolTip(
                self._tab_dustA,
                "Outlier curve of the group-consensus fusion.\n"
                + ("Active." if is_dustA else
                   f"Inactive -- mode is '{mode_now}'."))
            self._tabsTrust.tabBar().setTabTextColor(
                self._tab_dustB,
                QColor() if is_dustB else QColor("#7a7f87"))
            self._tabsTrust.setTabToolTip(
                self._tab_dustB,
                "Residual curve of the committee without the input frame.\n"
                + ("Active." if is_dustB else
                   f"Inactive -- mode is '{mode_now}'."))
            self._tabsTrust.tabBar().setTabTextColor(
                self._tab_pho,
                QColor("#7a7f87") if is_dust else QColor())
            self._tabsTrust.setTabToolTip(
                self._tab_pho,
                "Appearance test against the input frame.\n"
                + ("Active." if not is_dust else
                   f"Inactive -- in mode '{mode_now}' the group\n"
                   f"consensus takes over this job (ctg = gt * pgt).\n"
                   f"The 'Trust photo' map keeps responding; the\n"
                   f"RESULT does not."))

    def _goto(self, i):
        if not self.files:
            return
        i = int(np.clip(i, 0, len(self.files) - 1))
        if i == self.idx:
            return
        self.idx = i
        self.sld_frame.blockSignals(True)
        self.sld_frame.setValue(i)
        self.sld_frame.blockSignals(False)
        self._update_frame_label()
        self._dispatch(fcore._TIER_FLOW, f"Frame {i+1}")

    def _frame_slider(self, v):
        self.idx = int(v)
        self._update_frame_label()
        if self.sld_frame.isSliderDown():
            self._slider_moved = True
        else:
            self._dispatch(fcore._TIER_FLOW, f"Frame {self.idx+1}")

    def _frame_released(self):
        if not self._slider_moved:
            return
        self._slider_moved = False
        self.idx = int(self.sld_frame.value())
        self._update_frame_label()
        self._dispatch(fcore._TIER_FLOW, f"Frame {self.idx+1}")

    def _update_frame_label(self):
        self.lbl_frame.setText(f"{self.idx+1} / {len(self.files)}")
        self._update_status_state()

    def _zoom_changed(self, i, anchor=None):
        self.canvas.zoom_to(i, anchor=anchor)
        self._sync_zoom_ui()

    def _window_center(self):
        return QPoint(self.canvas.width() // 2, self.canvas.height() // 2)

    def _zoom_step(self, d, anchor=None):
        if anchor is None:
            anchor = self._window_center()
        self._zoom_changed(self.canvas.zoom_i + d, anchor=anchor)

    def _toggle_zoom(self):
        c = self.canvas
        self._zoom_changed(c._last_zoom_i if c.is_fit() else 0,
                           anchor=self._window_center())

    def _sync_zoom_ui(self):
        c = self.canvas
        if self.cb_zoom.currentIndex() != c.zoom_i:
            self.cb_zoom.blockSignals(True)
            self.cb_zoom.setCurrentIndex(c.zoom_i)
            self.cb_zoom.blockSignals(False)
        eff = c.effective_zoom()
        self.lbl_zoom.setText(f"({eff:.2f}\u00d7)" if c.is_fit() else "")
        self.canvas.update()

    def _ensure_split_ref(self):
        need = self._split_ref_key()
        if (need is not None and self.data is not None
                and need not in self.data):
            self._dispatch(fcore._TIER_FLOW, "split reference")
            return True
        return False

    def _split_changed(self, i):
        self.canvas.split_mode = i
        self.canvas.update()
        if i:
            if self._ensure_split_ref():
                return
            self._warn_if_split_impossible()

    def _warn_if_split_impossible(self):
        if self.data is None:
            return
        miss = self._split_unavailable
        if miss is not None:
            extra = ""
            if miss in ("output_dustA", "output_dustB") \
                    and not self._has_neighbors():
                extra = " (no group consensus without neighbours)"
            self.statusBar().showMessage(
                f"No split: reference \u201c{view_label(miss)}\u201d is not "
                f"computed for this state{extra}.", 6000)
        elif self._split_ref_key() is None:
            self.statusBar().showMessage(
                f"Split shows nothing: view and reference "
                f"(\u201c{self.cb_splitref.currentText()}\u201d) are the "
                f"same image \u2014 pick another reference (key k).",
                6000)

    def _redraw(self):
        if self.data is None:
            return
        key = self._current_view()
        if data_key(key) not in self.data:
            off = int(self.cfg.get("_neighbor_offset", 1))
            j = self.idx + off
            if not (0 <= j < len(self.files)):
                self.canvas.show_message(
                    f"Test neighbour In{off:+d} would be frame {j+1} \u2014 "
                    f"outside the scene (1\u2026{len(self.files)}).\n\n"
                    f"Reduce the offset, or pick another frame.")
                self.statusBar().showMessage(
                    f"neighbour In{off:+d} is outside the scene", 5000)
            else:
                self.canvas.show_message(
                    f"View \u201c{key}\u201d is not computed for this "
                    f"state.")
            return
        fn = display_fn(key, self.cfg)
        img = fn(self.data[data_key(key)])
        ref = None
        ref_key = self._split_ref_key()
        self._split_unavailable = None
        if ref_key is not None:
            ref_img = self.data.get(ref_key)
            if ref_img is not None:
                ref = display_fn(ref_key, self.cfg)(ref_img)
            else:
                self._split_unavailable = ref_key
        self._sync_split_labels()
        self.canvas.set_images(img, ref, view_key=key, clear_ref=(ref is None))
        self._update_stats()

    def _update_status_state(self):
        eff, want = fcore.resolve_backend(self.cfg, None)
        warn = (eff != want)
        shown = f"{want} \u2192 {eff} !" if warn else want

        self.busy.set_state(backend=shown, backend_warn=warn)

    def _update_stats(self):
        d = self.data or {}
        tex = d.get("texture")
        tw = d.get(self._mode_key("tex_weight"))
        tbo = d.get("trust_by_offset") or {}
        mono = "font-family:monospace; padding:3px;"

        if tw is not None:
            twm = float(np.mean(tw))
            base = self.cfg["sharp_base"]
            span = max(1e-9, 1.0 - base)
            adapt = (twm - base) / span
            pct = max(0.0, min(1.0, adapt)) * 100.0
            aktiv = adapt > 0.20
            self.st_texw.setText(f"Adaption {pct:.0f}%")
            self.st_texw.setToolTip(
                self._tip_texw
                + f"<br><br><b>Now:</b> tex_w {twm:.3f}, base {base:.2f}")
            self.st_texw.setStyleSheet(
                (f"color:#ff7a45; font-weight:bold; {mono}") if not aktiv
                else f"color:#8fb8d8; {mono}")
        else:
            self.st_texw.setText("")
            self.st_texw.setToolTip(self._tip_texw)

        if tex is not None:
            self.st_tex.setText(
                f"Tex p90 {float(np.percentile(tex,90)):.3f} "
                f"vs full {self.cfg['sharp_full']:.3f}")
        else:
            self.st_tex.setText("")

        if tbo:
            by = {}
            for o, v in tbo.items():
                by.setdefault(abs(int(o)), []).append(v)
            self.st_trust.setText(
                "Trust +-" + "  ".join(f"{a}:{np.mean(v):.2f}"
                                       for a, v in sorted(by.items())))
        else:
            self.st_trust.setText("")

        self._update_hf_stats(d)

    @staticmethod
    def _hf_energy(rgb):
        l = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2])
        return float((l - cv2.blur(l, (5, 5))).std())

    def _update_hf_stats(self, d):
        if self._cycle_entry() != RESULT_VIEW:
            self.st_hf.setText("")
            return

        mode = str(self.cfg.get("mode", "best"))
        src_img = d.get("input")
        base = d.get({"dustA": "fuse_dustA",
                      "dustB": "fuse_dustB"}.get(mode, "fuse_best"))
        out = d.get({"dustA": "output_dustA",
                     "dustB": "output_dustB"}.get(mode, "output_best"))
        if src_img is None or base is None or out is None:
            self.st_hf.setText("")
            return

        key = (id(src_img), id(base), id(out))
        if getattr(self, "_hf_cache_key", None) == key:
            self.st_hf.setText(self._hf_cache_txt)
            return

        try:
            hs = self._hf_energy(src_img)
            hb = self._hf_energy(base)
            ho = self._hf_energy(out)
        except Exception:
            self.st_hf.setText("")
            return
        txt = ("" if hs <= 0 or hb <= 0 else
               f"HF {(hb/hs-1)*100:+.0f}% / {(ho/hb-1)*100:+.0f}% "
               f"= {(ho/hs-1)*100:+.0f}%")
        self._hf_cache_key = key
        self._hf_cache_txt = txt
        self.st_hf.setText(txt)

    def _start_dir(self):
        start = self._settings.get(_DIR_KEY, "")
        if start and not os.path.isdir(start):
            start = os.path.dirname(start)
        if not start or not os.path.isdir(start):
            start = "/mnt" if os.path.isdir("/mnt") else os.path.expanduser("~")
        return start

    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(
            self, "Choose TIFF folder", self._start_dir())
        if d:
            self._load_folder(d)

    def _choose_video(self):
        pat = " ".join(f"*{e}" for e in fcore.VIDEO_EXTS)
        dlg = QFileDialog(self, "Select a video file", self._start_dir())
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        dlg.setNameFilters([f"Video ({pat})", "All files (*)"])
        dlg.setSidebarUrls(_sidebar_urls())
        if dlg.exec_() and dlg.selectedFiles():
            self._load_folder(dlg.selectedFiles()[0])

    def _load_folder(self, d):
        try:
            src = fcore.open_source(d)
        except Exception as e:
            QMessageBox.warning(self, "Cannot load", f"{d}\n\n{e}")
            return

        self._serial += 1
        self.worker.set_latest(self._serial)

        self.folder = d
        self.files = src
        if src.kind == "video":
            self._frame_size = (src.height, src.width)
        else:
            try:
                self._frame_size = src[0].shape[:2]
            except Exception:
                self._frame_size = None
        self.idx = 0
        self.data = None
        self.sld_frame.setMaximum(len(src) - 1)
        self.sld_frame.setValue(0)
        self._update_frame_label()
        tag = "Video" if src.kind == "video" else "Frames"
        self.setWindowTitle(f"flowQt {__version__} -- {os.path.basename(d)}  "
                            f"({len(src)} {tag}, {src.backend})")
        self._settings[_DIR_KEY] = d
        _save_settings(self._settings)

        p = scene_config_path(d)
        laden = False
        _nm = os.path.basename(str(d).rstrip("/\\")) or str(d)
        _hw = getattr(self, "_frame_size", None)
        _sz = f", {_hw[1]}x{_hw[0]}" if _hw else ""
        _basis = (f"{self.cfg.get('mode', 'best')}, "
                  f"{self.cfg.get('flow_backend', '?')}, "
                  f"context=+-{self.cfg.get('context', '?')}")
        _cfg_txt = ("cineflow.json found" if os.path.isfile(p)
                    else f"no cineflow.json -- using current ({_basis})")
        fcore.log("scene", f"{_nm} -- {len(self.files)} frames{_sz}, {_cfg_txt}")
        if os.path.isfile(p):
            box = QMessageBox(self)
            box.setWindowTitle("Recipe found")
            box.setText("This scene already has a saved recipe:")
            box.setInformativeText(os.path.basename(p))
            b_keep = box.addButton("Keep current recipe",
                                   QMessageBox.ActionRole)
            b_load = box.addButton("Load saved recipe", QMessageBox.ActionRole)
            box.setDefaultButton(b_keep)
            box.setEscapeButton(b_keep)
            b_keep.setDefault(True)
            b_keep.setAutoDefault(True)
            b_load.setAutoDefault(False)
            b_keep.setStyleSheet("color:#6ea8e8; font-weight:700;")
            box.show()
            box.raise_()
            box.activateWindow()
            b_keep.setFocus(Qt.OtherFocusReason)
            QTimer.singleShot(0, lambda: (box.activateWindow(),
                                          b_keep.setFocus(Qt.OtherFocusReason)))
            box.exec_()
            laden = (box.clickedButton() is b_load)
        if laden:
            try:
                import json
                with open(p) as f:
                    saved = json.load(f)
                vals = {k: v for k, v in saved.items()
                        if not str(k).startswith("_")}
                applied, _unknown = self._apply_recipe(
                    vals, "scene recipe", dispatch=False)
                fcore.log("scene",
                          f"cineflow.json applied ({applied} values)")
                self.statusBar().showMessage(
                    f"scene recipe loaded ({len(saved)} values).", 6000)
            except Exception as e:
                fcore.log("scene", f"cineflow.json not readable: {e!r}")
                QMessageBox.warning(self, "Recipe not readable",
                                    f"{p}\n\n{e!r}\n\n"
                                    "The current settings are kept.")
        elif os.path.isfile(p):
            self.statusBar().showMessage(
                "scene recipe NOT loaded -- keeping the current settings. "
                "Exporting will overwrite it.", 8000)
        if laden or not os.path.isfile(p):
            self._saved_cfg = self._recipe_dict()
        else:
            self._saved_cfg = (self._read_scene_cfg(p)
                               or self._recipe_dict())
        self._sync_dirty()
        self._sync_derived_ui()

        self._sync_diag_enabled(self._current_view())
        self._update_status_state()
        self._dispatch(fcore._TIER_FLOW, "loaded")

    def _export(self):
        if not getattr(self, "folder", None):
            return False
        return self._write_recipe(self._recipe_dict(),
                                  scene_config_path(self.folder))

    def _recipe_dict(self):
        mode = str(self.cfg.get("mode", "best"))
        cfg = {"mode": mode}
        for k in SCENE_PARAMS:
            if k != "mode" and k in self.cfg:
                cfg[k] = self.cfg[k]
        if mode != "dustA":
            cfg.pop("center_weight", None)
            for k in ("dustA_mismatch", "dustA_softness"):
                cfg.pop(k, None)
        if mode != "dustB":
            for k in ("dustB_mismatch", "dustB_softness", "dustB_disagreement",
                      "dustB_disagreement_softness"):
                cfg.pop(k, None)
        return cfg

    def _export_as(self):
        if not getattr(self, "folder", None):
            return False
        cfg = self._recipe_dict()
        start = scene_config_path(self.folder)
        path, _f = QFileDialog.getSaveFileName(
            self, "Save recipe as", start, "JSON (*.json);;All files (*)")
        if not path:
            return False
        ok = self._write_recipe(cfg, path, mark_saved=False)
        if ok:
            self.statusBar().showMessage(f"written: {path}", 6000)
        return ok

    def _write_recipe(self, cfg, path, mark_saved=True):
        try:
            _atomic_write_json(path, cfg)
        except OSError as e:
            QMessageBox.warning(self, "Export failed", f"{path}\n\n{e}")
            self.statusBar().showMessage(f"export failed: {e!r}", 8000)
            return False
        if mark_saved:
            self._saved_cfg = self._recipe_dict()
            self._sync_dirty()
            _b = (f"{cfg.get('mode', '?')}, {cfg.get('flow_backend', '?')}, "
                  f"r=\u00b1{cfg.get('context', '?')}")
            self.statusBar().showMessage(
                f"config written ({_b}) \u2014 {path}", 6000)
            fcore.log("config", f"written: {os.path.basename(path)} ({_b})")
        return True

    def closeEvent(self, ev):
        if self._dirty and getattr(self, "folder", None):
            r = QMessageBox.question(
                self, "Unsaved changes",
                "The parameters were changed but not written to the "
                "cineflow.json.\n\nSave now?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save)
            if r == QMessageBox.Cancel:
                ev.ignore()
                return
            if r == QMessageBox.Save:
                if not self._export():
                    ev.ignore()
                    return

        self.ar.close()

        self._serial += 1
        self.worker.set_latest(self._serial)
        self.thread.quit()
        if not self.thread.wait(15000):
            self.thread.terminate()
            self.thread.wait(1000)

        src = getattr(self, "files", None)
        if src is not None and hasattr(src, "close"):
            try:
                src.close()
            except Exception:
                pass
        ev.accept()

def _apply_dark(app):
    app.setStyle("Fusion")
    p = QPalette()
    bg     = QColor(30, 30, 32)
    base   = QColor(22, 22, 24)
    alt    = QColor(38, 38, 41)
    text   = QColor(210, 210, 214)
    dim    = QColor(130, 130, 136)
    accent = QColor(78, 132, 190)
    p.setColor(QPalette.Window,          bg)
    p.setColor(QPalette.WindowText,      text)
    p.setColor(QPalette.Base,            base)
    p.setColor(QPalette.AlternateBase,   alt)
    p.setColor(QPalette.Text,            text)
    p.setColor(QPalette.Button,          QColor(33, 34, 38))
    p.setColor(QPalette.ButtonText,      text)
    p.setColor(QPalette.ToolTipBase,     base)
    p.setColor(QPalette.ToolTipText,     text)
    p.setColor(QPalette.Highlight,       accent)
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Disabled, QPalette.Text,       dim)
    p.setColor(QPalette.Disabled, QPalette.ButtonText, dim)
    p.setColor(QPalette.Disabled, QPalette.WindowText, dim)
    app.setPalette(p)

    app.setStyleSheet("""
        QDialog       { background: #1e1e20; }
        QFileDialog   { background: #1e1e20; }
        QListView, QTreeView, QTableView {
                        background: #161618; alternate-background-color: #1c1c1f;
                        border: 1px solid #3a3a3e; }
        QListView::item:selected, QTreeView::item:selected {
                        background: #4e84be; }
        /* Drop-down list of a combo -- the SELECTED entry must stand
           out.
           Without these rules Qt paints it in a grey that matches the
           rest of the interface, while the unselected entries sit on the
           darker base: the contrast then reads the wrong way round, and
           the dark-backed entry looks like the highlighted one.
           With only two entries -- mode best/dust -- that is especially
           misleading.
           It MUST go through the stylesheet: with an app stylesheet set,
           QStyleSheetStyle is active, and that ignores the palette. */
        QComboBox QAbstractItemView {
                        background: #161618;
                        border: 1px solid #3a3a3e;
                        outline: none;
                        selection-background-color: #4e84be;
                        selection-color: #ffffff; }
        QComboBox QAbstractItemView::item {
                        padding: 3px 6px; color: #d2d2d6;
                        background: #161618; }
        QComboBox QAbstractItemView::item:selected,
        QComboBox QAbstractItemView::item:hover {
                        background: #4e84be; color: #ffffff; }
        QHeaderView::section {
                        background: #2a2b30; color: #b8bcc2;
                        border: 1px solid #3a3a3e; padding: 3px; }
        QLineEdit     { background: #212226; border: 1px solid #3a3a3e;
                        border-radius: 3px; padding: 3px; }
        QScrollBar:vertical, QScrollBar:horizontal {
                        background: #202124; border: none; }
        QScrollBar::handle {
                        background: #45464d; border-radius: 4px; }
        QScrollBar::handle:hover { background: #56575f; }
        QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
        QSplitter::handle { background: #2c2d31; }
        QMenu         { background: #26272b; border: 1px solid #45464d; }
        QMenu::item:selected { background: #4e84be; }
        QGroupBox     { border: 1px solid #3a3a3e; border-radius: 4px;
                        margin-top: 10px; padding-top: 8px; color: #9aa0a6; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QPushButton   { background: #33343a; border: 1px solid #45464d;
                        border-radius: 3px; padding: 4px 10px; }
        QPushButton:hover   { background: #3d3f47; }
        QPushButton:pressed { background: #2a2b30; }
        /* NOTE -- QComboBox is DELIBERATELY absent here.
           "QComboBox { background: ... }" colours not only the collapsed
           field but is inherited by the DROP-DOWN LIST, where it paints
           over the selected entry. That entry then got exactly the grey
           of the rest of the interface, while the unselected entries
           stayed darker -- the contrast read the wrong way round.
           No ::item rule, however specific, wins against that; verified
           on the rendered list.
           The collapsed field therefore gets its background through the
           PALETTE (QPalette.Button, see above), which is not inherited. */
        /* VERTICAL padding kept tight (1px): the line height of the
           controls hangs on this field alone -- font height + padding +
           border. With three to four controls per tab, every pixel counts
           three times over. HORIZONTAL stays at 4, otherwise the
           digits stick to the frame. */
        QSpinBox, QDoubleSpinBox {
                        background: #212226; border: 1px solid #3a3a3e;
                        border-radius: 3px; padding: 1px 4px; }
        QComboBox     { border: 1px solid #3a3a3e;
                        border-radius: 3px; padding: 2px 4px; }
        QSlider::groove:horizontal {
                        height: 4px; background: #2c2d31; border-radius: 2px; }
        QSlider::handle:horizontal {
                        background: #8a8f98; width: 12px; margin: -5px 0;
                        border-radius: 6px; }
        QSlider::handle:horizontal:hover { background: #a8aeb8; }
        QStatusBar    { color: #9aa0a6; }
        QToolTip      { background: #26272b; color: #d2d2d6;
                        border: 1px solid #45464d; padding: 4px; }
    """)

def _setup_hidpi():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

def _scale_font(app):
    scr = app.primaryScreen()
    if scr is None:
        return
    h = scr.geometry().height()
    pt = 12 if h >= 2000 else (10 if h >= 1400 else 9)
    f = app.font()
    f.setPointSize(pt)
    app.setFont(f)

def _startup_banner():
    have = fcore.backends_available()

    try:
        env = f"Python {sys.version.split()[0]}, numpy {np.__version__}, " \
              f"OpenCV {cv2.__version__}"
    except Exception:
        env = f"Python {sys.version.split()[0]}"
    fcore.log("flowQt", f"{__version__}  --  {env}")

    miss = [k for k in fcore.ALL_BACKENDS if k not in have]
    line = "flow: " + ", ".join(fcore.backend_label(k) for k in have)
    if miss:
        line += ("  (unavailable: "
                 + ", ".join(fcore.backend_label(k) for k in miss) + ")")
    fcore.log("flowQt", line)
    fcore.log("flowQt", f"settings: {_SETTINGS}")

def main():
    _startup_banner()

    folder = sys.argv[1] if len(sys.argv) > 1 else None
    if folder and not (os.path.isdir(folder) or fcore.is_video(folder)):
        sys.exit(f"[flowQt] neither a directory nor a video file: {folder}")

    _setup_hidpi()

    app = QApplication(sys.argv)
    _scale_font(app)
    _apply_dark(app)
    if app.platformName() in ("", "minimal"):
        print("\n[flowQt] Qt could not open a display.", file=sys.stderr)
        print("  Under WSL2 system libraries are usually missing:", file=sys.stderr)
        print("    sudo apt install libxcb-cursor0 libxcb-xinerama0 "
              "libxkbcommon-x11-0\n", file=sys.stderr)

    w = Main(folder)
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
