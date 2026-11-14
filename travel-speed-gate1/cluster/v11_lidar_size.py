#!/usr/bin/env python3
"""
T1 v1.1 refresh (13 Nov 2026, #135-136): how much NEW lidar would
t2_lidarveg.py download for the rebuilt segments? Lists the EPT blocks
under the walked trails (as t2_lidarveg.py does) and counts the ones not
yet in cache/ept/<project>/. Reads only the small EPT metadata (ept.json,
hierarchy files); downloads no point data.
Run:  python cluster/v11_lidar_size.py <region> ...
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json

import numpy as np

import t2_lidarveg as lv

total_new, total_pts = 0, 0
for key in sys.argv[1:]:
    s, paths = lv.seg_paths(key)
    feats = json.loads(lv.INDEX.read_text())["features"]
    pts_ll = np.c_[s.mlon, s.mlat]
    owner = np.full(len(s), -1)
    for i, f in enumerate(feats):
        free = owner < 0
        if not free.any():
            break
        inside = np.zeros(len(s), bool)
        for poly in lv.polygons(f["geometry"]):
            inside |= poly.contains_points(pts_ll)
        owner[free & inside] = i
    use = np.nonzero(owner >= 0)[0]
    new_b = new_p = all_b = 0
    for pi in sorted(set(owner[use])):
        f = feats[pi]
        name = f["properties"]["name"]
        idx = use[owner[use] == pi]
        lat = s.mlat.to_numpy()[idx]
        scale = 1 / np.cos(np.radians(lat.mean()))
        B = lv.BUF_M * scale
        boxes = np.array([[p[:, 0].min() - B, p[:, 1].min() - B,
                           p[:, 0].max() + B, p[:, 1].max() + B]
                          for p in (paths[i] for i in idx)])
        nodes = lv.EPT(f["properties"]["url"]).nodes(boxes)
        miss = [(k, n) for k, n in nodes
                if not (lv.CACHE / name / f"{k}.laz").exists()]
        all_b += len(nodes)
        new_b += len(miss)
        new_p += sum(n for _, n in miss)
    print(f"LIDAR {key}: {len(s):,} walking segments, {all_b:,} blocks, "
          f"{new_b:,} not cached, ~{new_p * 9 / 1e9:.2f} GB new", flush=True)
    total_new += new_b
    total_pts += new_p
print(f"LIDAR TOTAL: {total_new:,} new blocks, ~{total_pts * 9 / 1e9:.2f} GB")
