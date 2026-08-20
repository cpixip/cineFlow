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


VERSION = "2.0"

EPS_GUARD = 1e-3

VIDEO_EXTS = (".mov", ".mkv", ".mp4", ".avi")

DEFAULT_CONFIG = {
    "mode": "best",
    "output_dir": "",
    "output_bit_depth": 16,
    "tiff_compression": "none",
    "writer_queue_size": 150,
    "writer_timeout": 0.2,
    "writer_flush_interval": 0,
    "writer_workers": 4,
    "reader_queue_size": 120,
    "reader_timeout": 0.1,
    "reader_workers": 4,

    "downscale": 2.0,
    "flow_backend": "RAFT",

    "raft_fp16": True,
    "raft_iterations": 6,

    "context": 2,
    "geo_mismatch": 1.9,
    "geo_softness": 0.5,
    "photo_mismatch": 0.055,
    "photo_softness": 0.018,
    "photo_radius": 3,

    "center_weight": 1,
    "dustA_mismatch": 3.0,
    "dustA_softness": 1.5,

    "dustB_mismatch": 3.0,
    "dustB_softness": 1.5,

    "dustB_disagreement": 0.02,
    "dustB_disagreement_softness": 0.002,

    "sharp_base": 0.05,
    "sharp_full": 0.034,
    "sharp_gamma": 0.70,
    "sharp_amount": 4.50,
    "detail_filter": "guided",
    "detail_sigma": 0.5,
    "detail_eps": 0.01,
}

MODES = ("copy", "best", "dustA", "dustB")

SCENE_PARAMS = (
    "mode",

    "downscale", "flow_backend",

    "context",
    "geo_mismatch", "geo_softness",
    "photo_mismatch", "photo_softness", "photo_radius",

    "center_weight", "dustA_mismatch", "dustA_softness",

    "dustB_mismatch", "dustB_softness",
    "dustB_disagreement", "dustB_disagreement_softness",

    "sharp_base", "sharp_full", "sharp_gamma", "sharp_amount",
    "detail_filter", "detail_sigma", "detail_eps",
)

RUNTIME_PARAMS = tuple(k for k in DEFAULT_CONFIG if k not in SCENE_PARAMS)

_missing = [k for k in SCENE_PARAMS if k not in DEFAULT_CONFIG]
if _missing:
    raise KeyError(f"SCENE_PARAMS names unknown keys: {_missing}")
