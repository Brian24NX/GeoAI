#!/usr/bin/env python3
"""
Track A of the imagery arm, trees (decision #124; docs/T3_naip_imagery_design.md;
set up and run by Claude, 6 Nov 2026). Does aerial imagery add to terrain in
places the model never saw?

Data: the 15 regions with Clay v1.5 NAIP embeddings (Olympic and the North
Shore have none), from cache/exercise/t3_naip_clay.npy (t3_export_naip_clay.py),
one 1,024-number embedding per segment: the 155 m chip under its midpoint.

Per split and fold, exactly the Gate 2 trees (week10 run_all.trees: the
harness's gbm_rs settings, early-stopped on the stop rows, spread from the cal
residuals) on three input sets:
    terrain   slope + the 12 terrain measures (the Gate 2 trees, on 15 regions)
    imagery   slope + 16 imagery numbers
    both      slope + 12 terrain measures + 16 imagery numbers
The 16 imagery numbers are a PCA of the embeddings fitted on that fold's
training rows only (fit + stop + cal; at most 60,000 of them, seed 0).

Writes ../../cache/t3_imagery/<split>.parquet (per test segment: row, fold,
region, outing, hiker, crps_ref, crps_terrain, crps_imagery, crps_both) and
../../results/t3_imagery/track_a_trees_summary.csv: skill for each input set,
and the paired gain of both over terrain with 95% bootstrap intervals
(2,000 draws of the split's units, as in gate2_summary.py).

Success rule (set before looking): in loro and loro_hiker, both - terrain
> 0 with the interval above zero.
Run:  ../../../.venv/bin/python track_a_trees.py [--splits loro ...]
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "week10_learned_tobler"))
import learned_tobler as lt  # noqa: E402
import run_all as ra         # noqa: E402

ROOT = lt.ROOT
OUT = ROOT / "cache" / "t3_imagery"
RES = ROOT / "results" / "t3_imagery"
SPLITS = ["outing5", "hiker5", "block5", "loro", "loro_hiker"]
UNIT = {"outing5": "outing", "block5": "outing", "hiker5": "hiker",
        "loro": "region", "loro_hiker": "region"}
N_PC, PCA_ROWS, B = 16, 60_000, 2000
PCS = [f"img_pc{i}" for i in range(N_PC)]


def load():
    t, inner, cols = lt.load()
    terrain = cols["covariates"]["terrain5m"] + cols["covariates"]["terrain1m"]
    emb = np.load(ROOT / "cache" / "exercise" / "t3_naip_clay.npy", mmap_mode="r")
    assert emb.shape[0] == len(t)
    keep = ~np.isnan(emb[:, 0])
    t = t[keep].reset_index().rename(columns={"index": "row"})   # row = full-table row
    emb = np.asarray(emb[keep], dtype=np.float32)
    return t, inner, terrain, emb


def imagery_pcs(emb, rows, rng):
    """The 16 imagery numbers for every segment: a PCA of the embeddings
    fitted on `rows` only (at most PCA_ROWS of them, drawn with `rng`).
    Shared with the learned-Tobler exercise, so both models see the same
    numbers when they use the same rows and draws."""
    sub = rng.choice(rows, min(PCA_ROWS, len(rows)), replace=False)
    pca = PCA(N_PC, svd_solver="randomized", random_state=0).fit(emb[sub])
    return pca.transform(emb).astype(np.float32)


def run_split(t, inner, terrain, emb, split):
    s, y = t.slope.to_numpy(), t.y.to_numpy()
    rng = np.random.default_rng(0)
    parts = []
    for f, fit, stop, cal, test in lt.folds(t, inner, split):
        t0 = time.time()
        p, c_ref = lt.reference(s, y, fit, stop, cal, test)
        tf = t.copy()
        tf[PCS] = imagery_pcs(emb, np.r_[fit, stop, cal], rng)
        d = pd.DataFrame({"row": t.row.to_numpy()[test], "fold": f,
                          "region": t.region.to_numpy()[test],
                          "outing": t.outing.to_numpy()[test],
                          "hiker": t.hiker.to_numpy()[test], "crps_ref": c_ref})
        for name, cols in [("terrain", terrain), ("imagery", PCS), ("both", terrain + PCS)]:
            d[f"crps_{name}"] = ra.trees(tf, cols, y, fit, stop, cal, test)
        parts.append(d)
        sk = {k: 100 * (1 - d[f"crps_{k}"].sum() / d.crps_ref.sum())
              for k in ("terrain", "imagery", "both")}
        print(f"{split} fold {f}: {len(test):,} test; skill terrain {sk['terrain']:+.2f}, "
              f"imagery {sk['imagery']:+.2f}, both {sk['both']:+.2f} "
              f"({time.time() - t0:.0f} s)", flush=True)
    d = pd.concat(parts, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_parquet(OUT / f"{split}.parquet", index=False)
    return d


def skill(d, col):
    return 100 * (1 - d[col].sum() / d.crps_ref.sum())


def summarize(split, d):
    """Skill per input set and the paired gain of both over terrain, with a
    bootstrap over the split's units (2,000 draws, seed 0)."""
    rng = np.random.default_rng(0)
    g = d.groupby(UNIT[split])[["crps_ref", "crps_terrain", "crps_imagery", "crps_both"]].sum()
    a = g.to_numpy()
    draws = rng.integers(0, len(a), (B, len(a)))
    tot = np.stack([a[i].sum(0) for i in draws])            # B x 4
    boot = 100 * (1 - tot[:, 1:] / tot[:, :1])               # skill: terrain, imagery, both
    gain = boot[:, 2] - boot[:, 0]
    row = {"split": split, "unit": UNIT[split], "units": len(a), "segments": len(d)}
    for k, name in enumerate(["terrain", "imagery", "both"]):
        row[name] = skill(d, f"crps_{name}")
        row[f"{name}_lo"], row[f"{name}_hi"] = np.percentile(boot[:, k], [2.5, 97.5])
    row["both_minus_terrain"] = row["both"] - row["terrain"]
    row["gain_lo"], row["gain_hi"] = np.percentile(gain, [2.5, 97.5])
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", nargs="+", default=SPLITS, choices=SPLITS)
    a = ap.parse_args()
    t, inner, terrain, emb = load()
    print(f"{len(t):,} segments in {t.region.nunique()} regions with imagery", flush=True)
    rows = [summarize(split, run_split(t, inner, terrain, emb, split)) for split in a.splits]
    res = pd.DataFrame(rows)
    RES.mkdir(parents=True, exist_ok=True)
    res.to_csv(RES / "track_a_trees_summary.csv", index=False)
    print(res.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
