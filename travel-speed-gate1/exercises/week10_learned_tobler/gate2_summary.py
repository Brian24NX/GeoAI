#!/usr/bin/env python3
"""
Gate 2 summary (week 11; prepared by Claude, 26 Oct 2026), from
../../cache/t3_learned/<split>.parquet (run_all.py). Per split:
  skill vs the slope curve, %:  trees (the harness's gbm_rs, reproduced),
      learned Tobler (a) scored the harness's way and (b) with its own
      Student-t spread; per-row CRPS averaged over the seeds, plus the
      seeds' own range for (a)
  95% bootstrap intervals, resampling the split's units as
      t3_harness.skill_intervals does (outings; uploaders for hiker5;
      regions for loro and loro_hiker), 2,000 draws
  paired: learned (a) - trees and (b) - trees, with the share of draws
      above zero (Gate 2's last box: "beats a plain gradient-boosted-trees
      baseline on the same features")
  calibration: share of test segments inside the model's own 90% range
Writes ../../results/t3_learned_tobler/gate2_summary.csv
Run:   ../../../.venv/bin/python gate2_summary.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IN = ROOT / "cache" / "t3_learned"
OUT = ROOT / "results" / "t3_learned_tobler"
SPLITS = ["outing5", "hiker5", "block5", "loro", "loro_hiker"]
UNIT = {"outing5": "outing", "block5": "outing", "hiker5": "hiker",
        "loro": "region", "loro_hiker": "region"}
B = 2000


def skill(model, ref):
    return 100 * (1 - model / ref)


def summarize(split, d, rng):
    seeds = sorted(int(m.group(1)) for c in d.columns
                   if (m := re.fullmatch(r"crps_a_s(\d+)", c)))
    d = d.assign(a=d[[f"crps_a_s{k}" for k in seeds]].mean(axis=1),
                 b=d[[f"crps_b_s{k}" for k in seeds]].mean(axis=1))
    g = d.groupby(UNIT[split])[["crps_ref", "crps_trees", "a", "b"]].sum()
    idx = rng.integers(0, len(g), (B, len(g)))
    draw = {c: g[c].to_numpy()[idx].sum(1) for c in g.columns}
    sk = {c: skill(draw[c], draw["crps_ref"]) for c in ("crps_trees", "a", "b")}
    tot = g.sum()
    row = {"split": split, "unit": UNIT[split], "units": len(g),
           "segments": len(d), "seeds": len(seeds)}
    for c, name in (("crps_trees", "trees"), ("a", "learned_a"),
                    ("b", "learned_b")):
        row[name] = skill(tot[c], tot.crps_ref)
        row[f"{name}_lo"], row[f"{name}_hi"] = np.percentile(sk[c], [2.5, 97.5])
    per_seed = [skill(d[f"crps_a_s{k}"].sum(), d.crps_ref.sum()) for k in seeds]
    row["learned_a_seed_min"], row["learned_a_seed_max"] = min(per_seed), max(per_seed)
    for c, name in (("a", "a_minus_trees"), ("b", "b_minus_trees")):
        diff = sk[c] - sk["crps_trees"]
        row[name] = row[f"learned_{c}"] - row["trees"]
        row[f"{name}_lo"], row[f"{name}_hi"] = np.percentile(diff, [2.5, 97.5])
        row[f"{name}_share_above_0"] = float((diff > 0).mean())
    row["own_90pct_range_holds"] = 100 * float(
        d[[f"in90_s{k}" for k in seeds]].to_numpy().mean())
    return row


def main():
    rng = np.random.default_rng(0)
    rows = [summarize(sp, pd.read_parquet(IN / f"{sp}.parquet"), rng)
            for sp in SPLITS if (IN / f"{sp}.parquet").exists()]
    if not rows:
        raise SystemExit(f"nothing in {IN}; run run_all.py first")
    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "gate2_summary.csv", index=False)
    for r in rows:
        print(f"{r['split']:<11} ({r['units']} {r['unit']}s, {r['seeds']} seeds)  "
              f"trees {r['trees']:+.2f} [{r['trees_lo']:+.2f}, {r['trees_hi']:+.2f}]  "
              f"learned (a) {r['learned_a']:+.2f} [{r['learned_a_lo']:+.2f}, "
              f"{r['learned_a_hi']:+.2f}]  (b) {r['learned_b']:+.2f}  |  "
              f"(a) - trees {r['a_minus_trees']:+.2f} [{r['a_minus_trees_lo']:+.2f}, "
              f"{r['a_minus_trees_hi']:+.2f}]  (b) - trees {r['b_minus_trees']:+.2f} "
              f"[{r['b_minus_trees_lo']:+.2f}, {r['b_minus_trees_hi']:+.2f}]  |  "
              f"own 90% range holds {r['own_90pct_range_holds']:.1f}%")
    print(f"-> {OUT / 'gate2_summary.csv'}")


if __name__ == "__main__":
    main()
