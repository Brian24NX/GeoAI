#!/usr/bin/env python3
"""
Track B (decision #126): the Satlas chip embeddings for the exercise table,
one row per row of cache/exercise/t3_table.parquet, in the same order (as
t3_export_naip_clay.py does for Track A).

Rows are matched by position to the harness's saved folds (segment ids), then
to their 25 m spot (data/t3/naip_spot_of_segment.parquet), then to that
spot's embedding (data/t3/naip_satlas/<region>.npz from t3_naip_satlas.py).

Writes cache/exercise/t3_naip_satlas.npy (not in git): float16, rows x 1,024.
North Shore rows (no NAIP) are NaN. Run on ENGR after the Slurm array:
    python t3_export_naip_satlas.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

t = pd.read_parquet("cache/exercise/t3_table.parquet", columns=["region"])
f = pd.read_parquet("results/t3_harness_terrain15m_folds/folds_segments.parquet",
                    columns=["segment_id"])
assert len(t) == len(f)
links = pd.read_parquet("data/t3/naip_spot_of_segment.parquet")
assert not links.duplicated(["region", "segment_id"]).any()
key = pd.DataFrame({"region": t.region.to_numpy(), "segment_id": f.segment_id.to_numpy()})
m = key.merge(links, on=["region", "segment_id"], how="left")
assert len(m) == len(t)
out = np.full((len(t), 1024), np.nan, dtype=np.float16)
for npz in sorted(Path("data/t3/naip_satlas").glob("*.npz")):
    region = npz.stem
    z = np.load(npz)
    pos = pd.Series(np.arange(len(z["spot"])), index=z["spot"])
    rows = np.flatnonzero((m.region == region).to_numpy() & m.spot.notna().to_numpy())
    got = pos.reindex(m.spot.to_numpy()[rows].astype(int)).to_numpy()
    ok = ~np.isnan(got)
    out[rows[ok]] = z["emb"][got[ok].astype(int)]
    print(f"{region}: {ok.sum():,} rows, {(~ok).sum()} without a chip", flush=True)
have = ~np.isnan(out[:, 0])
np.save("cache/exercise/t3_naip_satlas.npy", out)
print(f"{len(t):,} table rows, {have.sum():,} with imagery; without, by region: "
      f"{t.region[~have].value_counts().to_dict()}")
