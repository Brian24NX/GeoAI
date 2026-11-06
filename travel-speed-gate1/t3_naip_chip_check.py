#!/usr/bin/env python3
"""
Track B sanity check for Brian (decision #126): 20 random trail spots, each
96 m NAIP chip with its matched trail segments drawn in red on top. Does the
chip actually show the trail?

Writes chip_check/chip_NN.png (480 x 480, the 160 x 160 chip enlarged 3x) and
chip_check/chips.json (region, photo year and pixel size, segments per spot),
for the sheet chip_check.html.
Run on ENGR:  python t3_naip_chip_check.py
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import t3_naip_satlas as ns

OUT = Path("chip_check")
N, SIZE = 20, 480


def lonlat(wkt):
    return [tuple(map(float, p.split())) for p in re.findall(r"-?\d+\.?\d*\s+-?\d+\.?\d*", wkt)]


def main():
    spots = pd.read_parquet(ns.SPOTS)
    links = pd.read_parquet("data/t3/naip_spot_of_segment.parquet")
    seg = pd.read_parquet("data/t1_all/segments_L50.parquet",
                          columns=["region", "segment_id", "geometry_wkt", "analysis_walk"])
    seg = seg[seg.analysis_walk.astype(bool)]
    pick = spots.sample(N, random_state=0).reset_index(drop=True)
    token, meta = ns.Token(), []
    OUT.mkdir(exist_ok=True)
    for k, r in enumerate(pick.itertuples(), 1):
        ids = links[(links.region == r.region) & (links.spot == r.spot)].segment_id
        g = seg[(seg.region == r.region) & seg.segment_id.isin(ids)]
        with ns.open_photo(r.href, token) as src:
            c = ns.chips(src, [r.lat], [r.lon])[0]
            (cx,), (cy,) = ns.centre_xy(src, [r.lat], [r.lon])
            img = Image.fromarray(np.ascontiguousarray(c.transpose(1, 2, 0))).resize(
                (SIZE, SIZE), Image.NEAREST)
            draw = ImageDraw.Draw(img)
            scale = SIZE / (2 * ns.HALF_M)
            for wkt in g.geometry_wkt:
                pts = lonlat(wkt)
                xs, ys = ns.warp("EPSG:4326", src.crs, [p[0] for p in pts], [p[1] for p in pts])
                draw.line([((x - cx + ns.HALF_M) * scale, (cy + ns.HALF_M - y) * scale)
                           for x, y in zip(xs, ys)], fill=(255, 40, 40), width=3)
        img.save(OUT / f"chip_{k:02d}.png")
        meta.append({"id": k, "region": r.region, "year": int(r.year), "gsd": float(r.gsd),
                     "segments": int(len(g))})
        print(f"chip {k}: {r.region} {int(r.year)} {r.gsd} m, {len(g)} segments", flush=True)
    (OUT / "chips.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
