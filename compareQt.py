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


import json
import os
import sys
import time

import cv2
import numpy as np

try:
    from PyQt5.QtCore import Qt, QTimer, QPoint
    from PyQt5.QtGui import QImage, QPixmap, QPainter, QPalette, QColor
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QRadioButton, QButtonGroup,
        QSpinBox, QComboBox, QSlider, QFileDialog, QGroupBox, QCheckBox,
        QSizePolicy, QMessageBox, QProgressBar)
except ImportError:
    sys.exit("\ncompareQt: PyQt5 is not installed.\n         pip install PyQt5\n")

import flowcore as fcore
import cineio

VERSION = "0.1"
DIFF_SCALER = 6
LABEL_COLOR = (255, 255, 0)
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "compareQt_settings.json")
LAYOUTS = (("a",      "A only          (Up)"),
           ("b",      "B only          (Down)"),
           ("split",  "A | B  vertical split"),
           ("hsplit", "A / B  horizontal split"),
           ("side",   "A \u00b7 B  side by side"),
           ("diff",   "A | B  + diff"))
HEIGHTS = (("orig", "original height"), ("1080", "1080 px"), ("720", "720 px"))
CODECS = (("avi", "AVI  \u00b7  MJPG"),
          ("mp4", "MP4  \u00b7  MPEG-4"),
          ("png", "PNG image sequence"))

def to_u8(img):
    return np.clip(img * 255.0 + 0.5, 0, 255).astype(np.uint8)

def put_label(img, text, x=20, y=None):
    if not text:
        return img
    h = img.shape[0]
    scale = max(0.6, h / 900.0)
    y = y or int(28 * scale + 12)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                LABEL_COLOR, max(1, int(2 * scale)), cv2.LINE_AA)
    return img

def compose(layout, a, b, title_a, title_b, scaler=DIFF_SCALER):
    h, w = a.shape[:2]
    if b is None:
        b = np.full_like(a, 96)
    if layout == "a":
        return put_label(a.copy(), title_a or "A")
    if layout == "b":
        return put_label(b.copy(), title_b or "B")
    if layout == "hsplit":
        mid = h // 2
        img = np.vstack((a[:mid], b[mid:]))
        img[mid - 1:mid + 1, :] = LABEL_COLOR
        put_label(img, title_a)
        return put_label(img, title_b, y=mid + int(28 * max(0.6, h / 900.0) + 12))
    if layout == "side":
        img = np.hstack((a, b))
        put_label(img, title_a)
        return put_label(img, title_b, x=w + 20)
    mid = w // 2
    split = np.hstack((a[:, :mid], b[:, mid:]))
    split[:, mid - 1:mid + 1] = LABEL_COLOR
    put_label(split, title_a)
    put_label(split, title_b, x=mid + 20)
    if layout == "split":
        return split
    diff = 128 + int(scaler) * (a.astype(np.int16) - b.astype(np.int16))
    diff = np.clip(diff, 0, 255).astype(np.uint8)
    put_label(diff, f"A - B  x{int(scaler)}")
    return np.hstack((split, diff))

def fit_height(img, height):
    if not height or img.shape[0] == height:
        return img
    w = int(round(img.shape[1] * height / img.shape[0]))
    return cv2.resize(img, (w, height), interpolation=cv2.INTER_AREA)

def even(img):
    h, w = img.shape[:2]
    return img[:h - h % 2, :w - w % 2]

class VideoOut:

    verified = None

    FOURCC = {"mp4": ("mp4v", ".mp4"), "avi": ("MJPG", ".avi")}

    def __init__(self, path, w, h, fps, status=print, kind="avi"):
        cc, ext = self.FOURCC.get(kind, self.FOURCC["avi"])
        self.cc = cc
        self.path = os.path.normpath(os.path.splitext(path)[0] + ext)
        self.n, self.size = 0, (w, h)
        self.cv = cv2.VideoWriter(self.path, cv2.VideoWriter_fourcc(*cc),
                                  round(float(fps or 18.0), 3) or 18.0, (w, h))
        if not self.cv.isOpened():
            raise RuntimeError("cv2.VideoWriter could not open the file "
                               "(codec, path or drive?)")
        self.how = f"cv2 {cc}"

    def write(self, rgb):
        if (rgb.shape[1], rgb.shape[0]) != self.size:
            rgb = cv2.resize(rgb, self.size, interpolation=cv2.INTER_AREA)
        bgr = np.ascontiguousarray(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        self.cv.write(bgr)
        self.n += 1

    def close(self):
        if self.cv is None:
            return
        self.cv.release()
        self.cv = None
        if not self.n:
            return
        cap = cv2.VideoCapture(self.path)
        ok = cap.isOpened()
        got = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) if ok else 0
        ok = ok and cap.read()[0]
        cap.release()
        if not ok:
            raise RuntimeError(
                f"the file was written ({self.n} frames) but cannot be read "
                f"back -- no video track. Try the PNG sequence instead.")
        self.verified = got

class SeqOut:

    def __init__(self, path, w, h, fps, status=print):
        self.dir = self.path = os.path.normpath(
            os.path.splitext(path)[0] + "_frames")
        os.makedirs(self.dir, exist_ok=True)
        self.out = os.path.splitext(path)[0] + ".mp4"
        self.fps, self.n = float(fps or 18.0), 0
        self.how = "PNG sequence"

    def write(self, rgb):
        cv2.imwrite(os.path.join(self.dir, f"frame_{self.n:06d}.png"),
                    cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        self.n += 1

    def cmd(self):
        return (f'ffmpeg -framerate {self.fps:g} -i "{os.path.join(self.dir, "frame_%06d.png")}" '
                f'-c:v libx264 -crf 15 -preset slow -pix_fmt yuv420p '
                f'-color_range tv -colorspace bt709 -color_primaries bt709 '
                f'-color_trc bt709 -movflags +faststart -y "{self.out}"')

    def close(self):
        if self.n:
            print("\nEncode the sequence with:\n  " + self.cmd() + "\n")

class Source:

    def __init__(self, path):
        self.path = path
        self.src = fcore.open_source(path)
        if not self.src:
            raise ValueError(f"no frames in {path}")
        self.n = len(self.src)
        self.fps = float(getattr(self.src, "fps", 0) or 18.0)
        self.record = self._read_record()
        h, w = self.src[0].shape[:2]
        self.size = (w, h)

    def _read_record(self):
        p = cineio.record_path(self.path)
        if not os.path.isfile(p):
            return None
        try:
            with open(p) as fh:
                return json.load(fh)
        except Exception:
            return None

    @property
    def frame_start(self):
        r = (self.record or {}).get("_run", {})
        fr = r.get("frame_range")
        return int(fr[0]) if fr else 0

    @property
    def name(self):
        p = self.path.rstrip("\\/")
        return os.path.basename(p) if os.path.isdir(p) \
            else os.path.splitext(os.path.basename(p))[0]

    def frame(self, i, size=None):
        if i < 0 or i >= self.n:
            return None
        img = to_u8(self.src[i])
        if size is not None and (img.shape[1], img.shape[0]) != size:
            img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
        return img

    def close(self):
        try:
            self.src.close()
        except Exception:
            pass

class Canvas(QWidget):
    ZOOMS = (0.0, 1.0, 2.0, 4.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._img = None
        self._qimg = None
        self.zoom_i = 0
        self.pan = QPoint(0, 0)
        self._drag = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_image(self, rgb):
        self._img = rgb
        if rgb is None:
            self._qimg = None
        else:
            h, w = rgb.shape[:2]
            buf = np.ascontiguousarray(rgb)
            self._qimg = QImage(buf.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        self.update()

    def scale(self):
        if self._qimg is None:
            return 1.0
        z = self.ZOOMS[self.zoom_i]
        if z > 0:
            return z
        return min(self.width() / self._qimg.width(),
                   self.height() / self._qimg.height())

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        if self._qimg is None:
            p.setPen(Qt.gray)
            p.drawText(self.rect(), Qt.AlignCenter,
                       "drop two sources above -- a folder of TIFFs or a video file")
            return
        s = self.scale()
        w, h = int(self._qimg.width() * s), int(self._qimg.height() * s)
        x = (self.width() - w) // 2 + (self.pan.x() if self.zoom_i else 0)
        y = (self.height() - h) // 2 + (self.pan.y() if self.zoom_i else 0)
        p.setRenderHint(QPainter.SmoothPixmapTransform, s < 1.0)
        p.drawPixmap(x, y, w, h, QPixmap.fromImage(self._qimg))

    def wheelEvent(self, ev):
        d = 1 if ev.angleDelta().y() > 0 else -1
        self.zoom_i = max(0, min(len(self.ZOOMS) - 1, self.zoom_i + d))
        if self.zoom_i == 0:
            self.pan = QPoint(0, 0)
        self.update()

    def mousePressEvent(self, ev):
        self.setFocus()
        if ev.button() == Qt.LeftButton:
            self._drag = ev.pos() - self.pan

    def mouseMoveEvent(self, ev):
        if self._drag is not None and self.zoom_i:
            self.pan = ev.pos() - self._drag
            self.update()

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def mouseDoubleClickEvent(self, ev):
        self.zoom_i = 1 if self.zoom_i == 0 else 0
        self.pan = QPoint(0, 0)
        self.update()

class DropBox(QGroupBox):
    def __init__(self, letter, on_path, parent=None):
        super().__init__(f"Source {letter}", parent)
        self.on_path = on_path
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.path_lbl = QLabel("drop a TIFF folder or a video file here")
        self.path_lbl.setStyleSheet("color: gray")
        self.path_lbl.setWordWrap(True)
        row.addWidget(self.path_lbl, 1)
        b = QPushButton("\u2026")
        b.setFixedWidth(28)
        b.setToolTip("browse")
        b.clicked.connect(self._browse)
        row.addWidget(b)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("title"))
        self.title = QLineEdit()
        row2.addWidget(self.title, 1)
        lay.addLayout(row2)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for url in ev.mimeData().urls():
            p = url.toLocalFile()
            if p:
                self.on_path(p)
                break

    def _browse(self):
        p, _f = QFileDialog.getOpenFileName(
            self, "Video file (for a TIFF folder, drop it or pick any file in it)",
            "", "Video or TIFF (*.mp4 *.mov *.mkv *.avi *.tif *.tiff);;All files (*)")
        if not p:
            return
        if p.lower().endswith((".tif", ".tiff")):
            p = os.path.dirname(p)
        self.on_path(p)

    def set_path(self, p):
        self.path_lbl.setText(p)
        self.path_lbl.setStyleSheet("")

class Main(QMainWindow):
    NAV_STEP = {Qt.NoModifier: 1, Qt.ShiftModifier: 10, Qt.ControlModifier: 100}

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"compareQt {VERSION}")
        self.a = None
        self.b = None
        self.idx = 0
        self._cancel = False
        self._rendering = False
        self.settings = self._load_settings()
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._apply_settings()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)

        self.canvas = Canvas()

        top = QHBoxLayout()
        self.box_a = DropBox("A", lambda p: self._load("a", p))
        self.box_b = DropBox("B", lambda p: self._load("b", p))
        for box in (self.box_a, self.box_b):
            box.title.textChanged.connect(self._redraw)
            box.title.returnPressed.connect(self.canvas.setFocus)
            box.title.setToolTip("Enter hands the keyboard back to the picture.")
        top.addWidget(self.box_a, 1)
        top.addWidget(self.box_b, 1)
        v.addLayout(top)

        mid = QHBoxLayout()
        mid.addWidget(self.canvas, 1)

        side = QVBoxLayout()
        g = QGroupBox("Layout")
        gl = QVBoxLayout(g)
        self.layout_group = QButtonGroup(self)
        for i, (key, label) in enumerate(LAYOUTS):
            rb = QRadioButton(label)
            rb.setProperty("key", key)
            self.layout_group.addButton(rb, i)
            gl.addWidget(rb)
        self.layout_group.buttons()[2].setChecked(True)
        self.layout_group.buttonClicked.connect(lambda _b: self._redraw())
        self.cb_swap = QCheckBox("swap A and B")
        self.cb_swap.setToolTip("Put B on the left (or on top). Swapped before "
                                "the halves are cut, so a split stays a split.")
        self.cb_swap.toggled.connect(self._redraw)
        gl.addWidget(self.cb_swap)
        side.addWidget(g)

        g = QGroupBox("Difference")
        gl = QHBoxLayout(g)
        gl.addWidget(QLabel("amplify \u00d7"))
        self.diff_scaler = QSpinBox()
        self.diff_scaler.setRange(1, 40)
        self.diff_scaler.setValue(DIFF_SCALER)
        self.diff_scaler.setToolTip("How much the A-B difference is amplified "
                                    "around mid grey. 6 is noiseDiff's value.")
        self.diff_scaler.valueChanged.connect(self._redraw)
        gl.addWidget(self.diff_scaler, 1)
        side.addWidget(g)

        g = QGroupBox("Offset B")
        gl = QHBoxLayout(g)
        self.offset = QSpinBox()
        self.offset.setRange(-100000, 100000)
        self.offset.setToolTip("B frame = A frame + offset.\n"
                               "Proposed from the run log beside B, if there is one.")
        self.offset.valueChanged.connect(self._offset_changed)
        gl.addWidget(self.offset)
        self.offset_note = QLabel("")
        self.offset_note.setStyleSheet("color: #8a9099")
        gl.addWidget(self.offset_note, 1)
        side.addWidget(g)

        g = QGroupBox("Output folder")
        gl = QHBoxLayout(g)
        self.out_dir = QLineEdit()
        self.out_dir.setPlaceholderText("next to source A")
        self.out_dir.setToolTip("Where snapshots (p) and rendered videos go.\n"
                                "Empty: a _snapshots folder next to source A, "
                                "and the render dialog starts beside A.")
        self.out_dir.returnPressed.connect(self.canvas.setFocus)
        gl.addWidget(self.out_dir, 1)
        b = QPushButton("\u2026")
        b.setFixedWidth(28)
        b.clicked.connect(self._browse_out)
        gl.addWidget(b)
        side.addWidget(g)

        g = QGroupBox("Export")
        gl = QVBoxLayout(g)
        self.cb_codec = QComboBox()
        for key, label in CODECS:
            self.cb_codec.addItem(label, key)
        gl.addWidget(self.cb_codec)
        self.cb_height = QComboBox()
        for key, label in HEIGHTS:
            self.cb_height.addItem(label, key)
        self.cb_height.setToolTip("Original keeps the grain; a smaller height "
                                  "averages fine residual grain away, and the "
                                  "difference shows less.")
        self.cb_codec.setToolTip(
            "AVI / MJPG          every frame a JPEG, ~95 %\n"
            "MP4 / MPEG-4     inter-frame, smaller files\n"
            "PNG sequence   lossless, plus an ffmpeg line on the console")
        gl.addWidget(self.cb_height)
        self.btn_render = QPushButton("Render \u2026")
        self.btn_render.clicked.connect(self._render_or_cancel)
        gl.addWidget(self.btn_render)
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v / %m")
        self.progress.hide()
        gl.addWidget(self.progress)
        side.addWidget(g)
        side.addStretch(1)
        w = QWidget()
        w.setLayout(side)
        w.setFixedWidth(270)
        mid.addWidget(w)
        v.addLayout(mid, 1)

        nav = QHBoxLayout()
        b = QPushButton("<")
        b.setFixedWidth(30)
        b.clicked.connect(lambda: self._goto(self.idx - 1))
        nav.addWidget(b)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self._goto)
        nav.addWidget(self.slider, 1)
        b = QPushButton(">")
        b.setFixedWidth(30)
        b.clicked.connect(lambda: self._goto(self.idx + 1))
        nav.addWidget(b)
        self.lbl_frame = QLabel("0 / 0")
        self.lbl_frame.setMinimumWidth(90)
        nav.addWidget(self.lbl_frame)
        self.btn_play = QPushButton("play")
        self.btn_play.setFixedWidth(50)
        self.btn_play.clicked.connect(self._play_pause)
        nav.addWidget(self.btn_play)
        self.cb_loop = QCheckBox("loop")
        self.cb_loop.setToolTip("Play the overlap of A and B round and round.")
        nav.addWidget(self.cb_loop)
        v.addLayout(nav)

        hint = QLabel("\u2190/\u2192 frame \u00b7 Shift \u00b110 \u00b7 Ctrl \u00b1100 "
                      "\u00b7 Home/End \u00b7 Up/Down: A / B \u00b7 space: play "
                      "\u00b7 p: snapshot \u00b7 wheel: zoom \u00b7 double-click: fit / 1x "
                      "\u00b7 Esc: cancel render")
        hint.setStyleSheet("color: #8a9099")
        v.addWidget(hint)
        self.status = self.statusBar()

        for wdg in root.findChildren((QPushButton, QComboBox, QRadioButton,
                                      QCheckBox, QSlider)):
            wdg.setFocusPolicy(Qt.NoFocus)
        for sb in (self.offset, self.diff_scaler):
            sb.setFocusPolicy(Qt.ClickFocus)
        self.canvas.setFocus()

    def keyPressEvent(self, ev):
        k = ev.key()
        if k == Qt.Key_Escape and self._rendering:
            self._cancel = True
            return
        if k in (Qt.Key_Left, Qt.Key_Right):
            mods = ev.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)
            step = self.NAV_STEP.get(mods, 1)
            self._goto(self.idx + (step if k == Qt.Key_Right else -step))
        elif k == Qt.Key_Home:
            self._goto(self._range()[0])
        elif k == Qt.Key_End:
            self._goto(self._range()[1])
        elif k == Qt.Key_PageUp:
            self._goto(self.idx - 10)
        elif k == Qt.Key_PageDown:
            self._goto(self.idx + 10)
        elif k == Qt.Key_Space:
            self._play_pause()
        elif k == Qt.Key_Up:
            self._set_layout("a")
        elif k == Qt.Key_Down:
            self._set_layout("b")
        elif k == Qt.Key_P:
            self._snapshot()
        else:
            super().keyPressEvent(ev)

    def _snapshot(self):
        img = self._composed(self.idx)
        if img is None:
            return
        d = self._out_folder("_snapshots")
        os.makedirs(d, exist_ok=True)
        j = self.idx + self.offset.value()
        stem = f"cmp_{self._layout()}_A{self.idx + 1:06d}_B{j + 1:06d}"
        path = os.path.join(d, stem + ".png")
        k = 1
        while os.path.exists(path):
            path = os.path.join(d, f"{stem}_{k}.png")
            k += 1
        cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        self.status.showMessage(f"snapshot -> {path}")

    def _load(self, which, path):
        try:
            src = Source(path)
        except Exception as e:
            QMessageBox.warning(self, "compareQt", f"Cannot open {path}:\n{e}")
            return
        old = getattr(self, which)
        if old is not None:
            old.close()
        setattr(self, which, src)
        box = self.box_a if which == "a" else self.box_b
        box.set_path(path)
        if not box.title.text():
            box.title.setText(src.name)
        self.settings[f"path_{which}"] = path
        self._propose_offset()
        self._sync_range()
        self._redraw()

    def _propose_offset(self):
        if self.a is None or self.b is None:
            return
        if self.b.record is None and self.a.record is None:
            self.offset_note.setText("")
            return
        off = self.a.frame_start - self.b.frame_start
        self.offset.blockSignals(True)
        self.offset.setValue(off)
        self.offset.blockSignals(False)
        self.offset_note.setText("from run log")

    def _range(self):
        if self.a is None:
            return 0, 0
        lo, hi = 0, self.a.n - 1
        if self.b is not None:
            off = self.offset.value()
            lo, hi = max(lo, -off), min(hi, self.b.n - 1 - off)
        if hi < lo:
            return 0, self.a.n - 1
        return lo, hi

    def _has_overlap(self):
        if self.a is None or self.b is None:
            return False
        off = self.offset.value()
        return max(0, -off) <= min(self.a.n - 1, self.b.n - 1 - off)

    def _offset_changed(self, *_):
        self.offset_note.setText("")
        self._sync_range()
        self._redraw()

    def _sync_range(self):
        lo, hi = self._range()
        self.slider.blockSignals(True)
        self.slider.setRange(lo, hi)
        self.idx = max(lo, min(hi, self.idx))
        self.slider.setValue(self.idx)
        self.slider.blockSignals(False)
        title = f"compareQt {VERSION}"
        if self.a:
            title += f" -- {self.a.name}"
            if self.b:
                title += f" vs {self.b.name}"
            title += f"  ({self.a.n} frames, {self.a.size[0]}x{self.a.size[1]})"
        self.setWindowTitle(title)

    def _layout(self):
        return self.layout_group.checkedButton().property("key")

    def _set_layout(self, key):
        for rb in self.layout_group.buttons():
            if rb.property("key") == key:
                rb.setChecked(True)
        self._redraw()

    def _frames(self, i):
        if self.a is None:
            return None, None
        a = self.a.frame(i)
        b = self.b.frame(i + self.offset.value(), size=self.a.size) \
            if self.b is not None else None
        return a, b

    def _composed(self, i):
        a, b = self._frames(i)
        if a is None:
            return None
        ta, tb = self.box_a.title.text(), self.box_b.title.text()
        if self.cb_swap.isChecked():
            if b is not None:
                a, b = b, a
                ta, tb = tb, ta
        return compose(self._layout(), a, b, ta, tb, self.diff_scaler.value())

    def _redraw(self, *_):
        self.canvas.set_image(self._composed(self.idx))
        n = self.a.n if self.a else 0
        self.lbl_frame.setText(f"{self.idx + 1} / {n}")
        msg = f"A {self.idx + 1}"
        if self.b:
            j = self.idx + self.offset.value()
            msg += f"  \u00b7  B {j + 1}" + ("" if 0 <= j < self.b.n else " (out of range)")
            if self._has_overlap():
                lo, hi = self._range()
                msg += f"  \u00b7  overlap A {lo + 1}\u2013{hi + 1} ({hi - lo + 1} frames)"
            else:
                msg += "  \u00b7  no overlap at this offset"
        self.status.showMessage(msg)

    def _goto(self, i):
        lo, hi = self._range()
        i = max(lo, min(hi, i)) if self.a else 0
        if i == self.idx and self.slider.value() == i:
            return
        self.idx = i
        self.slider.blockSignals(True)
        self.slider.setValue(i)
        self.slider.blockSignals(False)
        self._redraw()

    def _play_pause(self):
        if self._timer.isActive():
            self._timer.stop()
            self.btn_play.setText("play")
        elif self.a is not None:
            self._timer.start(int(1000 / self.a.fps))
            self.btn_play.setText("stop")

    def _tick(self):
        lo, hi = self._range()
        if self.idx >= hi:
            if self.cb_loop.isChecked():
                self._goto(lo)
            else:
                self._play_pause()
            return
        self._goto(self.idx + 1)

    def _browse_out(self):
        p = QFileDialog.getExistingDirectory(self, "Output folder",
                                             self.out_dir.text() or "")
        if p:
            self.out_dir.setText(p)
        self.canvas.setFocus()

    def _out_folder(self, sub=None):
        d = self.out_dir.text().strip()
        if d and os.path.isdir(d):
            return os.path.join(d, sub) if sub else d
        base = self.a.path.rstrip("\\/")
        base = base if os.path.isdir(base) else os.path.dirname(base)
        return os.path.join(base, sub) if sub else base

    def _render_or_cancel(self):
        if self._rendering:
            self._cancel = True
        else:
            self._render()

    def _render(self):
        if self.a is None or self.b is None:
            QMessageBox.information(self, "compareQt", "Two sources are needed.")
            return
        if self._timer.isActive():
            self._play_pause()
        codec = self.cb_codec.currentData()
        height_key = self.cb_height.currentData()
        ext, flt, what = {
            "avi": (".avi", "AVI video (*.avi)", "Render to"),
            "mp4": (".mp4", "MP4 video (*.mp4)", "Render to"),
            "png": ("", "All files (*)", "Render to (a _frames folder is "
                                         "created beside this name)"),
        }[codec]
        start = os.path.join(self._out_folder(), f"{self.a.name}_compare{ext}")
        out, _f = QFileDialog.getSaveFileName(self, what, start, flt)
        if not out:
            return
        if ext and not out.lower().endswith(ext):
            out += ext
        self.settings["last_output"] = out
        self._save_settings()
        height = None if height_key == "orig" else int(height_key)

        lo, hi = self._range()
        n = hi - lo + 1
        first = even(fit_height(self._composed(lo), height))
        h, w = first.shape[:2]
        try:
            if codec == "png":
                writer = SeqOut(out, w, h, self.a.fps,
                                status=self.status.showMessage)
            else:
                writer = VideoOut(out, w, h, self.a.fps,
                                  status=self.status.showMessage, kind=codec)
            out = writer.path
        except Exception as e:
            QMessageBox.warning(self, "compareQt", f"Cannot open {out}:\n{e}")
            return

        self._rendering, self._cancel = True, False
        self.btn_render.setText("Cancel  (Esc)")
        self.progress.setRange(0, n)
        self.progress.setValue(0)
        self.progress.show()
        t0 = time.time()
        err = None
        try:
            for i in range(lo, hi + 1):
                if self._cancel:
                    break
                img = first if i == lo else even(fit_height(self._composed(i), height))
                writer.write(img)
                if writer.n % 3 == 0 or i == hi:
                    self.idx = i
                    self.slider.blockSignals(True)
                    self.slider.setValue(i)
                    self.slider.blockSignals(False)
                    self.canvas.set_image(img)
                    self.lbl_frame.setText(f"{i + 1} / {self.a.n}")
                    self.progress.setValue(writer.n)
                    self.status.showMessage(
                        f"rendering {writer.n}/{n} \u2026  ({writer.how})")
                    QApplication.processEvents()
        except Exception as e:
            err = e
        finally:
            try:
                writer.close()
            except Exception as e:
                err = err or e
            self._rendering = False
            self.btn_render.setText("Render \u2026")
            self.progress.hide()
        dt = time.time() - t0
        if err is not None:
            self.status.showMessage(f"render failed after {writer.n} frames: {err}")
        elif self._cancel:
            self.status.showMessage(f"cancelled -- {writer.n} of {n} frames written, "
                                    f"closed properly ({writer.how})")
        elif isinstance(writer, SeqOut):
            self.status.showMessage(f"{writer.n} frames -> {writer.dir}  "
                                    f"-- ffmpeg line printed on the console")
        else:
            ver = f", read back: {writer.verified} frames" \
                if getattr(writer, "verified", None) else ""
            self.status.showMessage(f"done -> {out}  ({writer.n} frames, {dt:.1f}s, "
                                    f"{writer.how}{ver})")

    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _save_settings(self):
        s = self.settings
        s["title_a"] = self.box_a.title.text()
        s["title_b"] = self.box_b.title.text()
        s["layout"] = self._layout()
        s["offset"] = self.offset.value()
        s["codec"] = self.cb_codec.currentData()
        s["height"] = self.cb_height.currentData()
        s["out_dir"] = self.out_dir.text().strip()
        s["swap"] = self.cb_swap.isChecked()
        s["diff_scaler"] = self.diff_scaler.value()
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
                json.dump(s, fh, indent=2)
        except Exception:
            pass

    def _apply_settings(self):
        s = self.settings
        for i, (key, _l) in enumerate(LAYOUTS):
            if key == s.get("layout"):
                self.layout_group.buttons()[i].setChecked(True)
        for cb, key in ((self.cb_codec, "codec"), (self.cb_height, "height")):
            j = cb.findData(s.get(key))
            if j >= 0:
                cb.setCurrentIndex(j)
        self.box_a.title.setText(s.get("title_a", ""))
        self.box_b.title.setText(s.get("title_b", ""))
        self.out_dir.setText(s.get("out_dir", ""))
        self.cb_swap.setChecked(bool(s.get("swap", False)))
        self.diff_scaler.setValue(int(s.get("diff_scaler", DIFF_SCALER)))
        for which in ("a", "b"):
            p = s.get(f"path_{which}")
            if p and os.path.exists(p):
                self._load(which, p)
        if "offset" in s and not self.offset_note.text():
            self.offset.setValue(int(s["offset"]))

    def closeEvent(self, ev):
        self._cancel = True
        self._save_settings()
        for src in (self.a, self.b):
            if src is not None:
                src.close()
        super().closeEvent(ev)

def _apply_dark(app):
    app.setStyle("Fusion")
    p = QPalette()
    bg, base, alt = QColor(30, 30, 32), QColor(22, 22, 24), QColor(38, 38, 41)
    text, dim, accent = QColor(210, 210, 214), QColor(130, 130, 136), QColor(78, 132, 190)
    p.setColor(QPalette.Window, bg)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, alt)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, QColor(33, 34, 38))
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Highlight, accent)
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        p.setColor(QPalette.Disabled, role, dim)
    app.setPalette(p)
    app.setStyleSheet("""
        QDialog, QFileDialog { background: #1e1e20; }
        QListView, QTreeView, QTableView {
            background: #161618; alternate-background-color: #1c1c1f;
            border: 1px solid #3a3a3e; }
        QListView::item:selected, QTreeView::item:selected { background: #4e84be; }
        QGroupBox { border: 1px solid #3a3a3e; border-radius: 4px; margin-top: 8px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; color: #8a9099; }
        /* Fusion malt Kaestchen und Radiopunkte im Fensterhintergrund --
           auf dunklem Grund bleibt nur der Haken. Rand hell, angekreuzt in
           der Akzentfarbe, damit man den Zustand ohne Suchen sieht. */
        QCheckBox::indicator, QRadioButton::indicator {
            width: 14px; height: 14px; border: 1px solid #8a9099; background: #161618; }
        QCheckBox::indicator { border-radius: 3px; }
        QRadioButton::indicator { border-radius: 8px; }
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {
            background: #4e84be; border-color: #8fb8d8; }
        QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: #d2d2d6; }
    """)

def _scale_font(app):
    scr = app.primaryScreen()
    if scr is None:
        return
    h = scr.geometry().height()
    f = app.font()
    f.setPointSize(12 if h >= 2000 else (10 if h >= 1400 else 9))
    app.setFont(f)

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    _scale_font(app)
    _apply_dark(app)
    w = Main()
    w.resize(1280, 860)
    w.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())
