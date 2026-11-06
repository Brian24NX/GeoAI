#!/usr/bin/env python3
"""
Track A, step 2 (decision #124): give every walking segment the Clay v1.5
embedding of the NAIP chip under its midpoint.

Input:  data/t1_all/segments_L50.parquet (walking rows, `analysis_walk`)
        results/t3_naip/clay_manifest.csv (region, tile -> Clay file)
        cache/naip_clay/<key> (t3_naip_clay_download.py)
Output: data/t3/naip_clay_index.parquet: region, segment_id, tile, row,
        chip_dist_m (midpoint to chip centre)
        data/t3/naip_clay_emb.npy: float16, one 1,024-number row per index row

Chip outlines are WKB polygons in longitude/latitude (checked 5 Nov), about
155 m on a side, so a segment takes the chip whose centre is nearest its
midpoint (within ~110 m when inside it). Olympic (Clay has only 2017 at 1 m)
and the North Shore (no NAIP) get no rows. Tiles whose file is missing or
incomplete are skipped and counted, so the script also runs mid-download.
    python t3_naip_clay_join.py
"""
import struct
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

SEGMENTS = Path("data/t1_all/segments_L50.parquet")
MANIFEST = Path("results/t3_naip/clay_manifest.csv")
CACHE = Path("cache/naip_clay")
OUT = Path("data/t3")
SKIP_REGIONS = {"olympic", "northshore"}


def tile_of(lat, lon):
    """NAIP quarter quad of each point: block, quad 01-64 from the block's
    north-west corner eastward then south, and the quarter (ne/nw/se/sw)."""
    L = np.floor(lat).astype(int)
    M = np.floor(-lon).astype(int)
    r = np.floor((L + 1 - lat) / 0.125).astype(int)
    c = np.floor((lon + M + 1) / 0.125).astype(int)
    n = r * 8 + c + 1
    north = L + 1 - r * 0.125
    west = -(M + 1) + c * 0.125
    q = (np.where(lat >= north - 0.0625, "n", "s").astype(object)
         + np.where(lon < west + 0.0625, "w", "e").astype(object))
    return [f"{a:02d}{b:03d}{k:02d}_{x}" for a, b, k, x in zip(L, M, n, q)]


def chip_centres(wkbs):
    """Centre (lon, lat) of each WKB polygon: the mean of its distinct corners."""
    out = np.empty((len(wkbs), 2))
    for i, w in enumerate(wkbs):
        bo = "<" if w[0] == 1 else ">"
        npt = struct.unpack(bo + "I", w[9:13])[0]
        xy = np.frombuffer(w[13:13 + 16 * npt], dtype=bo + "f8").reshape(-1, 2)
        out[i] = xy[:-1].mean(0)            # the ring repeats its first corner
    return out


def main():
    s = pd.read_parquet(SEGMENTS, columns=["region", "segment_id", "lat0", "lon0",
                                           "lat1", "lon1", "analysis_walk"])
    s = s[s.analysis_walk.astype(bool) & ~s.region.isin(SKIP_REGIONS)].reset_index(drop=True)
    s["lat"] = (s.lat0 + s.lat1) / 2
    s["lon"] = (s.lon0 + s.lon1) / 2
    s["tile"] = tile_of(s.lat.to_numpy(), s.lon.to_numpy())
    man = pd.read_csv(MANIFEST)
    s = s.merge(man[["region", "tile", "key", "bytes"]], on=["region", "tile"], how="left")
    print(f"{len(s)} walking segments in {s.region.nunique()} regions, "
          f"{s.key.nunique()} Clay files", flush=True)

    rows, embs, missing = [], [], 0
    for key, g in s.groupby("key", sort=False):
        f = CACHE / key
        if not f.exists() or f.stat().st_size != int(g.bytes.iloc[0]):
            missing += 1
            continue
        t = pq.read_table(f)
        ctr = chip_centres(t.column("geometry").to_pylist())
        lat, lon = g.lat.to_numpy(), g.lon.to_numpy()
        dx = (lon[:, None] - ctr[None, :, 0]) * 111320 * np.cos(np.radians(lat))[:, None]
        dy = (lat[:, None] - ctr[None, :, 1]) * 110540
        d2 = dx ** 2 + dy ** 2
        k = d2.argmin(1)
        e = t.column("embeddings").combine_chunks().flatten().to_numpy(zero_copy_only=False)
        e = e.reshape(t.num_rows, -1)
        embs.append(e[k].astype(np.float16))
        rows.append(pd.DataFrame({"region": g.region.to_numpy(), "segment_id": g.segment_id.to_numpy(),
                                  "tile": g.tile.to_numpy(),
                                  "chip_dist_m": np.sqrt(d2[np.arange(len(k)), k]).astype(np.float32)}))
    if not rows:
        raise SystemExit(f"no Clay files downloaded yet ({missing} missing)")
    idx = pd.concat(rows, ignore_index=True)
    idx["row"] = np.arange(len(idx))
    emb = np.vstack(embs)
    OUT.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(OUT / "naip_clay_index.parquet", index=False)
    np.save(OUT / "naip_clay_emb.npy", emb)
    far = (idx.chip_dist_m > 120).sum()
    print(f"joined {len(idx)} segments ({emb.shape[1]} numbers each); files missing {missing}; "
          f"midpoint to chip centre: median {idx.chip_dist_m.median():.0f} m, "
          f"max {idx.chip_dist_m.max():.0f} m, {far} over 120 m", flush=True)
    print(idx.groupby("region").size().to_string(), flush=True)


if __name__ == "__main__":
    main()
