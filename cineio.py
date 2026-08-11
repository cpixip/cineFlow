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
import subprocess
import threading

import numpy as np

from cineflow_defaults import VERSION as __version__

_ffmpeg_tools = {}

def tool(name):
    if name in _ffmpeg_tools:
        return _ffmpeg_tools[name]
    from shutil import which
    exe = name + (".exe" if os.name == "nt" else "")

    cand = []
    env = os.environ.get("FFMPEG_DIR")
    if env:
        cand.append(os.path.join(env, exe))
        cand.append(os.path.join(env, "bin", exe))
    hit = which(name)
    if hit:
        cand.append(hit)
    if os.name == "nt":
        for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", ""),
                     os.environ.get("LOCALAPPDATA", ""),
                     "C:\\"):
            if not root:
                continue
            for sub in ("ffmpeg\\bin", "ffmpeg",
                        "Microsoft\\WinGet\\Links"):
                cand.append(os.path.join(root, sub, exe))

    found = next((c for c in cand if c and os.path.isfile(c)), None)
    _ffmpeg_tools[name] = found
    return found

def ff(name):
    return tool(name) or name

SCENE_CONFIG_FILENAME = "cineflow.json"

def scene_config_path(input_path, is_dir=None):
    if is_dir is None:
        is_dir = os.path.isdir(input_path)
    if is_dir:
        return os.path.join(input_path, SCENE_CONFIG_FILENAME)
    base = os.path.splitext(input_path)[0]
    return f"{base}_cineflow.json"

def safe_name(name):
    out = []
    for ch in str(name):
        out.append(ch if (ch.isalnum() or ch in "-_") else "_")
    cleaned = "".join(out).strip("_")
    return cleaned or "scene"

def ffprobe(path, timeout=60):
    p = subprocess.run(
        [ff("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries",
         "stream=width,height,pix_fmt,color_range,color_space,"
         "color_transfer,color_primaries,bits_per_raw_sample,"
         "codec_name,nb_frames,r_frame_rate,avg_frame_rate,duration",
         "-of", "json", path], capture_output=True, timeout=timeout)
    try:
        st = json.loads(p.stdout or b"{}").get("streams", [])
    except json.JSONDecodeError:
        st = []
    if not st or "width" not in st[0]:
        raise ValueError(f"no video stream in {path}")
    return st[0]

def video_fps(st):
    for key in ("r_frame_rate", "avg_frame_rate"):
        try:
            a, b = str(st.get(key, "")).split("/")
            if float(b):
                return float(a) / float(b)
        except Exception:
            pass
    return 18.0

def video_frame_count(path, st, timeout=600):
    nb = st.get("nb_frames")
    if nb and str(nb).isdigit() and int(nb) > 0:
        return int(nb)
    p = subprocess.run(
        [ff("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-count_frames", "-show_entries", "stream=nb_read_frames",
         "-of", "default=nokey=1:noprint_wrappers=1", path],
        capture_output=True, timeout=timeout)
    try:
        return int((p.stdout or b"0").strip())
    except Exception:
        raise ValueError(f"cannot determine the frame count of {path}")

def guess_range(path, st, forced=None):
    if forced in ("pc", "tv"):
        return forced

    if st.get("color_range") in ("pc", "tv"):
        return st["color_range"]

    pix = str(st.get("pix_fmt", ""))
    if "gbr" in pix or "rgb" in pix:
        return "pc"

    depth = 12 if "12" in pix else (10 if "10" in pix else 8)
    maxv = (1 << depth) - 1
    lo = round(16 * maxv / 255)
    hi = round(235 * maxv / 255)
    fmt = f"yuv444p{depth}le" if "444" in pix else f"yuv422p{depth}le"
    w, h = int(st["width"]), int(st["height"])
    try:
        p = subprocess.run(
            [ff("ffmpeg"), "-nostdin", "-v", "error", "-i", path,
             "-frames:v", "3", "-pix_fmt", fmt, "-f", "rawvideo", "-"],
            capture_output=True, timeout=180)
        if not p.stdout:
            return "pc"
        arr = np.frombuffer(p.stdout, dtype="<u2" if depth > 8 else np.uint8)
        luma = arr[:w * h].astype(np.int32)
        frac = float(((luma < lo) | (luma > hi)).mean())
        rng = "pc" if frac > 0.001 else "tv"
        print(f"  [video] range NOT tagged -- measured: {rng} "
              f"({100*frac:.2f} % of luma values outside 16..235).")
        if frac < 0.02:
            print(f"  [video] NOTE: close call. On flat material "
                  f"(Log/HDR) this can be WRONG.")
            print(f"  [video]   -> when in doubt pass --video-range pc "
                  f"(DaVinci: export with 'Data Levels: Full').")
        return rng
    except Exception:
        return "pc"

class StderrDrain:

    KEEP = 8192

    def __init__(self, proc):
        self._chunks = []
        self._size = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run, args=(proc.stderr,), daemon=True)
        self._thread.start()

    def _run(self, pipe):
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                with self._lock:
                    self._chunks.append(chunk)
                    self._size += len(chunk)
                    while self._size > self.KEEP and len(self._chunks) > 1:
                        self._size -= len(self._chunks.pop(0))
        except Exception:
            pass

    def text(self, limit=2000):
        self._thread.join(timeout=1.0)
        with self._lock:
            raw = b"".join(self._chunks)
        return raw[-limit:].decode(errors="replace")

_FALLBACK_WARNED = set()

def load_tiff(path, want_float=True):
    import errno

    path = str(path)
    img = None
    try:
        import tifffile
        img = tifffile.imread(path)
    except OSError as e:
        if getattr(e, "errno", None) in (errno.EIO, errno.ENODEV, errno.ENXIO,
                                         getattr(errno, "EREMOTEIO", -1)):
            raise RuntimeError(
                f"cannot read {path}: {e} -- input storage gone? "
                f"(no fallback attempted: reading on a dead device risks "
                f"an uncatchable bus error)")
        img = _imread_cv2(path, e)
    except Exception as e:
        img = _imread_cv2(path, e)

    if img.ndim == 2:
        img = np.stack([img, img, img], axis=-1)
    if not want_float:
        return img
    div = 65535.0 if img.dtype == np.uint16 else 255.0
    return img.astype(np.float32) / div

def _imread_cv2(path, why):
    import cv2
    reason = f"{type(why).__name__}: {why}"
    if reason not in _FALLBACK_WARNED:
        _FALLBACK_WARNED.add(reason)
        print(f"  [reader] WARNING: tifffile fails ({why}) -- "
              f"falling back to cv2.imread")
        print(f"  [reader]          first seen on {path}; further files with "
              f"the same cause are read the same way, silently")
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"cannot read {path} with tifffile or cv2 "
                           f"-- damaged file?")
    return img[:, :, ::-1].copy() if img.ndim == 3 else img
