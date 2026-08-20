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


from cineflow_defaults import VERSION as __version__
import argparse
import datetime
import json
import math
import subprocess
import errno
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from queue import Queue, Empty, Full

import numpy as np
import cv2
import tifffile

APP_TAG = f"CINEFLOW v{__version__}"

def _ff(name):
    return cineio.ff(name)

from cineflow_defaults import VIDEO_EXTS
import cineio
from cineio import scene_config_path, safe_name, SCENE_CONFIG_FILENAME
TIFF_EXTS = (".tif", ".tiff")

from cineflow_defaults import DEFAULT_CONFIG, MODES, EPS_GUARD

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

FOLDER_CONFIG_FILENAME = "cineflow_folder.json"

def _check_config_keys(cfg, path):
    unknown = [k for k in cfg if k not in DEFAULT_CONFIG]
    if unknown:
        sys.exit(f"[{APP_TAG}] ERROR: {path} has unknown keys {unknown} -- "
                 f"nothing was processed.\n"
                 f"  an old config? v2 renamed several keys.")

def load_global_config(path, input_path=None):
    cfg = dict(DEFAULT_CONFIG)
    sources = []

    if input_path:
        folder = input_path if os.path.isdir(input_path) \
            else os.path.dirname(input_path)
        fpath = os.path.join(folder, FOLDER_CONFIG_FILENAME)
        if os.path.isfile(fpath):
            try:
                folder_cfg = _load_json(fpath)
            except json.JSONDecodeError as e:
                sys.exit(f"[{APP_TAG}] ERROR: {fpath} is not valid JSON "
                         f"(line {e.lineno}, column {e.colno}): {e.msg}")
            _check_config_keys(folder_cfg, fpath)
            cfg.update(folder_cfg)
            sources.append(FOLDER_CONFIG_FILENAME)

    if path:
        if not os.path.isfile(path):
            sys.exit(f"[{APP_TAG}] ERROR: config file not found: {path}")
        try:
            user_cfg = _load_json(path)
        except json.JSONDecodeError as e:
            sys.exit(f"[{APP_TAG}] ERROR: {path} is not valid JSON "
                      f"(line {e.lineno}, column {e.colno}): {e.msg}")
        _check_config_keys(user_cfg, path)
        cfg.update(user_cfg)
        sources.append("--config")
    cfg["_config_sources"] = sources
    return cfg

def load_scene_config(global_config, scene, forced=False):
    cfg = dict(global_config)

    if forced:
        return cfg

    override_path = scene_config_path(scene.input_path, scene.kind == "tiff_dir")
    if os.path.isfile(override_path):
        try:
            override = _load_json(override_path)
            cfg.update(override)
            unknown = [k for k in override if k not in DEFAULT_CONFIG]
            if unknown:
                print(f"  [config] ERROR: unknown keys {unknown} "
                      f"-- scene skipped")
                print(f"  [config]   an old recipe? v2 renamed several keys "
                      f"-- re-export it from flowQt.")
                return None
        except json.JSONDecodeError as e:
            print(f"  [config] WARNING: {override_path} is not valid JSON "
                  f"(line {e.lineno}, column {e.colno}) -- ignored, global config stays active")
    else:
        src = " + ".join(cfg.get("_config_sources") or []) or "defaults"
        print(f"  [config] no {SCENE_CONFIG_FILENAME} -- using {src} "
              f"({cfg['mode']}, {cfg['flow_backend']}, "
              f"context=+-{cfg['context']})")
    return cfg

class Scene:
    __slots__ = ("kind", "input_path", "rel_path", "name")

    def __init__(self, kind, input_path, rel_path, name):
        self.kind = kind
        self.input_path = input_path
        self.rel_path = rel_path
        self.name = name

    def __repr__(self):
        return f"Scene(kind={self.kind!r}, rel_path={self.rel_path!r})"

def _dir_has_tiffs(path):
    try:
        return any(f.lower().endswith(TIFF_EXTS) for f in os.listdir(path))
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return False

def _dir_has_videos(path):
    try:
        return any(f.lower().endswith(VIDEO_EXTS) for f in os.listdir(path))
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return False

def discover_scenes(input_path):
    if os.path.isfile(input_path):
        if input_path.lower().endswith(VIDEO_EXTS):
            base = os.path.splitext(os.path.basename(input_path))[0]
            return [Scene("video_file", os.path.abspath(input_path), base,
                          base)]
        sys.exit(f"[{APP_TAG}] ERROR: {input_path} is not a video file "
                 f"(expected: {', '.join(VIDEO_EXTS)})")

    if not os.path.isdir(input_path):
        sys.exit(f"[{APP_TAG}] ERROR: {input_path} does not exist.")

    if _dir_has_tiffs(input_path):
        name = os.path.basename(os.path.normpath(input_path))
        return [Scene("tiff_dir", input_path, name, name)]

    scenes = []

    for f in sorted(os.listdir(input_path), key=_numeric_sort_key):
        if f.lower().endswith(VIDEO_EXTS):
            full = os.path.join(input_path, f)
            base = os.path.splitext(f)[0]
            scenes.append(Scene("video_file", full, base, base))

    for entry in sorted(os.listdir(input_path), key=_numeric_sort_key):
        full = os.path.join(input_path, entry)
        if not os.path.isdir(full):
            continue
        if _dir_has_tiffs(full):
            scenes.append(Scene("tiff_dir", full, entry, entry))
        elif _dir_has_videos(full):
            for f in sorted(os.listdir(full), key=_numeric_sort_key):
                if f.lower().endswith(VIDEO_EXTS):
                    base = os.path.splitext(f)[0]
                    scenes.append(Scene("video_file", os.path.join(full, f),
                                        os.path.join(entry, base),
                                        os.path.join(entry, base)))

    if not scenes:
        sys.exit(f"[{APP_TAG}] ERROR: in {input_path} neither TIFFs nor "
                 f"video files found.")

    scenes.sort(key=lambda sc: _numeric_sort_key(sc.name))
    return scenes

_numeric_sort_key = cineio.numeric_sort_key

def list_tiffs(scene_dir):
    files = [os.path.join(scene_dir, f) for f in os.listdir(scene_dir)
             if f.lower().endswith(TIFF_EXTS)]
    return sorted(files, key=_numeric_sort_key)

def source_frame_offset(first_file):
    m = re.search(r"(\d+)\.[^.]+$", os.path.basename(first_file))
    return int(m.group(1)) if m else 0

def _read_sample_shape(f_path):
    try:
        img = tifffile.imread(f_path)
        return img.shape[:2]
    except Exception:
        img = cineio.imread_unicode(f_path, cv2.IMREAD_UNCHANGED)
        return img.shape[:2] if img is not None else None

def resolve_output_root(input_path, out_cli, config):
    if out_cli:
        return out_cli
    cfg_out = config["output_dir"]
    if cfg_out:
        return cfg_out
    in_p = os.path.abspath(input_path)
    base = os.path.dirname(in_p) if os.path.isfile(input_path) else in_p
    return os.path.join(os.path.dirname(base), "Resultate")

def estimate_output_bytes(scenes, config, output_format=None):
    bit = int(config.get("output_bit_depth",
                         DEFAULT_CONFIG["output_bit_depth"]))
    fmt = (output_format or "tiff")
    total = 0
    sicher = True
    zeilen = []
    for sc in scenes:
        if sc.kind == "tiff_dir":
            try:
                files = [os.path.join(sc.input_path, f)
                         for f in os.listdir(sc.input_path)
                         if f.lower().endswith(TIFF_EXTS)]
            except OSError:
                zeilen.append(f"  {sc.name}: not readable -- skipped")
                continue
            if not files:
                continue
            shape = _read_sample_shape(files[0])
            if shape is None:
                zeilen.append(f"  {sc.name}: not readable -- skipped")
                continue
            h, w = shape
            raw = h * w * 3 * (2 if bit == 16 else 1)
            gross = int(len(files) * raw * 1.01)
            total += gross
            zeilen.append(f"  {sc.name}: {len(files)} Frames, "
                          f"~{gross/2**30:.2f} GiB")
        else:
            try:
                ein = os.path.getsize(sc.input_path)
            except OSError:
                continue
            gross = ein * (20 if fmt != "video" else 3)
            total += gross
            sicher = False
            zeilen.append(f"  {sc.name}: video, ~{gross/2**30:.2f} GiB "
                          f"(rough estimate)")
    return total, sicher, zeilen

def check_disk_space(scenes, config, output_root, output_format=None,
                     reserve_frac=0.05, assume_yes=False):
    try:
        frei = shutil.disk_usage(output_root).free
    except OSError as e:
        print(f"  [space] WARNING: cannot determine free space ({e!r}) "
              f"-- check skipped.")
        return True

    noetig, sicher, zeilen = estimate_output_bytes(scenes, config,
                                                   output_format)
    noetig = int(noetig * (1.0 + reserve_frac))
    g = 2 ** 30
    print(f"[space] estimated need: {noetig/g:.2f} GiB"
          f"{'' if sicher else ' (uncertain, video input)'}"
          f" | free on {output_root}: {frei/g:.2f} GiB")
    for z in zeilen:
        print(z)

    if noetig <= frei:
        return True

    fehlt = (noetig - frei) / g
    print(f"[space] SHORT BY ~{fehlt:.2f} GiB.")
    if not sicher:
        print("  The estimate is crude for video input -- it can be off in "
              "either direction.")
    if assume_yes:
        print("  --yes given: the run starts anyway.")
        return True
    try:
        answer = input("  Start anyway? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")

def make_run_dir(output_root, tag=None):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    name = f"{stamp}_{tag}" if tag else stamp
    path = os.path.join(output_root, name)
    if os.path.exists(path):
        for i in range(2, 100):
            alt = f"{path}_{i}"
            if not os.path.exists(alt):
                path = alt
                break
    os.makedirs(path, exist_ok=True)
    return path

def scene_output_dir(run_dir, scene):
    base = scene.rel_path
    if scene.kind == "video_file":
        base = os.path.splitext(base)[0]
    parts = [safe_name(p) for p in base.replace("\\", "/").split("/") if p]
    return os.path.join(run_dir, *parts)

class AsyncTIFFReader:
    def __init__(self, file_list, height, width, start_frame=0, end_frame=None,
                 queue_size=120, read_timeout=0.1, num_workers=4):
        self.file_list = file_list
        self.height = height
        self.width = width
        self.queue = Queue(maxsize=queue_size)
        self.read_timeout = read_timeout
        self.running = True
        self.error = None
        n = len(file_list)
        self.start_frame = max(0, start_frame)
        self.end_frame = end_frame if (end_frame is not None and 0 < end_frame < n) else n - 1
        self.num_workers = max(1, int(num_workers))
        self._thread = None

    def _load(self, f_path):
        img = cineio.load_tiff(f_path, want_float=False)
        div = 65535.0 if img.dtype == np.uint16 else 255.0
        return img.astype(np.float32) / div

    def _push(self, idx, frame):
        while self.running:
            try:
                self.queue.put((idx, frame), timeout=self.read_timeout)
                return True
            except Full:
                continue
        return False

    def _run(self):
        indices = iter(range(self.start_frame, self.end_frame + 1))
        next_to_emit = self.start_frame
        pending = {}
        completed = {}

        try:
            self._run_body(pending, completed, indices, next_to_emit)
        except Exception as e:
            self.error = e

    def _run_body(self, pending, completed, indices, next_to_emit):
        with ThreadPoolExecutor(max_workers=self.num_workers) as pool:
            for _ in range(self.num_workers):
                idx = next(indices, None)
                if idx is None:
                    break
                pending[pool.submit(self._load, self.file_list[idx])] = idx

            while (pending or completed) and self.running:
                while next_to_emit in completed:
                    frame = completed.pop(next_to_emit)
                    if not self._push(next_to_emit, frame):
                        return
                    next_to_emit += 1

                if not pending:
                    break

                done, _ = wait(pending.keys(), timeout=0.5, return_when=FIRST_COMPLETED)
                for fut in done:
                    idx = pending.pop(fut)
                    completed[idx] = fut.result()
                    nxt = next(indices, None)
                    if nxt is not None and self.running:
                        pending[pool.submit(self._load, self.file_list[nxt])] = nxt

    def start(self):
        import threading
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def get_frame(self, timeout=1.5):
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            if self.error is not None:
                raise self.error
            return None, np.zeros((self.height, self.width, 3), dtype=np.float32)

    def stop(self):
        self.running = False
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Empty:
                break
        if self._thread is not None:
            self._thread.join(timeout=5.0)

VIDEO_CODECS = {
    "prores4444": {
        "args": ["-c:v", "prores", "-profile:v", "4",
                 "-pix_fmt", "yuv444p10le", "-vendor", "apl0"],
        "ext": ".mov",
        "note": "ProRes 4444, 'prores' encoder (NOT prores_ks -- measured "
                "worse). DaVinci reads it. Costs 0.077 %.",
    },
    "prores4444xq": {
        "args": ["-c:v", "prores_ks", "-profile:v", "5",
                 "-pix_fmt", "yuv444p10le", "-vendor", "apl0"],
        "ext": ".mov",
        "note": "ProRes 4444 XQ -- highest tier, larger files.",
    },
    "ffv1": {
        "args": ["-c:v", "ffv1", "-level", "3", "-pix_fmt", "gbrp16le"],
        "ext": ".mkv",
        "note": "LOSSLESS (measured bit-identical). BUT: DaVinci does not "
                "read FFV1 -- archival format, not an editing format.",
    },
    "h264": {
        "args": ["-c:v", "libx264", "-preset", "slow", "-crf", "14",
                 "-pix_fmt", "yuv420p"],
        "ext": ".mp4",
        "note": "LOSSY: 8 bit, 4:2:0, possible DC shift. Viewing/sharing "
                "format -- NOT meant for the roundtrip back into DaVinci. "
                "Included deliberately, limits known.",
    },
}

_ffprobe = cineio.ffprobe
_video_fps = cineio.video_fps
_video_frame_count = cineio.video_frame_count

_FORCED_RANGE = [None]

def _guess_range(path, st):
    return cineio.guess_range(path, st, forced=_FORCED_RANGE[0])

class AsyncVideoReader:

    def __init__(self, path, queue_size=60, read_timeout=5.0):
        self.path = path
        self.st = _ffprobe(path)
        self.width = int(self.st["width"])
        self.height = int(self.st["height"])
        self.fps = _video_fps(self.st)
        self.n_frames = _video_frame_count(path, self.st)
        self.color_range = _guess_range(path, self.st)
        self.color_space = self.st.get("color_space") or "bt709"
        if self.color_space in ("unknown", "-"):
            self.color_space = "bt709"
        self.color_trc = self.st.get("color_transfer")
        self.color_prim = self.st.get("color_primaries")

        self.queue = Queue(maxsize=queue_size)
        self.read_timeout = read_timeout
        self.running = True
        self._thread = None
        self._proc = None

    def _cmd(self):
        cmd = [_ff("ffmpeg"), "-nostdin", "-v", "error", "-i", self.path]
        pix = str(self.st.get("pix_fmt", ""))
        if not ("gbr" in pix or "rgb" in pix):
            cmd += ["-vf", f"scale=in_color_matrix={self.color_space}:"
                           f"in_range={self.color_range}:out_range=full"]
        cmd += ["-pix_fmt", "rgb48le", "-f", "rawvideo", "-"]
        return cmd

    def _run(self):
        fb = self.width * self.height * 3 * 2
        self._proc = subprocess.Popen(
            self._cmd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=fb)
        drain = cineio.StderrDrain(self._proc)
        idx = 0
        try:
            while self.running and idx < self.n_frames:
                buf = self._proc.stdout.read(fb)
                if not buf or len(buf) < fb:
                    if idx < self.n_frames and self.running:
                        err = drain.text(400)
                        print(f"\n  [reader] ffmpeg ended early at frame "
                              f"{idx}/{self.n_frames}"
                              + (f":\n{err}" if err.strip() else ""))
                    break
                frame = (np.frombuffer(buf, dtype="<u2")
                         .reshape(self.height, self.width, 3)
                         .astype(np.float32) / 65535.0)
                self.queue.put((idx, frame))
                idx += 1
        except Exception as e:
            print(f"\n  [reader] ERROR: {e!r}")
        finally:
            try:
                self._proc.stdout.close()
            except Exception:
                pass

    def start(self):
        import threading
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def get_frame(self, timeout=None):
        try:
            return self.queue.get(timeout=timeout or self.read_timeout)
        except Empty:
            return None, np.zeros((self.height, self.width, 3), dtype=np.float32)

    def stop(self):
        self.running = False
        try:
            if self._proc:
                self._proc.terminate()
        except Exception:
            pass
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Exception:
                break
        if self._thread is not None:
            self._thread.join(timeout=5.0)

class AsyncVideoWriter:

    def __init__(self, path, codec, width, height, fps=18.0,
                 color_space="bt709", color_trc=None, color_prim=None,
                 color_range="pc", queue_size=60):
        self.path = path
        self.codec = codec
        self.width = width
        self.height = height
        self.fps = fps
        self.color_space = color_space
        self.color_trc = color_trc
        self.color_prim = color_prim
        self.color_range = color_range
        self.queue = Queue(maxsize=queue_size)
        self.running = True
        self._thread = None
        self._proc = None
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _cmd(self):
        spec = VIDEO_CODECS[self.codec]
        cmd = [_ff("ffmpeg"), "-nostdin", "-v", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "rgb48le",
               "-s", f"{self.width}x{self.height}", "-r", f"{self.fps}",
               "-i", "-"]
        if self.codec == "ffv1":
            cmd += spec["args"] + [self.path]
            return cmd

        cmd += ["-vf", f"scale=out_color_matrix={self.color_space}:"
                       f"out_range={self.color_range}"]
        cmd += ["-color_range", self.color_range]
        if self.color_space and self.color_space not in ("unknown", "-"):
            cmd += ["-colorspace", self.color_space]
        if self.color_trc and self.color_trc not in ("unknown", "-"):
            cmd += ["-color_trc", self.color_trc]
        if self.color_prim and self.color_prim not in ("unknown", "-"):
            cmd += ["-color_primaries", self.color_prim]
        cmd += spec["args"] + [self.path]
        return cmd

    def _run(self):
        self._proc = subprocess.Popen(
            self._cmd(), stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        drain = cineio.StderrDrain(self._proc)
        pending = {}
        want = 0
        try:
            while self.running or not self.queue.empty() or pending:
                try:
                    idx, frame = self.queue.get(timeout=0.5)
                except Empty:
                    if not self.running and not pending:
                        break
                    if not self.running and self.queue.empty() and pending:
                        print(f"\n  [writer] STALLED: waiting for frame "
                              f"{want}, buffered: "
                              f"{sorted(pending)[:8]} -- dropping "
                              f"{len(pending)} frame(s), closing file.")
                        pending.clear()
                        break
                    continue
                pending[idx] = frame
                while want in pending:
                    f = pending.pop(want)
                    u16 = np.clip(f * 65535.0, 0, 65535).astype(np.uint16)
                    self._proc.stdin.write(np.ascontiguousarray(u16).tobytes())
                    want += 1
        except BrokenPipeError:
            pass
        except Exception as e:
            print(f"\n  [writer] ERROR: {e!r}")
        finally:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            self._proc.wait()
            if self._proc.returncode != 0:
                print(f"\n  [writer] ffmpeg error:\n{drain.text(400)}")

    def start(self):
        import threading
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def add_frame(self, idx, frame):
        self.queue.put((idx, frame))

    def stop(self):
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=120.0)

class AsyncWriter:
    def __init__(self, output_path, bit_depth=16, queue_size=150, write_timeout=0.2,
                 tiff_compression="none", flush_interval=0, num_workers=4, prefix=None,
                 frame_offset=0):
        self.output_path = output_path
        self.frame_offset = int(frame_offset)
        self.bit_depth = 16 if bit_depth not in (8, 16) else bit_depth
        self.queue = Queue(maxsize=queue_size)
        self.write_timeout = write_timeout
        self.running = True
        comp = str(tiff_compression).lower()
        self._compression = None if comp == "none" else comp
        self._flush_interval = int(flush_interval)
        self.num_workers = max(1, int(num_workers))
        self._thread = None
        self._frames_since_flush = 0
        self._flush_lock = None
        self.prefix = safe_name(prefix) if prefix else "frame"
        os.makedirs(output_path, exist_ok=True)

    def _write_one(self, idx, frame):
        path = os.path.join(self.output_path,
                            f"{self.prefix}_{idx + self.frame_offset:06d}.tiff")
        if self.bit_depth == 16:
            out = np.clip(frame * 65535.0, 0, 65535).astype(np.uint16)
        else:
            out = np.clip(frame * 255.0, 0, 255).astype(np.uint8)
        with open(path, "wb") as fh:
            tifffile.imwrite(fh, out, compression=self._compression, photometric="rgb")
            if self._flush_interval > 0:
                with self._flush_lock:
                    self._frames_since_flush += 1
                    do_flush = self._frames_since_flush >= self._flush_interval
                    if do_flush:
                        self._frames_since_flush = 0
                if do_flush:
                    fh.flush()
                    os.fsync(fh.fileno())
        return idx

    def _run(self):
        pending = set()
        with ThreadPoolExecutor(max_workers=self.num_workers) as pool:
            while self.running or not self.queue.empty() or pending:
                while len(pending) < self.num_workers:
                    try:
                        idx, frame = self.queue.get_nowait()
                    except Empty:
                        break
                    pending.add(pool.submit(self._write_one, idx, frame))

                if not pending:
                    try:
                        idx, frame = self.queue.get(timeout=self.write_timeout)
                        pending.add(pool.submit(self._write_one, idx, frame))
                    except Empty:
                        continue

                done, pending = wait(pending, timeout=self.write_timeout, return_when=FIRST_COMPLETED)
                for fut in done:
                    fut.result()

    def start(self):
        import threading
        self._flush_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def add_frame(self, idx, frame):
        self.queue.put((idx, frame))

    def stop(self):
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=30.0)

_TORCH_OK = None

def _torch_available():
    global _TORCH_OK
    if _TORCH_OK is None:
        try:
            import importlib
            importlib.import_module("torch")
            importlib.import_module("torchvision")
            _TORCH_OK = True
        except Exception:
            _TORCH_OK = False
    return _TORCH_OK

def build_pipeline(config):
    try:
        import torch
        import torchvision.models.optical_flow as tv_of
    except Exception as e:
        sys.exit(f"[{APP_TAG}] ERROR: best/dust need PyTorch + "
                 f"torchvision, import failed: {e!r}\n"
                 f"  (copy runs without torch -- the algorithm modes do not.)")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        print(f"  [pipeline] WARNING: no CUDA GPU found -- running on CPU "
              f"(extremely slow, only meant for testing the logic).")

    weights = tv_of.Raft_Small_Weights.DEFAULT
    model = tv_of.raft_small(weights=weights).to(device).eval()
    model.raft_iterations = int(config["raft_iterations"])
    model.num_flow_updates = model.raft_iterations
    print(f"  [pipeline] RAFT_small loaded ({device}, "
          f"{model.num_flow_updates} iterations, "
          f"FP16={bool(config.get('raft_fp16', True)) and device.type == 'cuda'}).")
    return Pipeline(torch, model, device, config)

class GpuFrameWindow:
    def __init__(self, torch_mod, reader, device, height, width):
        self.torch = torch_mod
        self.reader = reader
        self.device = device
        self.height = height
        self.width = width
        self._resident = {}

    def _upload(self, frame_hwc):
        t = self.torch.from_numpy(np.ascontiguousarray(frame_hwc))
        t = t.permute(2, 0, 1).unsqueeze(0).float()
        return t.to(self.device)

    def ensure(self, idx, frame_hwc):
        if idx not in self._resident:
            self._resident[idx] = self._upload(frame_hwc)
        return self._resident[idx]

    def get(self, idx):
        return self._resident.get(idx)

    def evict_before(self, keep_from):
        for k in [k for k in self._resident if k < keep_from]:
            del self._resident[k]

    def clear(self):
        self._resident.clear()

class Pipeline:
    def __init__(self, torch_mod, model, device, config):
        self.torch = torch_mod
        self.model = model
        self.device = device
        self.config = config
        self.PF = torch_mod.nn.functional
        self.raft_iters = int(config.get(
            "raft_iterations", DEFAULT_CONFIG["raft_iterations"]))

        self.downscale = float(config["downscale"])
        self.raft_fp16 = bool(config["raft_fp16"])
        self.context = int(config["context"])

        self.geo_mismatch = float(config["geo_mismatch"])
        self.geo_softness = float(config["geo_softness"])
        self.photo_mismatch = float(config["photo_mismatch"])
        self.photo_radius = int(config["photo_radius"])
        self.photo_softness = float(config["photo_softness"])

        self.center_weight = int(config["center_weight"])
        self.dustA_mismatch = float(config["dustA_mismatch"])
        self.dustA_softness = float(config["dustA_softness"])
        self.dustB_mismatch = float(config["dustB_mismatch"])
        self.dustB_softness = float(config["dustB_softness"])
        self.dustB_disagreement = float(config["dustB_disagreement"])
        self.dustB_disagreement_softness = float(config["dustB_disagreement_softness"])

        self.sharp_base = float(config["sharp_base"])
        self.sharp_full = float(config["sharp_full"])
        self.sharp_gamma = float(config["sharp_gamma"])
        self.sharp_amount = float(config["sharp_amount"])
        self.detail_filter = str(config["detail_filter"]).lower()
        self._filter_warned = False
        self.detail_sigma = float(config["detail_sigma"])
        self.detail_eps = float(config["detail_eps"])

    def _to_gray(self, rgb):
        return (0.299 * rgb[:, 0:1] + 0.587 * rgb[:, 1:2] + 0.114 * rgb[:, 2:3])

    def _box_blur(self, x, radius):
        k = 2 * radius + 1
        return self.PF.avg_pool2d(x, kernel_size=k, stride=1, padding=radius)

    def _gauss_blur(self, x, radius, sigma=None):
        k = 2 * radius + 1
        if sigma is None:
            sigma = max(k / 6.0, 0.1)
        ax = self.torch.arange(k, device=x.device, dtype=x.dtype) - radius
        g1 = self.torch.exp(-0.5 * (ax / sigma) ** 2)
        g1 = g1 / g1.sum()
        g2 = (g1[:, None] @ g1[None, :]).view(1, 1, k, k)
        c = x.shape[1]
        g2 = g2.expand(c, 1, k, k)
        return self.PF.conv2d(x, g2, padding=radius, groups=c)

    def _guided_gray(self, guide, src, radius, eps):
        mean_I = self._box_blur(guide, radius)
        mean_p = self._box_blur(src, radius)
        corr_I = self._box_blur(guide * guide, radius)
        corr_Ip = self._box_blur(guide * src, radius)
        var_I = corr_I - mean_I * mean_I
        cov_Ip = corr_Ip - mean_I * mean_p
        a = cov_Ip / (var_I + eps)
        b = mean_p - a * mean_I
        mean_a = self._box_blur(a, radius)
        mean_b = self._box_blur(b, radius)
        return mean_a * guide + mean_b

    def _smooth_detail(self, luma):
        r = max(1, int(math.ceil(3.0 * self.detail_sigma)))
        if self.detail_filter == "guided":
            return self._guided_gray(luma, luma, r, self.detail_eps)
        if self.detail_filter != "gauss" and not self._filter_warned:
            self._filter_warned = True
            print(f"  [detail_filter] WARNING: unknown value "
                  f"{self.detail_filter!r} -- continuing with 'gauss' "
                  f"(valid: guided | gauss)")
        return self._gauss_blur(luma, r, sigma=self.detail_sigma)

    def _pyr_down_gpu(self, img, levels):
        if levels <= 0:
            return img
        c = img.shape[1]
        k1d = self.torch.tensor([1., 4., 6., 4., 1.], device=img.device, dtype=img.dtype) / 16.0
        kh = k1d.view(1, 1, 1, 5).repeat(c, 1, 1, 1)
        kv = k1d.view(1, 1, 5, 1).repeat(c, 1, 1, 1)
        out = img
        for _ in range(levels):
            out = self.PF.pad(out, (2, 2, 0, 0), mode='reflect')
            out = self.PF.conv2d(out, kh, groups=c)
            out = self.PF.pad(out, (0, 0, 2, 2), mode='reflect')
            out = self.PF.conv2d(out, kv, groups=c)
            out = out[:, :, ::2, ::2]
        return out

    def _gauss_resample(self, img, factor):
        if factor <= 1.0 + 1e-6:
            return img
        _, c, h, w = img.shape
        sigma = 0.5 * math.sqrt(max(factor * factor - 1.0, 0.0))
        if sigma > 1e-3:
            r = max(1, int(math.ceil(3.0 * sigma)))
            k = 2 * r + 1
            ax = self.torch.arange(k, device=img.device, dtype=img.dtype) - r
            g1 = self.torch.exp(-0.5 * (ax / sigma) ** 2)
            g1 = g1 / g1.sum()
            kh = g1.view(1, 1, 1, k).repeat(c, 1, 1, 1)
            kv = g1.view(1, 1, k, 1).repeat(c, 1, 1, 1)
            img = self.PF.pad(img, (r, r, 0, 0), mode='reflect')
            img = self.PF.conv2d(img, kh, groups=c)
            img = self.PF.pad(img, (0, 0, r, r), mode='reflect')
            img = self.PF.conv2d(img, kv, groups=c)
        nh = max(8, int(round(h / factor)))
        nw = max(8, int(round(w / factor)))
        return self.PF.interpolate(img, size=(nh, nw), mode='bilinear',
                                   align_corners=False)

    def stage_a_flow_prep(self, rgb_full):
        f = self.downscale
        if f <= 1.0 + 1e-6:
            return rgb_full
        levels = int(math.floor(math.log2(f)))
        out = self._pyr_down_gpu(rgb_full, levels)
        rest = f / (2 ** levels)
        return self._gauss_resample(out, rest)

    def _raft_prepare(self, rgb_down):
        _, _, h, w = rgb_down.shape
        ph = (8 - h % 8) % 8
        pw = (8 - w % 8) % 8
        t = rgb_down * 2.0 - 1.0
        if ph or pw:
            t = self.PF.pad(t, (0, pw, 0, ph), mode='replicate')
        return t, h, w

    def stage_b_flow(self, prep_from, prep_to, full_h, full_w):
        t_from, dh, dw = self._raft_prepare(prep_from)
        t_to, _, _ = self._raft_prepare(prep_to)
        use_amp = self.raft_fp16 and self.device.type == "cuda"
        with self.torch.inference_mode():
            with self.torch.autocast(device_type="cuda", enabled=use_amp):
                flow = self.model(
                    t_from, t_to,
                    num_flow_updates=self.raft_iters)[-1]
        flow = flow[:, :, :dh, :dw]
        if (dh, dw) != (full_h, full_w):
            sx = float(full_w) / float(dw)
            sy = float(full_h) / float(dh)
            flow = self.PF.interpolate(flow, size=(full_h, full_w),
                                       mode='bilinear', align_corners=False)
            flow = flow.clone()
            flow[:, 0] *= sx
            flow[:, 1] *= sy
        return flow

    def _warp(self, img, flow):
        _, _, h, w = img.shape
        grid_y, grid_x = self.torch.meshgrid(
            self.torch.linspace(-1.0, 1.0, h, device=img.device, dtype=img.dtype),
            self.torch.linspace(-1.0, 1.0, w, device=img.device, dtype=img.dtype),
            indexing='ij')
        base = self.torch.stack((grid_x, grid_y), dim=-1).unsqueeze(0)
        norm_flow = self.torch.stack(
            (flow[:, 0] * 2.0 / max(w - 1, 1),
             flow[:, 1] * 2.0 / max(h - 1, 1)), dim=-1)
        grid = base + norm_flow
        return self.PF.grid_sample(img, grid, mode='bilinear',
                                   padding_mode='reflection', align_corners=True)

    def sigmoid_trust(self, err, mismatch, softness):
        raw = 1.0 - self.torch.sigmoid((err - mismatch) / softness)
        raw0 = 1.0 - 1.0 / (1.0 + math.exp(mismatch / softness))
        return self.torch.clamp(raw / max(raw0, 1e-12), 0.0, 1.0)

    def _geometric_trust(self, resid):
        error = self.torch.linalg.vector_norm(resid, dim=1, keepdim=True)
        error = self.torch.clamp(error, 0.0, 15.0)
        return self.sigmoid_trust(error, self.geo_mismatch, self.geo_softness)

    def _photometric_trust(self, warped, frame_0):
        dev = self.torch.abs(warped - frame_0).mean(dim=1, keepdim=True)
        smooth = self._box_blur(dev, self.photo_radius)
        return self.sigmoid_trust(smooth, self.photo_mismatch, self.photo_softness)

    def stage_c_trust(self, data):
        f0 = data["frame_0"]
        _, _, H, W = f0.shape
        prep = data["flow_prep"]
        pairs = {}
        for off in data["neighbor_offsets"]:
            flow_fwd = self.stage_b_flow(prep[0], prep[off], H, W)
            flow_bwd = self.stage_b_flow(prep[off], prep[0], H, W)
            warped_frame = self._warp(data["neighbors"][off], flow_fwd)
            warped_flow_bw = self._warp(flow_bwd, flow_fwd)
            resid = flow_fwd + warped_flow_bw
            gtrust = self._geometric_trust(resid)
            ptrust = self._photometric_trust(warped_frame, f0)
            ctrust = gtrust * ptrust
            pairs[off] = {"flow_fwd": flow_fwd, "warped_frame": warped_frame,
                          "gtrust": gtrust, "ptrust": ptrust, "trust": ctrust}
        data["pairs"] = pairs
        return data

    def dispatch_best(self, data):
        f0 = data["frame_0"]
        pairs = data["pairs"]
        num = f0.clone()
        den = self.torch.ones_like(f0[:, 0:1])
        trust_list = []
        for off, d in pairs.items():
            ct = d["trust"]
            num = num + d["warped_frame"] * ct
            den = den + ct
            trust_list.append(ct)
        data["base"] = num / den
        if trust_list:
            data["trust_mean"] = self.torch.stack(trust_list, dim=0).mean(dim=0)
        else:
            data["trust_mean"] = self.torch.zeros_like(f0[:, 0:1])
        return data

    def _median0(self, stack):
        k = stack.shape[0]
        srt, _ = self.torch.sort(stack, dim=0)
        if k % 2:
            return srt[k // 2:k // 2 + 1]
        return (srt[k // 2 - 1:k // 2] + srt[k // 2:k // 2 + 1]) * 0.5

    def dispatch_dustA(self, data):
        f0 = data["frame_0"]
        pairs = data["pairs"]
        warped = [d["warped_frame"] for d in pairs.values()]
        gtrusts = [d["gtrust"] for d in pairs.values()]
        if not warped:
            data["base"] = f0.clone()
            data["trust_mean"] = self.torch.zeros_like(f0[:, 0:1])
            return data

        fw = max(1, self.center_weight)
        stack = self.torch.cat([f0] * fw + warped, dim=0)
        median_img = self._median0(stack)
        dev = self.torch.abs(stack - median_img).mean(dim=1, keepdim=True)
        mad = self._median0(dev)

        def outlier_trust(dev_member):
            score = dev_member / (mad[0] + EPS_GUARD)
            return self.sigmoid_trust(score, self.dustA_mismatch, self.dustA_softness)

        f0_trust = outlier_trust(dev[0:1])
        grp_trusts = [outlier_trust(dev[fw + i:fw + i + 1]) for i in range(len(warped))]

        num = f0 * f0_trust
        den = f0_trust.clone()
        ctg_list = []
        for wf, gt, pgt in zip(warped, gtrusts, grp_trusts):
            ctg = gt * pgt
            ctg_list.append(ctg)
            num = num + wf * ctg
            den = den + ctg
        den = self.torch.clamp(den, 1e-4, None)
        data["base"] = self.torch.clamp(num / den, 0.0, 1.0)
        data["trust_mean"] = self.torch.stack(ctg_list, dim=0).mean(dim=0) if ctg_list \
            else self.torch.zeros_like(f0[:, 0:1])
        return data

    def dispatch_dustB(self, data):
        f0 = data["frame_0"]
        pairs = data["pairs"]
        warped = [d["warped_frame"] for d in pairs.values()]
        gtrusts = [d["gtrust"] for d in pairs.values()]
        if not warped:
            data["base"] = f0.clone()
            data["trust_mean"] = self.torch.zeros_like(f0[:, 0:1])
            return data

        stack = self.torch.cat(warped, dim=0)
        median_nb = self._median0(stack)
        dev_nb = self.torch.abs(stack - median_nb).mean(dim=1, keepdim=True)
        disp = self._median0(dev_nb)

        resid = self.torch.abs(f0 - median_nb).mean(dim=1, keepdim=True)

        score = resid / (disp + EPS_GUARD)
        t_center = self.sigmoid_trust(score, self.dustB_mismatch, self.dustB_softness)
        committee_ok = self.sigmoid_trust(disp, self.dustB_disagreement,
                                           self.dustB_disagreement_softness)

        f0_trust = self.torch.clamp(
            1.0 - (1.0 - t_center) * committee_ok, 0.0, 1.0)

        def outlier_trust(dev_member):
            sc = dev_member / (disp + EPS_GUARD)
            return self.sigmoid_trust(sc, self.dustB_mismatch, self.dustB_softness)

        grp_trusts = [outlier_trust(dev_nb[i:i + 1]) for i in range(len(warped))]

        num = f0 * f0_trust
        den = f0_trust.clone()
        ctg_list = []
        for wf, gt, pgt in zip(warped, gtrusts, grp_trusts):
            ctg = gt * pgt
            ctg_list.append(ctg)
            num = num + wf * ctg
            den = den + ctg
        den = self.torch.clamp(den, 1e-4, None)
        data["base"] = self.torch.clamp(num / den, 0.0, 1.0)
        data["trust_mean"] = self.torch.stack(ctg_list, dim=0).mean(dim=0) if ctg_list \
            else self.torch.zeros_like(f0[:, 0:1])
        return data

    def stage_e_enhance(self, data):
        base = data["base"]
        trust_mean = data["trust_mean"]
        luma = self._to_gray(base)

        r = 4
        mean = self._gauss_blur(luma, r)
        mean_sq = self._gauss_blur(luma * luma, r)
        var = self.torch.clamp(mean_sq - mean * mean, min=0.0)
        texture = self.torch.sqrt(var)

        t = self.torch.clamp(texture / self.sharp_full, 0.0, 1.0) ** self.sharp_gamma
        tex_w = self.sharp_base + (1.0 - self.sharp_base) * t
        sharp_gate_w = tex_w * trust_mean

        luma_smooth = self._smooth_detail(luma)
        detail = luma - luma_smooth

        sharp = base + detail * self.sharp_amount * sharp_gate_w
        data["output"] = self.torch.clamp(sharp, 0.0, 1.0)

        return data

    def process_frame(self, window, mode):
        data = {
            "frame_0": window["frame_0"],
            "neighbors": window["neighbors"],
            "neighbor_offsets": window["neighbor_offsets"],
        }
        flow_prep = {0: self.stage_a_flow_prep(window["frame_0"])}
        for off in window["neighbor_offsets"]:
            flow_prep[off] = self.stage_a_flow_prep(window["neighbors"][off])
        data["flow_prep"] = flow_prep

        self.stage_c_trust(data)

        if mode == "dustA":
            self.dispatch_dustA(data)
        elif mode == "dustB":
            self.dispatch_dustB(data)
        else:
            self.dispatch_best(data)

        self.stage_e_enhance(data)
        return data["output"]

RECORD_NAME = "cineflow_run.json"

def _record_path(out_path):
    if os.path.isdir(out_path):
        return os.path.join(out_path, RECORD_NAME)
    base = os.path.splitext(out_path)[0]
    return f"{base}_{RECORD_NAME}"

def _read_input_chain(input_path):
    if os.path.isdir(input_path):
        d, stem = input_path, ""
    else:
        d = os.path.dirname(input_path)
        stem = os.path.splitext(os.path.basename(input_path))[0] + "_"

    best = os.path.join(d, f"{stem}{RECORD_NAME}") if stem \
        else os.path.join(d, RECORD_NAME)
    if not os.path.isfile(best):
        return [], 1
    try:
        with open(best) as fh:
            doc = json.load(fh)
    except Exception as e:
        print(f"  [config] WARNING: Vorgaenger-Protokoll {os.path.basename(best)} "
              f"not readable ({e!r}) -- Kette beginnt neu bei 1.")
        return [], 1
    kette = doc.get("_chain")
    if not isinstance(kette, list) or not kette:
        return [], 1
    print(f"  [config] predecessor detected: {os.path.basename(best)} "
          f"({len(kette)} run(s)) -- this becomes run "
          f"{len(kette) + 1}.")
    return kette, len(kette) + 1

def _write_resolved(out_path, config, scene, runner=None,
                    frames=None, fps=None, seconds=None):
    from cineflow_defaults import SCENE_PARAMS, RUNTIME_PARAMS

    kette, n = _read_input_chain(scene.input_path)

    schritt = {
        "run": n,
        "cineflow": APP_TAG,
        "source": scene.input_path,
        "scene": scene.name,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "frames": frames,
        "fps": round(fps, 3) if fps else None,
        "seconds": round(seconds, 1) if seconds else None,
        "params": {k: config[k] for k in SCENE_PARAMS if k in config},
        "runner": runner or {},
    }
    kette = list(kette) + [schritt]

    doc = {
        "_run": {
            "cineflow": APP_TAG,
            "run": n,
            "runs_total": len(kette),
            "source": scene.input_path,
            "origin": kette[0].get("source"),
            "scene": scene.name,
            "frames": frames,
            "fps": round(fps, 3) if fps else None,
            "seconds": round(seconds, 1) if seconds else None,
            "time": schritt["time"],
        },
        "_chain": kette,
        "_runner": runner or {},
    }
    for k in SCENE_PARAMS:
        if k in config:
            doc[k] = config[k]
    doc["_runtime"] = {k: config[k] for k in RUNTIME_PARAMS if k in config}

    path = _record_path(out_path)
    try:
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
        print(f"  [config] run log -> {os.path.basename(path)}"
              + (f"  (chain: {len(kette)} runs)" if len(kette) > 1 else ""))
    except Exception as e:
        print(f"  [config] WARNING: could not write {path}: {e!r}")

class _Progress:

    def __init__(self, mode, n, every):
        self.mode = mode
        self.n = n
        self.every = max(1, int(every))
        self.t0 = time.time()
        self.t_steady = None

    def update(self, win):
        if win == 0:
            self.t_steady = time.time()
        if (win + 1) % self.every and win != self.n - 1:
            return
        elapsed = time.time() - self.t0
        if self.t_steady is not None and win > 0:
            fps = win / (time.time() - self.t_steady)
        else:
            fps = (win + 1) / elapsed if elapsed > 0 else 0.0
        pct = (win + 1) / self.n * 100
        eta = (str(datetime.timedelta(seconds=int((self.n - win - 1) / fps)))
               if fps > 0 else "?")
        print(f"\r  [{self.mode}] {pct:5.1f}% | Frame {win+1}/{self.n} | "
              f"{fps:.2f} fps | ETA: {eta}   ", end="", flush=True)

    def finish(self):
        print()
        total = time.time() - self.t0
        steady = ((self.n - 1) / (time.time() - self.t_steady)
                  if (self.t_steady is not None and self.n > 1
                      and time.time() > self.t_steady) else 0.0)
        wall = self.n / total if total > 0 else 0.0
        return total, steady, wall

def _finish_run(out_dir, config, scene, st, n, total, fps):
    _write_resolved(out_dir, config, scene, st,
                    frames=n, fps=fps, seconds=total)
    return {"out": out_dir, "frames": n, "fps": fps, "seconds": total,
            "runner": st}

def run_copy(scene, config, run_dir, force_format=None,
             video_codec="prores4444"):
    reader, writer, meta = open_scene_io(scene, config, run_dir,
                                         force_format, video_codec)
    if reader is None:
        print(f"  [copy] WARNING: {scene.name} not readable, skipped")
        return None

    n = meta["n"]
    out_dir = meta["out"]
    kind = "video" if meta["fmt"] == "video" else "TIFF"
    print(f"  [copy] {scene.name}: {n} frames, "
          f"{meta['width']}x{meta['height']} ({kind}) -> {out_dir}")

    reader.start()
    writer.start()
    prog = _Progress("copy", n, every=50)
    for i in range(n):
        idx, frame = reader.get_frame()
        if idx is None:
            idx = i
        writer.add_frame(idx, frame)
        prog.update(i)
    reader.stop()
    writer.stop()
    total, _steady, _wall = prog.finish()
    print(f"  [copy] done: {n} frames in {total:.1f}s")
    _write_resolved(out_dir, config, scene, frames=n)
    return {"out": out_dir, "frames": n, "fps": n / total if total else None,
            "seconds": total}

def open_scene_io(scene, config, run_dir, force_format=None,
                  video_codec="prores4444"):
    fmt = force_format or ("video" if scene.kind == "video_file" else "tiff")

    if scene.kind == "video_file":
        try:
            reader = AsyncVideoReader(scene.input_path,
                                      queue_size=config["reader_queue_size"])
        except (ValueError, OSError, subprocess.SubprocessError) as e:
            print(f"  [scene] WARNING: {scene.name} not probeable "
                  f"({e}) -- skipped")
            return None, None, None
        n, h, w = reader.n_frames, reader.height, reader.width
        src_meta = dict(fps=reader.fps, color_space=reader.color_space,
                        color_trc=reader.color_trc,
                        color_prim=reader.color_prim,
                        color_range=reader.color_range)
    else:
        files = list_tiffs(scene.input_path)
        if not files:
            return None, None, None
        sample = _read_sample_shape(files[0])
        if sample is None:
            return None, None, None
        h, w = sample
        n = len(files)
        reader = AsyncTIFFReader(files, h, w,
                                 queue_size=config["reader_queue_size"],
                                 read_timeout=config["reader_timeout"],
                                 num_workers=config["reader_workers"])
        src_meta = dict(fps=18.0, color_space="bt709", color_trc=None,
                        color_prim=None, color_range="pc")

    if fmt == "video":
        spec = VIDEO_CODECS[video_codec]
        out = scene_output_dir(run_dir, scene) + spec["ext"]
        writer = AsyncVideoWriter(out, video_codec, w, h,
                                  fps=src_meta["fps"],
                                  color_space=src_meta["color_space"],
                                  color_trc=src_meta["color_trc"],
                                  color_prim=src_meta["color_prim"],
                                  color_range=src_meta["color_range"],
                                  queue_size=config["writer_queue_size"])
    else:
        out = scene_output_dir(run_dir, scene)
        frame_offset = source_frame_offset(files[0])
        writer = AsyncWriter(out, prefix=scene.name,
                             bit_depth=config["output_bit_depth"],
                             queue_size=config["writer_queue_size"],
                             write_timeout=config["writer_timeout"],
                             tiff_compression=config["tiff_compression"],
                             flush_interval=config["writer_flush_interval"],
                             num_workers=config["writer_workers"],
                             frame_offset=frame_offset)

    return reader, writer, {"n": n, "height": h, "width": w, "out": out,
                            "fmt": fmt, "codec": video_codec}

def run_cpu_scene(scene, config, run_dir,
                  force_format=None, video_codec="prores4444"):
    import flowcore as fcore

    reader, writer, meta = open_scene_io(scene, config, run_dir,
                                         force_format, video_codec)
    if reader is None:
        print(f"  [{config['mode']}] WARNING: {scene.name} not readable "
              f"-- skipped")
        return None

    n = meta["n"]
    out_dir = meta["out"]
    mode = str(config["mode"])
    radius = int(config["context"])
    eff, want = fcore.resolve_backend(config, None)

    kind = "video" if meta["fmt"] == "video" else "TIFF"
    print(f"  [{mode}] {n} frames, {meta['width']}x{meta['height']} ({kind}) "
          f"| CPU path (flowcore), flow={eff}, context=+-{radius}")
    if eff != want:
        why = fcore.backend_reason(want) or "not available on this machine"
        print(f"  [{mode}] NOTE: recipe says {want}, running {eff} "
              f"({why}) -- the result differs from the recipe.")
    print(f"  [{mode}] -> {out_dir}")

    writer.start()

    reader.stop()
    try:
        source = fcore.open_source(scene.input_path)
    except Exception as e:
        writer.stop()
        print(f"  [{mode}] ERROR: {scene.input_path} not readable: {e!r}")
        return None
    n = min(n, len(source))

    try:
        return _run_cpu_body(scene, config, out_dir, source, writer, mode, n,
                             eff, want)
    finally:
        try:
            source.close()
        except Exception:
            pass
        try:
            writer.stop()
        except Exception:
            pass

def _run_cpu_body(scene, config, out_dir, source, writer, mode, n, eff, want):
    import flowcore as fcore
    cfg_run = dict(config)
    cfg_run["_need_dustA"] = (mode == "dustA")
    cfg_run["_need_dustB"] = (mode == "dustB")

    prog = _Progress(mode, n, every=10)

    for win in range(n):
        data = fcore.compute_flow_trust(win, source, cfg_run, backend=eff)
        key = {"dustA": "output_dustA", "dustB": "output_dustB"}.get(mode, "output_best")
        img = data.get(key)
        if img is None:
            img = data.get("output_best")
        if img is None:
            img = data["input"]
        writer.add_frame(win, np.clip(img, 0.0, 1.0).astype(np.float32))
        prog.update(win)

    total, _steady_fps, wall_fps = prog.finish()
    writer.stop()
    print(f"  [{mode}] done: {n} frames in {total:.1f}s ({wall_fps:.2f} fps)")

    st = {"path": "cpu/flowcore", "flow": eff}
    if eff != want:
        st["note"] = f"recipe said {want}, computed {eff}"
    return _finish_run(out_dir, config, scene, st, n, total, wall_fps)

def run_pipeline_scene(scene, config, run_dir, pipeline,
                       force_format=None, video_codec="prores4444"):
    reader, writer, meta = open_scene_io(scene, config, run_dir,
                                         force_format, video_codec)
    if reader is None:
        print(f"  [{config['mode']}] WARNING: {scene.name} not readable "
              f"-- skipped")
        return None

    n = meta["n"]
    height, width = meta["height"], meta["width"]
    out_dir = meta["out"]
    mode = str(config["mode"])
    radius = int(config["context"])
    fscale = float(config["downscale"])

    kind = "Video" if meta["fmt"] == "video" else "TIFF"
    print(f"  [{mode}] {n} frames, {width}x{height} ({kind}) | "
          f"downscale={fscale:.2f} | "
          f"context=+-{radius} ({2*2*radius} flow calls/frame)")

    import flowcore as _fc
    _want = str(config.get("flow_backend", "RAFT"))
    _lo = _fc.min_flow_div(_want, width, height)
    if fscale < _lo - 1e-6:
        print(f"  [{mode}] WARNING: downscale={fscale:.2f} is below the limit "
              f"{_lo:.2f} for {_fc.backend_label(_want)} at {width}x{height}.")
        print(f"  [{mode}]   ({width*height/max(fscale,1e-6)**2/1e6:.2f} Mpx "
              f"input vs. {_fc.BACKENDS[_want].max_pixels/1e6:.2f} Mpx budget "
              f"-- expect an out-of-memory abort.)")
        print(f"  [{mode}]   Raise downscale in the recipe, or run this scene "
              f"with flow_backend DIS.")
    if meta["fmt"] == "video":
        print(f"  [{mode}] Codec: {meta['codec']}")
    print(f"  [{mode}] -> {out_dir}")

    reader.start()
    writer.start()
    try:
        return _run_pipeline_body(scene, config, out_dir, pipeline,
                                  reader, writer, mode, n, height, width,
                                  radius)
    finally:
        try:
            reader.stop()
        except Exception:
            pass
        try:
            writer.stop()
        except Exception:
            pass

def _run_pipeline_body(scene, config, out_dir, pipeline, reader, writer,
                       mode, n, height, width, radius):
    torch = pipeline.torch
    window = GpuFrameWindow(torch, reader, pipeline.device, height, width)

    cpu_buffer = {}
    next_read = 0

    READ_TRY, READ_TRIES = 1.5, 20

    def pull_until(idx_needed):
        nonlocal next_read
        while next_read <= idx_needed and next_read < n:
            for _ in range(READ_TRIES):
                r_idx, frame = reader.get_frame(timeout=READ_TRY)
                if r_idx is not None:
                    break
            else:
                raise RuntimeError(
                    f"reader stalled at frame {next_read} of {n} "
                    f"(no data for {READ_TRY * READ_TRIES:.0f} s) -- "
                    f"slow or unavailable input storage?")
            cpu_buffer[r_idx] = frame
            next_read = r_idx + 1

    prog = _Progress(mode, n, every=25)

    for win in range(n):
        lo = max(0, win - radius)
        hi = min(n - 1, win + radius)
        pull_until(hi)

        for j in range(lo, hi + 1):
            if j in cpu_buffer:
                window.ensure(j, cpu_buffer[j])
        window.evict_before(lo)
        for j in list(cpu_buffer):
            if j < lo:
                del cpu_buffer[j]

        neighbors = {}
        offsets = []
        for off in range(-radius, radius + 1):
            if off == 0:
                continue
            j = win + off
            if 0 <= j < n and window.get(j) is not None:
                neighbors[off] = window.get(j)
                offsets.append(off)
        if window.get(win) is None:
            raise RuntimeError(f"frame {win} missing from the GPU window "
                               f"-- buffer/reader out of sync")
        win_data = {
            "frame_0": window.get(win),
            "neighbors": neighbors,
            "neighbor_offsets": sorted(offsets),
        }

        result_gpu = pipeline.process_frame(win_data, mode)
        result_np = result_gpu.squeeze(0).permute(1, 2, 0).contiguous().cpu().numpy()
        writer.add_frame(win, result_np)
        prog.update(win)

    total, steady_fps, wall_fps = prog.finish()
    window.clear()
    reader.stop()
    writer.stop()
    print(f"  [{mode}] done: {n} frames in {total:.1f}s "
          f"({steady_fps:.2f} fps steady, {wall_fps:.2f} fps wall)")

    st = {"path": "gpu/torch", "flow": str(config.get("flow_backend", "RAFT"))}
    return _finish_run(out_dir, config, scene, st, n, total, steady_fps)

def _print_summary(rows, elapsed, skipped=()):
    NW = 18
    COLS = (("scene", NW, "<"), ("mode", 6, "<"), ("downscale", 9, ">"),
            ("context", 7, ">"), ("frames", 7, ">"), ("fps", 6, ">"))
    WIDTH = 2 + sum(w for _, w, _ in COLS) + (len(COLS) - 1) + 1 + NW
    RULE = "=" * WIDTH
    THIN = "-" * WIDTH

    def _fit(s, w=NW):
        s = str(s)
        if len(s) <= w:
            return s
        keep = w - 3
        a = (keep + 1) // 2
        b = keep - a
        return s[:a] + "..." + (s[-b:] if b else "")

    print("\n" + RULE)
    if not rows:
        print(f"  {APP_TAG}  --  no scene processed"
              f"{f', {len(skipped)} skipped' if skipped else ''}.")
        for nm in skipped:
            print(f"  skipped: {_fit(nm, NW)}")
        print(RULE)
        return
    print(f"  {APP_TAG}  --  {len(rows)} scene(s) in "
          f"{datetime.timedelta(seconds=int(elapsed))}"
          f"{f', {len(skipped)} skipped' if skipped else ''}")
    print(RULE)

    head = "  " + " ".join(f"{name:{al}{w}}" for name, w, al in COLS) + "  output"
    print(head)
    print(THIN)
    for r in rows:
        fps = f"{r['fps']:.2f}" if r.get("fps") else "  -  "
        n   = str(r.get("frames", "-"))
        lvl = f"{r.get('scale', 0):.2f}"
        rad = f"+-{r.get('radius','-')}"
        out = os.path.basename(r.get("out") or "-")
        cells = (_fit(r["name"], NW), r["mode"], lvl, rad, n, fps)
        line = "  " + " ".join(f"{c:{al}{w}}" for c, (_, w, al) in zip(cells, COLS))
        print(f"{line}  {_fit(out, NW)}")
    for nm in skipped:
        cells = (_fit(nm, NW), "-", "", "", "", "")
        line = "  " + " ".join(f"{c:{al}{w}}"
                               for c, (_, w, al) in zip(cells, COLS))
        print(f"{line}  (skipped)")
    tot = sum(r.get("frames", 0) for r in rows)
    if tot:
        print(THIN)
        tcells = ("total", "", "", "", str(tot), f"{tot/elapsed:.2f}")
        print("  " + " ".join(f"{c:{al}{w}}"
                              for c, (_, w, al) in zip(tcells, COLS)))
    print(RULE)

def parse_cli(argv):
    ap = argparse.ArgumentParser(description=f"{APP_TAG} -- batch processing")
    ap.add_argument("input", help="Input path: video, TIFF folder, or "
                                   "parent folder holding several scene sub-folders")
    ap.add_argument("output", nargs="?", default=None,
                     help="Output root folder (optional, otherwise from config/default)")
    ap.add_argument("--config", default=None,
                    help="Global JSON config. Scene-local cineflow.json "
                         "still overrides it.")
    ap.add_argument("--video-codec", default="prores4444",
                    choices=sorted(VIDEO_CODECS),
                    help="Codec for video OUTPUT. prores4444 = DaVinci reads "
                         "it, costs 0.077 %%. ffv1 = lossless, but DaVinci "
                         "does NOT read it.")
    ap.add_argument("--video-range", default=None, choices=["pc", "tv"],
                    help="Force the range of INPUT videos. pc = full "
                         "(DaVinci: 'Data Levels: Full'), tv = limited. "
                         "DaVinci does NOT tag the range -- without this "
                         "option it is measured, and that can go wrong on "
                         "flat material.")
    ap.add_argument("--output-format", default=None, choices=["tiff", "video"],
                    help="Force the output format. Default: follows the input "
                         "(TIFF dir -> TIFFs, video file -> video).")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="Answer prompts (e.g. not enough disk space) "
                         "with yes -- for script/batch use where "
                         "no input is possible.")
    ap.add_argument("--tag", default=None,
                    help="Descriptive suffix for the run directory, e.g. "
                         "2026-07-12_1834_texref-sweep")
    ap.add_argument("--force-config", default=None, metavar="JSON",
                    help="FORCE this config -- scene-local cineflow.json files "
                         "are IGNORED. For A/B tests of several parameter "
                         "sets on the same frames -- no duplication needed, "
                         "the output folders get a counter suffix anyway.")
    return ap.parse_args(argv)

def main(argv=None):
    args = parse_cli(argv if argv is not None else sys.argv[1:])

    forced = args.force_config is not None
    config = load_global_config(args.force_config if forced else args.config,
                                input_path=args.input)
    output_root = resolve_output_root(args.input, args.output, config)

    print("=" * 68)
    print(f"  {APP_TAG}")
    print(f"  input:   {args.input}")
    print(f"  output:  {output_root}")
    if os.path.isfile(os.path.join(
            args.input if os.path.isdir(args.input)
            else os.path.dirname(args.input), FOLDER_CONFIG_FILENAME)):
        print(f"  config:  {FOLDER_CONFIG_FILENAME} (applies to every scene)")
    if forced:
        print(f"  ERZWUNGENE Config: {args.force_config}")
        print(f"  (scene-local {SCENE_CONFIG_FILENAME} files are IGNORED)")

    if args.video_range:
        _FORCED_RANGE[0] = args.video_range
        print(f"  Video-Range ERZWUNGEN: {args.video_range}")

    run_dir = make_run_dir(output_root, args.tag)
    print(f"  run:     {os.path.basename(run_dir)}/")
    print("=" * 68)

    try:
        scenes = discover_scenes(args.input)
    except FileNotFoundError as e:
        sys.exit(f"[{APP_TAG}] ERROR: {e}")

    print(f"[scenes] {len(scenes)} scene(s) found")

    if not check_disk_space(scenes, config, output_root,
                            args.output_format, assume_yes=args.yes):
        try:
            os.rmdir(run_dir)
        except OSError:
            pass
        sys.exit(f"[{APP_TAG}] aborted -- not enough disk space.")

    _loaded = {"model": None, "torch": None, "device": None}

    def get_pipeline(scene_cfg):
        if _loaded["model"] is None:
            p = build_pipeline(scene_cfg)
            _loaded["model"] = p.model
            _loaded["torch"] = p.torch
            _loaded["device"] = p.device
            return p
        return Pipeline(_loaded["torch"], _loaded["model"], _loaded["device"], scene_cfg)

    t_batch = time.time()
    summary = []
    skipped = []

    for i, scene in enumerate(scenes):
        print(f"\n[{i+1}/{len(scenes)}] {scene.name}  ({scene.kind})")
        scene_cfg = load_scene_config(config, scene, forced=forced)
        if scene_cfg is None:
            skipped.append(scene.name)
            continue
        mode = str(scene_cfg["mode"])
        result = None
        import flowcore as fcore

        _fb = str(scene_cfg.get("flow_backend", fcore.DEFAULT_BACKEND))
        if _fb not in fcore.ALL_BACKENDS:
            print(f"  [scene] WARNING: unknown flow_backend '{_fb}' -- skipped "
                  f"(valid: {' | '.join(fcore.ALL_BACKENDS)})")
            skipped.append(scene.name)
            continue
        if mode == "copy":
            result = run_copy(scene, scene_cfg, run_dir,
                             args.output_format, args.video_codec)
        elif mode in ("best", "dustA", "dustB"):
            want = str(scene_cfg.get("flow_backend", "RAFT"))
            import flowcore as _fc
            try:
                if not _fc.backend_is_gpu(want) or not _torch_available():
                    result = run_cpu_scene(scene, scene_cfg, run_dir,
                                           args.output_format,
                                           args.video_codec)
                else:
                    pipeline = get_pipeline(scene_cfg)
                    result = run_pipeline_scene(scene, scene_cfg, run_dir,
                                                pipeline, args.output_format,
                                                args.video_codec)
            except Exception as e:
                print(f"  [{mode}] ERROR: {type(e).__name__}: {e}")
                print(f"  [{mode}] scene aborted -- continuing with the "
                      f"next one.")
                result = None
                skipped.append(scene.name)
        else:
            print(f"  [scene] WARNING: unknown mode '{mode}' -- skipped "
                  f"(valid: {' | '.join(MODES)})")
            skipped.append(scene.name)
        if result:
            result.update({"name": scene.name, "mode": mode,
                           "scale": scene_cfg["downscale"],
                           "radius": scene_cfg["context"]})
            summary.append(result)

    _print_summary(summary, time.time() - t_batch, skipped)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print(f"[{APP_TAG}] aborted by user (Ctrl+C).")
        print(f"[{APP_TAG}] Partial output stays where it is.")
        sys.exit(130)
