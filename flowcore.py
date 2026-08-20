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


import importlib
import math
import os
import subprocess
import sys
import threading
from collections import OrderedDict
from typing import NamedTuple

import cv2
import numpy as np

from cineflow_defaults import (DEFAULT_CONFIG, SCENE_PARAMS, EPS_GUARD,
                               VIDEO_EXTS as _VIDEO_EXTS)
import cineio

USE_BURT = False
_BURT_9 = np.array([1, 8, 28, 56, 70, 56, 28, 8, 1], dtype=np.float32)
_BURT_9 = _BURT_9 / _BURT_9.sum()

_dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)

_raft_models = {}
_raft_device = None
_tv_of = None
_raft_import_error = None
RAFT_AVAILABLE = False
try:
    import torch
    import torchvision.models.optical_flow as _tv_of
    _raft_device = "cuda" if torch.cuda.is_available() else "cpu"
    RAFT_AVAILABLE = True
except Exception as _e:
    _raft_import_error = repr(_e)
    RAFT_AVAILABLE = False

def log(tag, text=""):
    line = f"[{tag}] {text}" if text else f"[{tag}]"
    try:
        out = sys.stdout
        if out is None:
            return
        out.write(line.encode("ascii", "replace").decode("ascii") + "\n")
        out.flush()
    except Exception:
        pass

def log_is_tty():
    try:
        return bool(sys.stdout) and sys.stdout.isatty()
    except Exception:
        return False

class TrustRaw(NamedTuple):
    resid: object
    warped: object
    offset: int

_OFFSET_DEPENDENT_KEYS = {
    "nbr_warped", "nbr_warped_trust",
    "flow_fw", "warped_flow_bw",
    "trust_geo", "trust_photo",
}

_VIEW_ONLY_KEYS = {
    "_neighbor_offset",
    "_proxy",
    "_need_dustA",
    "_need_dustB",
}

def make_cfg(**overrides):
    cfg = dict(DEFAULT_CONFIG)
    unknown = [k for k in overrides
               if k not in cfg and k not in _VIEW_ONLY_KEYS]
    if unknown:
        raise KeyError(f"unknown parameters: {unknown}")
    cfg.update(overrides)
    cfg.setdefault("_neighbor_offset", 1)
    return cfg

class Backend(NamedTuple):
    key: str
    label: str
    gpu: bool
    color: bool
    max_pixels: int
    probe: str
    note: str

BACKENDS = OrderedDict((b.key, b) for b in (
    Backend("RAFT", "RAFT", True,  True,  1_690_000, "torchvision",
            "Torch/GPU. Accurate, robust against grain -- but fills areas "
            "without correspondence with self-consistent flow that passes "
            "geoTrust."),
    Backend("DIS",    "DIS",  False, False, 0, "cv2",
            "OpenCV/CPU. Faster, and fails LOUDLY: without correspondence "
            "the flow becomes incoherent and geoTrust catches it."),
))

ALL_BACKENDS = tuple(BACKENDS)

DEFAULT_BACKEND = "RAFT"

def backend_label(key):
    b = BACKENDS.get(key)
    return b.label if b else key

def backend_key(label):
    for k, b in BACKENDS.items():
        if b.label == label:
            return k
    return label

def backend_is_gpu(key):
    b = BACKENDS.get(key)
    return bool(b.gpu) if b else False

def backend_wants_color(key):
    b = BACKENDS.get(key)
    return bool(b.color) if b else False

def min_flow_div(key, width, height):
    b = BACKENDS.get(key)
    if not b or not b.max_pixels or not width or not height:
        return 1.0
    need = math.sqrt(float(width) * float(height) / float(b.max_pixels))
    return max(1.0, math.ceil(need * 20.0) / 20.0)

def resolve_backend(cfg=None, backend=None):
    want = backend or (cfg or {}).get("flow_backend") or DEFAULT_BACKEND
    have = backends_available()
    return (want if want in have else "DIS"), want

_backend_probe_cache = {}
_backend_probe_why = {}

def backends_available():
    out = []
    for key, b in BACKENDS.items():
        ok = _backend_probe_cache.get(key)
        if ok is None:
            why = None
            try:
                importlib.import_module(b.probe)
                if b.gpu:
                    importlib.import_module("torch")
                ok = True
            except Exception as e:
                ok = False
                why = repr(e)
            _backend_probe_cache[key] = ok
            if why:
                _backend_probe_why[key] = why
            if not ok:
                hint = ("PyTorch + torchvision" if b.gpu
                        else "opencv-python")
                log(b.label, f"not available -- install {hint}")
                log(b.label, f"  {why}")
        if ok:
            out.append(key)
    return out or ["DIS"]

def backend_reason(key):
    if key not in BACKENDS:
        return f"not a valid backend name (valid: {' | '.join(ALL_BACKENDS)})"
    backends_available()
    if key in _backend_probe_why:
        return f"probe failed: {_backend_probe_why[key]}"
    return None

def norm(d, lo, hi):
    x = (d.astype(np.float32) - lo) / (hi - lo)
    x = np.clip(x, 0.0, 1.0)
    u8 = (x * 255.0 + 0.5).astype(np.uint8)
    if u8.ndim == 2:
        return cv2.cvtColor(u8, cv2.COLOR_GRAY2BGR)
    return u8[:, :, ::-1].copy()

def heat(d):
    x = np.clip(d.astype(np.float32), 0.0, 1.0)
    u8 = (x * 255.0 + 0.5).astype(np.uint8)
    if u8.ndim == 3:
        u8 = cv2.cvtColor(u8, cv2.COLOR_RGB2GRAY)
    return cv2.applyColorMap(u8, cv2.COLORMAP_TURBO)

_FLOW_HUE_OFFSET = 0.0
_FLOW_SAT = 191

FLOW_MAXMAG = 30.0
FLOW_MAXMAG_REL = 8.0

def flow_hsv(flow, maxmag=FLOW_MAXMAG, hue_offset=_FLOW_HUE_OFFSET, sat=_FLOW_SAT):
    fx, fy = flow[..., 0], flow[..., 1]
    mag, ang = cv2.cartToPolar(fx.astype(np.float32), fy.astype(np.float32))
    hue = (ang * 180.0 / np.pi / 2.0 + float(hue_offset)) % 180.0
    hsv = np.zeros((*flow.shape[:2], 3), dtype=np.uint8)
    hsv[..., 0] = hue.astype(np.uint8)
    hsv[..., 1] = int(sat)
    hsv[..., 2] = np.clip(mag / maxmag * 255.0, 0, 255).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

def dominant_flow(flow):
    return np.median(flow.reshape(-1, 2), axis=0)

def flow_hsv_rel(flow, maxmag=FLOW_MAXMAG_REL, hue_offset=_FLOW_HUE_OFFSET):
    return flow_hsv(flow - dominant_flow(flow), maxmag=maxmag,
                    hue_offset=hue_offset)

def resid_mag(flow, hi=10.0):
    mag = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
    return heat(np.clip(mag / hi, 0, 1))

def load_tiff(path):
    return cineio.load_tiff(path)

VIDEO_EXTS = _VIDEO_EXTS

_VIDEO_CACHE_FRAMES = 240
_VIDEO_READ_AHEAD = 24
_VIDEO_SEEK_BACK = 3

_tool = cineio.tool

def have_ffmpeg():
    return bool(_tool("ffmpeg")) and bool(_tool("ffprobe"))

def is_video(path):
    return os.path.isfile(path) and path.lower().endswith(VIDEO_EXTS)

_ffprobe = cineio.ffprobe
_video_fps = cineio.video_fps
_video_frame_count = cineio.video_frame_count
_guess_range = cineio.guess_range

class FolderSource:

    kind = "tiff"
    depth = 16
    backend = "TIFF"

    CACHE_N = 9

    def __init__(self, folder):
        import glob
        self.path = folder
        self.files = sorted(glob.glob(os.path.join(folder, "*.tif")) +
                            glob.glob(os.path.join(folder, "*.tiff")),
                            key=cineio.numeric_sort_key)
        if not self.files:
            raise ValueError(
                f"no TIFF files in {folder} -- cineFlow reads "
                f".tif/.tiff image sequences and .mov/.mkv/.mp4/.avi "
                f"video files")
        self.height = self.width = None
        self._cache = {}
        self._order = []

    def __len__(self):
        return len(self.files)

    def __bool__(self):
        return bool(self.files)

    def __getitem__(self, i):
        hit = self._cache.get(i)
        if hit is not None:
            try:
                self._order.remove(i)
            except ValueError:
                pass
            self._order.append(i)
            return hit
        img = load_tiff(self.files[i])
        self._cache[i] = img
        self._order.append(i)
        while len(self._order) > self.CACHE_N:
            self._cache.pop(self._order.pop(0), None)
        return img

    def close(self):
        self._cache.clear()
        self._order.clear()

class VideoSource:

    kind = "video"
    depth = 16
    backend = "ffmpeg (16 bit)"

    def __init__(self, path, cache_frames=_VIDEO_CACHE_FRAMES):
        self.path = path
        self.st = _ffprobe(path)
        self.width = int(self.st["width"])
        self.height = int(self.st["height"])
        self.fps = _video_fps(self.st)
        self.n = _video_frame_count(path, self.st)
        self.color_range = _guess_range(path, self.st)
        self.color_space = self.st.get("color_space") or "bt709"
        if self.color_space in ("unknown", "-"):
            self.color_space = "bt709"

        self._cache = OrderedDict()
        self._cache_max = max(8, int(cache_frames))
        self._proc = None
        self._next = None
        self._drain = None
        self._fb = self.width * self.height * 3 * 2
        self._lock = threading.RLock()

    def _cmd(self, seek_idx):
        cmd = [_tool("ffmpeg"), "-nostdin", "-v", "error"]
        if seek_idx > 0:
            cmd += ["-ss", f"{max(0.0, (seek_idx - 0.1) / self.fps):.6f}"]
        cmd += ["-i", self.path]
        pix = str(self.st.get("pix_fmt", ""))
        if not ("gbr" in pix or "rgb" in pix):
            cmd += ["-vf", f"scale=in_color_matrix={self.color_space}:"
                           f"in_range={self.color_range}:out_range=full"]
        cmd += ["-pix_fmt", "rgb48le", "-f", "rawvideo", "-"]
        return cmd

    def _open(self, idx):
        self._close_pipe()
        seek = max(0, idx - _VIDEO_SEEK_BACK)
        self._proc = subprocess.Popen(
            self._cmd(seek), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=self._fb)
        self._drain = cineio.StderrDrain(self._proc)
        self._next = seek

    def _close_pipe(self):
        if self._proc is not None:
            try:
                self._proc.stdout.close()
            except Exception:
                pass
            try:
                self._proc.kill()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None
            self._next = None
            self._drain = None

    def _pull(self):
        buf = self._proc.stdout.read(self._fb)
        if not buf or len(buf) < self._fb:
            err = self._drain.text(300) if self._drain else ""
            if err.strip():
                log("video", f"ffmpeg: {err.strip()}")
            return None
        return (np.frombuffer(buf, dtype="<u2")
                .reshape(self.height, self.width, 3)
                .astype(np.float32) / 65535.0)

    def _put(self, i, frame):
        self._cache[i] = frame
        self._cache.move_to_end(i)
        while len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    def __len__(self):
        return self.n

    def __bool__(self):
        return self.n > 0

    def __getitem__(self, i):
        if i < 0:
            i += self.n
        if not (0 <= i < self.n):
            raise IndexError(f"frame {i} out of range 0..{self.n - 1}")
        with self._lock:
            hit = self._cache.get(i)
            if hit is not None:
                self._cache.move_to_end(i)
                return hit
            if not (self._proc is not None and self._next == i):
                self._open(i)

            got = None
            while self._next is not None and self._next <= i:
                frame = self._pull()
                if frame is None:
                    self._close_pipe()
                    raise IndexError(f"frame {i} could not be read")
                self._put(self._next, frame)
                if self._next == i:
                    got = frame
                self._next += 1

            for _ in range(_VIDEO_READ_AHEAD - 1):
                if self._next is None or self._next >= self.n:
                    break
                frame = self._pull()
                if frame is None:
                    self._close_pipe()
                    break
                self._put(self._next, frame)
                self._next += 1
            return got

    def close(self):
        with self._lock:
            self._close_pipe()
            self._cache.clear()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

class VideoSourceCV:

    kind = "video"
    depth = 8
    backend = "OpenCV (8 bit)"

    def __init__(self, path, cache_frames=_VIDEO_CACHE_FRAMES):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise ValueError(f"OpenCV cannot open {path}")
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS)) or 18.0
        if self.n <= 0:
            raise ValueError(f"cannot determine the frame count of {path}")
        self.color_range = None
        self._cache = OrderedDict()
        self._cache_max = max(8, int(cache_frames))
        self._next = 0
        self._lock = threading.RLock()
        log("video", "no ffmpeg found -- OpenCV fallback, 8 bit only.")
        log("video", "  Fine shadow detail cannot be judged this way; "
                     "install ffmpeg and ffprobe,")
        log("video", "  or set FFMPEG_DIR to the folder holding them.")

    def _put(self, i, frame):
        self._cache[i] = frame
        self._cache.move_to_end(i)
        while len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    def _grab(self):
        ok, bgr = self.cap.read()
        if not ok or bgr is None:
            return None
        return (bgr[:, :, ::-1].astype(np.float32) / 255.0)

    def __len__(self):
        return self.n

    def __bool__(self):
        return self.n > 0

    def __getitem__(self, i):
        if i < 0:
            i += self.n
        if not (0 <= i < self.n):
            raise IndexError(f"frame {i} out of range 0..{self.n - 1}")
        with self._lock:
            hit = self._cache.get(i)
            if hit is not None:
                self._cache.move_to_end(i)
                return hit
            if self._next != i:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                self._next = i
            frame = self._grab()
            if frame is None:
                raise IndexError(f"frame {i} could not be read")
            self._put(i, frame)
            self._next = i + 1
            for _ in range(_VIDEO_READ_AHEAD - 1):
                if self._next >= self.n:
                    break
                nxt = self._grab()
                if nxt is None:
                    break
                self._put(self._next, nxt)
                self._next += 1
            return frame

    def close(self):
        with self._lock:
            try:
                self.cap.release()
            except Exception:
                pass
            self._cache.clear()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

def open_source(path):
    if is_video(path):
        if have_ffmpeg():
            return VideoSource(path)
        return VideoSourceCV(path)
    if os.path.isdir(path):
        return FolderSource(path)
    raise ValueError(f"neither a TIFF folder nor a video file: {path}")

def to_gray(rgb):
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2])

def burt_filter(gray):
    tmp = cv2.filter2D(gray, -1, _BURT_9.reshape(1, -1), borderType=cv2.BORDER_REFLECT)
    return cv2.filter2D(tmp, -1, _BURT_9.reshape(-1, 1), borderType=cv2.BORDER_REFLECT)

def pyr_downscale(img, factor):
    f = float(factor)
    if f <= 1.0 + 1e-6:
        return img

    n = int(math.floor(math.log2(f)))
    out = img
    for _ in range(n):
        out = cv2.pyrDown(out)

    rest = f / (2 ** n)
    if rest > 1.0 + 1e-6:
        sigma = 0.5 * math.sqrt(max(rest * rest - 1.0, 0.0))
        if sigma > 1e-3:
            k = int(math.ceil(3.0 * sigma)) * 2 + 1
            out = cv2.GaussianBlur(out, (k, k), sigma)
        h, w = out.shape[:2]
        nh = max(8, int(round(h / rest)))
        nw = max(8, int(round(w / rest)))
        out = cv2.resize(out, (nw, nh), interpolation=cv2.INTER_AREA)
    return out

def prep_flow_input(rgb):
    g = to_gray(rgb)
    return burt_filter(g) if USE_BURT else g

_raft_warned = set()

def _ensure_raft(which):
    if which in _raft_models:
        return _raft_models[which]
    if not RAFT_AVAILABLE:
        if which not in _raft_warned:
            _raft_warned.add(which)
            print(f"[RAFT] not available ({which}) -- computing with DIS instead!")
            if _raft_import_error:
                print(f"[RAFT]   reason: {_raft_import_error}")
        return None
    try:
        if which == "RAFT":
            weights = _tv_of.Raft_Small_Weights.DEFAULT
            model = _tv_of.raft_small(weights=weights).to(_raft_device).eval()
        else:
            weights = _tv_of.Raft_Large_Weights.DEFAULT
            model = _tv_of.raft_large(weights=weights).to(_raft_device).eval()
        _raft_models[which] = model
        print(f"[RAFT] model loaded ({which}, {_raft_device}).")
        return model
    except Exception as e:
        _raft_models[which] = None
        if which not in _raft_warned:
            _raft_warned.add(which)
            print(f"[RAFT] Laden fehlgeschlagen ({which}): {e}")
            print(f"[RAFT] -> computing with DIS although {which} was selected!")
        return None

def _dis_flow(gray_from, gray_to):
    a = (np.clip(gray_from, 0, 1) * 255).astype(np.uint8)
    b = (np.clip(gray_to,   0, 1) * 255).astype(np.uint8)
    return _dis.calc(a, b, None)

def _raft_flow(model, rgb_from, rgb_to, cfg, cache=None, key_from=None, key_to=None):
    def prepare(rgb, key):
        if cache is not None and key is not None and key in cache:
            return cache[key]
        down = pyr_downscale(rgb, cfg["downscale"])
        dh, dw = down.shape[:2]
        ph = (8 - dh % 8) % 8
        pw = (8 - dw % 8) % 8
        t = torch.from_numpy(np.clip(down, 0, 1).astype(np.float32))
        t = t.permute(2, 0, 1)[None]
        t = t * 2.0 - 1.0
        if ph or pw:
            t = torch.nn.functional.pad(t, (0, pw, 0, ph), mode='replicate')
        t = t.to(_raft_device)
        result = {"tensor": t, "h": dh, "w": dw}
        if cache is not None and key is not None:
            cache[key] = result
        return result

    prepped_from = prepare(rgb_from, key_from)
    prepped_to = prepare(rgb_to, key_to)
    dh, dw = prepped_from["h"], prepped_from["w"]

    use_amp = (bool(cfg.get("raft_fp16", DEFAULT_CONFIG["raft_fp16"]))
               and _raft_device == "cuda")
    with torch.inference_mode():
        with torch.autocast(device_type="cuda", enabled=use_amp):
            flow = model(prepped_from["tensor"], prepped_to["tensor"],
                         num_flow_updates=int(cfg.get(
                             "raft_iterations",
                             DEFAULT_CONFIG["raft_iterations"])))[-1]
    flow = flow[0].float().permute(1, 2, 0).cpu().numpy()
    return flow[:dh, :dw].copy()

def compute_flow(rgb_from, rgb_to, cfg, backend, cache=None, key_from=None, key_to=None):
    h, w = rgb_from.shape[:2]

    model = _ensure_raft(backend) if BACKENDS.get(backend, None) and \
        BACKENDS[backend].gpu else None

    if model is not None:
        flow = _raft_flow(model, rgb_from, rgb_to, cfg, cache=cache, key_from=key_from, key_to=key_to)
    else:
        ga = to_gray(rgb_from)
        gb = to_gray(rgb_to)
        a = pyr_downscale(ga, cfg["downscale"])
        b = pyr_downscale(gb, cfg["downscale"])
        flow = _dis_flow(a, b)

    fh, fw = flow.shape[:2]
    if (fh, fw) != (h, w):
        sx, sy = w / fw, h / fh
        flow = cv2.resize(flow, (w, h), interpolation=cv2.INTER_LINEAR)
        flow[..., 0] *= sx
        flow[..., 1] *= sy
    return flow

def warp(img, flow):
    h, w = flow.shape[:2]
    xx, yy = np.meshgrid(np.arange(w, dtype=np.float32),
                         np.arange(h, dtype=np.float32))
    map_x = (xx + flow[..., 0]).astype(np.float32)
    map_y = (yy + flow[..., 1]).astype(np.float32)
    return cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT)

def sigmoid_trust(err, mismatch, softness):
    raw = 1.0 - 1.0 / (1.0 + np.exp(-((err - mismatch) / softness)))
    raw0 = 1.0 - 1.0 / (1.0 + np.exp(mismatch / softness))
    return np.clip(raw / max(float(raw0), 1e-12), 0.0, 1.0)

def geometric_trust(resid, mismatch=3.0, softness=1.5):
    error = np.sqrt(resid[..., 0]**2 + resid[..., 1]**2)
    error = np.clip(error, 0.0, 15.0)
    return sigmoid_trust(error, mismatch, softness)

def photometric_trust(warped_frame, frame_0, mismatch=0.1, radius=3,
                      softness=0.025):
    photo_dev = np.abs(warped_frame - frame_0).mean(axis=2)
    k = 2 * radius + 1
    photo_smooth = cv2.blur(photo_dev, (k, k))
    return sigmoid_trust(photo_smooth, mismatch, softness)

def group_median_mad(f0, warped_list, center_weight=1):
    stack = np.stack([f0] * center_weight + list(warped_list), axis=0)
    median_img = np.median(stack, axis=0)
    dev = np.abs(stack - median_img[None, ...]).mean(axis=3)
    mad = np.median(dev, axis=0)
    return median_img, mad, dev

def committee_stats(f0, warped_list):
    if not warped_list:
        return None, None, None, None, None

    stack = np.stack(warped_list, axis=0)
    median_nb = np.median(stack, axis=0)

    dev_nb = np.mean(np.abs(stack - median_nb[None]), axis=3)
    disp = np.median(dev_nb, axis=0)

    diff = f0 - median_nb
    signed = np.mean(diff, axis=2)
    resid = np.mean(np.abs(diff), axis=2)

    return (median_nb.astype(np.float32), disp.astype(np.float32),
            resid.astype(np.float32), signed.astype(np.float32),
            dev_nb.astype(np.float32))

def outlier_trust(dev_member, mad, mismatch, softness, eps):
    score = dev_member / (mad + eps)
    return sigmoid_trust(score, mismatch, softness)

def _guided_filter_gray(guide, src, radius, eps):
    k = 2 * radius + 1
    mean_I = cv2.blur(guide, (k, k))
    mean_p = cv2.blur(src, (k, k))
    corr_I = cv2.blur(guide * guide, (k, k))
    corr_Ip = cv2.blur(guide * src, (k, k))
    var_I = corr_I - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I
    mean_a = cv2.blur(a, (k, k))
    mean_b = cv2.blur(b, (k, k))
    return mean_a * guide + mean_b

_WARNED_FILTERS = set()

def _smooth_detail(luma, sigma, detail_filter, detail_eps):
    sig = max(float(sigma), 0.05)
    r = max(1, int(math.ceil(3.0 * sig)))
    if detail_filter == "guided":
        return _guided_filter_gray(luma, luma, r, detail_eps)
    if detail_filter != "gauss" and detail_filter not in _WARNED_FILTERS:
        _WARNED_FILTERS.add(detail_filter)
        print(f"[detail_filter] WARNING: unknown value {detail_filter!r} "
              f"-- continuing with 'gauss' (valid: guided | gauss)")
    k = 2 * r + 1
    return cv2.GaussianBlur(luma, (k, k), sig)

def _neighbor_diag(f0, fj, cfg, backend, cache=None):
    flow_fwd = compute_flow(f0, fj, cfg, backend, cache=cache, key_from=id(f0), key_to=id(fj))
    flow_bwd = compute_flow(fj, f0, cfg, backend, cache=cache, key_from=id(fj), key_to=id(f0))
    warped_frame   = warp(fj, flow_fwd)
    warped_flow_bw = warp(flow_bwd, flow_fwd)
    resid = flow_fwd + warped_flow_bw
    gtrust = geometric_trust(
        resid,
        mismatch=float(cfg.get("geo_mismatch",
                               DEFAULT_CONFIG["geo_mismatch"])),
        softness=float(cfg.get("geo_softness",
                               DEFAULT_CONFIG["geo_softness"])))
    ptrust = photometric_trust(
        warped_frame, f0,
        mismatch=float(cfg.get("photo_mismatch",
                               DEFAULT_CONFIG["photo_mismatch"])),
        radius=int(cfg.get("photo_radius",
                           DEFAULT_CONFIG["photo_radius"])),
        softness=float(cfg.get("photo_softness",
                               DEFAULT_CONFIG["photo_softness"])))
    ctrust = gtrust * ptrust
    return {
        "flow_fwd": flow_fwd, "flow_bwd": flow_bwd,
        "warped_frame": warped_frame, "warped_flow_bw": warped_flow_bw,
        "resid": resid, "gtrust": gtrust, "ptrust": ptrust, "ctrust": ctrust,
    }

def _apply_trust_stage(data, cfg):
    raw = data.get("_trust_raw")
    f0 = data.get("_center")
    if raw is None or f0 is None:
        return data

    gd = float(cfg.get("geo_mismatch", DEFAULT_CONFIG["geo_mismatch"]))
    gs = float(cfg.get("geo_softness", DEFAULT_CONFIG["geo_softness"]))
    pd = float(cfg.get("photo_mismatch", DEFAULT_CONFIG["photo_mismatch"]))
    prd = int(cfg.get("photo_radius", DEFAULT_CONFIG["photo_radius"]))
    ps = float(cfg.get("photo_softness", DEFAULT_CONFIG["photo_softness"]))

    trust_weighted = []
    offsets = []
    for entry in raw:
        offsets.append(entry.offset)
        gt = geometric_trust(entry.resid, mismatch=gd, softness=gs)
        pt = photometric_trust(entry.warped, f0, mismatch=pd, radius=prd,
                               softness=ps)
        warped = entry.warped
        trust_weighted.append((warped, gt, pt, gt * pt))
    data["_trust_weighted"] = trust_weighted

    if data.get("_lazy"):
        if trust_weighted:
            _wf, _gt, _pt, _ct = trust_weighted[0]
            data["trust_geo"] = _gt
            data["trust_photo"] = _pt
            data["nbr_warped_trust"] = _wf * _ct[..., None]
        return data

    num = f0.copy()
    den = np.ones(f0.shape[:2], dtype=np.float32)
    for wf, _gt, _pt, ct in trust_weighted:
        num = num + wf * ct[..., None]
        den = den + ct
    data["fuse_best"] = num / den[..., None]

    if trust_weighted:
        want_off = cfg.get("_neighbor_offset", 1)
        try:
            i_diag = offsets.index(want_off)
        except ValueError:
            i_diag = 0
        _wf, _gt, _pt, _ct = trust_weighted[i_diag]
        data["trust_geo"] = _gt
        data["trust_photo"] = _pt
        data["nbr_warped_trust"] = _wf * _ct[..., None]

    if trust_weighted:
        data["trust_mean_best"] = np.mean([ct for _, _, _, ct in trust_weighted],
                                     axis=0)
    else:
        data["trust_mean_best"] = np.zeros(f0.shape[:2], dtype=np.float32)
    data["trust_by_offset"] = {off: float(ct.mean())
                               for off, (_w, _g, _p, ct)
                               in zip(offsets, trust_weighted)}

    _apply_dustA_stage(data, cfg)
    _apply_dustB_stage(data, cfg)
    _apply_sharp_stage(data, cfg)
    return data

DUSTA_KEYS = frozenset({
    "fuse_dustA", "trust_mean_dustA",
    "output_dustA",
    "tex_weight_dustA", "sharp_gate_dustA",
})

DUSTB_KEYS = frozenset({
    "fuse_dustB", "trust_mean_dustB",
    "output_dustB",
    "tex_weight_dustB", "sharp_gate_dustB",
})

def _need_dustA(cfg):
    if cfg.get("mode", "best") == "dustA":
        return True
    want = cfg.get("_need_dustA")
    return True if want is None else bool(want)

def _need_dustB(cfg):
    if cfg.get("mode", "best") == "dustB":
        return True
    want = cfg.get("_need_dustB")
    return True if want is None else bool(want)

def _apply_dustA_stage(data, cfg):
    if not _need_dustA(cfg):
        for k in DUSTA_KEYS:
            data.pop(k, None)
        return data

    f0 = data.get("_center")
    warped_neighbors = data.get("_warped_neighbors")
    trust_weighted = data.get("_trust_weighted")
    if f0 is None or not warped_neighbors:
        return data

    median_img, mad, dev = group_median_mad(f0, warped_neighbors, center_weight=cfg["center_weight"])

    _mk, _ms, _me = cfg["dustA_mismatch"], cfg["dustA_softness"], EPS_GUARD
    f0_trust = outlier_trust(dev[0], mad, _mk, _ms, _me)

    grp_trusts = [outlier_trust(dev[cfg["center_weight"] + i], mad, _mk, _ms, _me)
                  for i in range(len(warped_neighbors))]

    ctg_list = []
    num = f0 * f0_trust[..., None]
    den = f0_trust.copy()
    for (wf, gt, _pt, _ct), pgt in zip(trust_weighted, grp_trusts):
        ctg = gt * pgt
        ctg_list.append(ctg)
        num = num + wf * ctg[..., None]
        den = den + ctg
    den = np.clip(den, 1e-4, None)
    data["fuse_dustA"] = np.clip(num / den[..., None], 0.0, 1.0)

    data["trust_mean_dustA"] = np.mean(ctg_list, axis=0) if ctg_list else \
        np.zeros(f0.shape[:2], dtype=np.float32)
    return data

def _apply_dustB_stage(data, cfg):
    if not _need_dustB(cfg):
        for k in DUSTB_KEYS:
            data.pop(k, None)
        return data

    f0 = data.get("_center")
    warped_neighbors = data.get("_warped_neighbors")
    trust_weighted = data.get("_trust_weighted")
    if f0 is None or not warped_neighbors:
        return data

    median_nb, disp, resid, _signed, dev_nb = committee_stats(f0, warped_neighbors)
    if median_nb is None:
        return data

    eps = EPS_GUARD

    score = resid / (disp + eps)

    t_center = sigmoid_trust(score, cfg["dustB_mismatch"], cfg["dustB_softness"])

    committee_ok = sigmoid_trust(disp, cfg["dustB_disagreement"],
                                  cfg["dustB_disagreement_softness"])

    f0_trust = 1.0 - (1.0 - t_center) * committee_ok
    f0_trust = np.clip(f0_trust, 0.0, 1.0).astype(np.float32)

    grp_trusts = [outlier_trust(dev_nb[i], disp, cfg["dustB_mismatch"],
                                cfg["dustB_softness"], eps)
                  for i in range(len(warped_neighbors))]

    ctg_list = []
    num = f0 * f0_trust[..., None]
    den = f0_trust.copy()
    for (wf, gt, _pt, _ct), pgt in zip(trust_weighted, grp_trusts):
        ctg = gt * pgt
        ctg_list.append(ctg)
        num = num + wf * ctg[..., None]
        den = den + ctg
    den = np.clip(den, 1e-4, None)
    data["fuse_dustB"] = np.clip(num / den[..., None], 0.0, 1.0)

    data["trust_mean_dustB"] = np.mean(ctg_list, axis=0) if ctg_list else \
        np.zeros(f0.shape[:2], dtype=np.float32)
    return data

def _sharpen(base_img, trust_mean, cfg):
    luma = to_gray(base_img)

    r = 4
    k = 2 * r + 1
    sigma_tex = max(k / 6.0, 0.1)
    mean = cv2.GaussianBlur(luma, (k, k), sigma_tex)
    mean_sq = cv2.GaussianBlur(luma * luma, (k, k), sigma_tex)
    var = np.clip(mean_sq - mean * mean, 0, None)
    texture = np.sqrt(var)

    t = np.clip(texture / cfg["sharp_full"], 0.0, 1.0) ** cfg["sharp_gamma"]
    tex_w = cfg["sharp_base"] + (1.0 - cfg["sharp_base"]) * t
    gate = tex_w * trust_mean

    luma_smooth = _smooth_detail(luma, cfg["detail_sigma"],
                                 cfg["detail_filter"], cfg["detail_eps"])
    detail = luma - luma_smooth

    out = base_img + detail[..., None] * cfg["sharp_amount"] * gate[..., None]
    return np.clip(out, 0.0, 1.0), texture, tex_w, gate

def _apply_sharp_stage(data, cfg):
    if "fuse_best" not in data:
        return data
    out, texture, tex_w, gate = _sharpen(data["fuse_best"],
                                         data["trust_mean_best"], cfg)
    data["output_best"] = out
    data["texture"] = texture
    data["tex_weight_best"] = tex_w
    data["sharp_gate_best"] = gate

    if "fuse_dustA" in data:
        _o, _tex, _tw, _g = _sharpen(data["fuse_dustA"],
                                     data["trust_mean_dustA"], cfg)
        data["output_dustA"] = _o
        data["tex_weight_dustA"] = _tw
        data["sharp_gate_dustA"] = _g

    if "fuse_dustB" in data:
        _o, _tex, _tw, _g = _sharpen(data["fuse_dustB"],
                                     data["trust_mean_dustB"], cfg)
        data["output_dustB"] = _o
        data["tex_weight_dustB"] = _tw
        data["sharp_gate_dustB"] = _g

    return data

def process_frame(idx, files, cfg, backend, active_view=None):
    data = {}
    n = len(files)

    f0 = files[idx]
    data["input"] = f0

    if active_view == "input":
        return data

    lazy = active_view is not None and active_view in _OFFSET_DEPENDENT_KEYS

    warped_neighbors = []
    trust_weighted   = []
    trust_raw        = []
    diag_by_offset   = {}
    flow_cache       = {}

    if not lazy:
        offsets = [o for o in range(-cfg["context"], cfg["context"] + 1) if o != 0]
        for off in offsets:
            j = idx + off
            if j < 0 or j >= n:
                continue
            fj = files[j]

            diag = _neighbor_diag(f0, fj, cfg, backend, cache=flow_cache)
            diag_by_offset[off] = diag

            warped_neighbors.append(diag["warped_frame"])
            trust_weighted.append((diag["warped_frame"], diag["gtrust"], diag["ptrust"], diag["ctrust"]))
            trust_raw.append(TrustRaw(diag["resid"], diag["warped_frame"], off))

    diag = None
    if "_neighbor_offset" in cfg:
        off = cfg["_neighbor_offset"]
        if off in diag_by_offset:
            diag = diag_by_offset[off]
        else:
            j_diag = idx + off
            if 0 <= j_diag < n:
                fj_diag = files[j_diag]
                diag = _neighbor_diag(f0, fj_diag, cfg, backend,
                                      cache=flow_cache)
            else:
                print(f"[neighbour] offset {off:+d} out of range "
                      f"(frame {idx+1}/{n}) -- diagnostic views stay empty.")

    if diag is not None:
        data["nbr_warped"]   = diag["warped_frame"]
        data["nbr_warped_trust"] = diag["warped_frame"] * diag["ctrust"][..., None]
        data["flow_fw"]        = diag["flow_fwd"]
        data["warped_flow_bw"] = diag["warped_flow_bw"]
        data["trust_geo"]      = diag["gtrust"]
        data["trust_photo"]    = diag["ptrust"]

    if lazy:
        data["_center"] = f0
        data["_trust_raw"] = (
            [TrustRaw(diag["resid"], diag["warped_frame"], off)]
            if diag is not None else [])
        data["_lazy"] = True
        return data

    num = f0.copy()
    den = np.ones(f0.shape[:2], dtype=np.float32)
    for wf, _gt, _pt, ct in trust_weighted:
        num = num + wf * ct[..., None]
        den = den + ct
    data["fuse_best"] = num / den[..., None]

    data["_center"] = f0
    data["_warped_neighbors"] = warped_neighbors
    data["_trust_weighted"] = trust_weighted
    data["_trust_raw"] = trust_raw
    _apply_dustA_stage(data, cfg)
    _apply_dustB_stage(data, cfg)

    if trust_weighted:
        trust_mean = np.mean([ct for _, _, _, ct in trust_weighted], axis=0)
    else:
        trust_mean = np.zeros(f0.shape[:2], dtype=np.float32)
    data["trust_mean_best"] = trust_mean

    data["trust_by_offset"] = {off: float(d["ctrust"].mean())
                               for off, d in diag_by_offset.items()}

    _apply_sharp_stage(data, cfg)

    return data

_TIER_FLOW   = 0
_TIER_TRUST  = 1
_TIER_FUSION = 2
_TIER_E      = 3

_PARAM_TIER = {
    "_neighbor_offset": _TIER_FLOW,
    "downscale":    _TIER_FLOW,
    "context":  _TIER_FLOW,

    "geo_mismatch":     _TIER_TRUST,
    "geo_softness":      _TIER_TRUST,
    "photo_mismatch":   _TIER_TRUST,
    "photo_radius":  _TIER_TRUST,
    "photo_softness":    _TIER_TRUST,

    "center_weight": _TIER_FUSION,
    "dustA_mismatch":    _TIER_FUSION,
    "dustA_softness":     _TIER_FUSION,

    "dustB_mismatch":      _TIER_FUSION,
    "dustB_softness":       _TIER_FUSION,
    "dustB_disagreement": _TIER_FUSION,
    "dustB_disagreement_softness":  _TIER_FUSION,

    "sharp_base":      _TIER_E,
    "sharp_full":    _TIER_E,
    "sharp_gamma":     _TIER_E,
    "sharp_amount":    _TIER_E,
    "detail_filter": _TIER_E,
    "detail_sigma":  _TIER_E,
    "detail_eps":    _TIER_E,
}

_TIER_EXEMPT_PARAMS = {"mode", "flow_backend"}

_tier_have = set(_PARAM_TIER) - set(_VIEW_ONLY_KEYS)
_tier_want = set(SCENE_PARAMS) - _TIER_EXEMPT_PARAMS
if _tier_have != _tier_want:
    raise KeyError(
        "_PARAM_TIER and SCENE_PARAMS do not agree -- "
        f"no tier for: {sorted(_tier_want - _tier_have)}, "
        f"unknown: {sorted(_tier_have - _tier_want)}")

def dirty_tier(changed_keys):
    tiers = [_PARAM_TIER[k] for k in changed_keys if k in _PARAM_TIER]
    return min(tiers) if tiers else None

def compute_flow_trust(idx, files, cfg, backend=None, active_view=None):
    eff, _want = resolve_backend(cfg, backend)
    return process_frame(idx, files, cfg, eff, active_view=active_view)

def compute_trust(data, cfg):
    return _apply_trust_stage(data, cfg)

def compute_fusion(data, cfg):
    _apply_dustA_stage(data, cfg)
    _apply_dustB_stage(data, cfg)
    _apply_sharp_stage(data, cfg)
    return data

def compute_e(data, cfg):
    _apply_sharp_stage(data, cfg)
    return data

def compute_e_proxy(data, cfg, scale=2):
    base = data.get("fuse_best")
    tmean = data.get("trust_mean_best")
    if base is None or tmean is None:
        return compute_e(data, cfg)

    h, w = base.shape[:2]
    sh, sw = max(8, h // scale), max(8, w // scale)
    small = {
        "fuse_best": cv2.resize(base, (sw, sh), interpolation=cv2.INTER_AREA),
        "trust_mean_best":  cv2.resize(tmean, (sw, sh), interpolation=cv2.INTER_AREA),
    }
    for k in ("fuse_dustA", "trust_mean_dustA", "fuse_dustB", "trust_mean_dustB"):
        if k in data:
            small[k] = cv2.resize(data[k], (sw, sh), interpolation=cv2.INTER_AREA)

    _apply_sharp_stage(small, cfg)

    out = dict(data)
    for k, v in small.items():
        if k in ("fuse_best", "trust_mean_best", "fuse_dustA",
                 "trust_mean_dustA", "fuse_dustB", "trust_mean_dustB"):
            continue
        out[k] = cv2.resize(v, (w, h), interpolation=cv2.INTER_LINEAR)
    return out
