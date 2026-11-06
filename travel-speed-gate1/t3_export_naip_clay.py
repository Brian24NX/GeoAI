#!/usr/bin/env python3
"""
Track A (decision #124): the Clay imagery embeddings for the exercise table,
one row per row of cache/exercise/t3_table.parquet, in the same order.

The table carries no segment ids, so rows are matched by position to the
harness's saved folds (results/t3_harness_terrain15m_folds/
folds_segments.parquet, written in the same order; see t3_export_table.py),
then to data/t3/naip_clay_index.parquet on (region, segment_id).

Writes cache/exercise/t3_naip_clay.npy (not in git): float16, rows x 1,024.
Rows in Olympic and the North Shore (no usable Clay imagery) are NaN.
Run on ENGR after t3_naip_clay_join.py:
    python t3_export_naip_clay.py
"""
import numpy as np
import pandas as pd

t = pd.read_parquet("cache/exercise/t3_table.parquet", columns=["region"])
f = pd.read_parquet("results/t3_harness_terrain15m_folds/folds_segments.parquet",
                    columns=["segment_id"])
assert len(t) == len(f)
idx = pd.read_parquet("data/t3/naip_clay_index.parquet")
assert not idx.duplicated(["region", "segment_id"]).any()
emb = np.load("data/t3/naip_clay_emb.npy", mmap_mode="r")
key = pd.DataFrame({"region": t.region.to_numpy(), "segment_id": f.segment_id.to_numpy()})
m = key.merge(idx[["region", "segment_id", "row"]], on=["region", "segment_id"], how="left")
assert len(m) == len(t) and (m.region.to_numpy() == t.region.to_numpy()).all()
have = m.row.notna().to_numpy()
out = np.full((len(t), emb.shape[1]), np.nan, dtype=np.float16)
out[have] = emb[m.row[have].astype(int).to_numpy()]
np.save("cache/exercise/t3_naip_clay.npy", out)
print(f"{len(t):,} table rows, {have.sum():,} with imagery; without, by region: "
      f"{t.region[~have].value_counts().to_dict()}")
