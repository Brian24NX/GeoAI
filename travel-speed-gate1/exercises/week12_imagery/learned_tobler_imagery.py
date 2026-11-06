#!/usr/bin/env python3
"""
Week 12 exercise (Brian's; set up by Claude, 6 Nov 2026): does aerial
imagery help learned Tobler in regions it never saw?

Track A of the imagery arm (decision #124). Every segment has Clay v1.5's
1,024-number embedding of the 155 m NAIP chip under its midpoint.
track_a_trees.py shrinks it to 16 numbers per fold and runs the Gate 2 trees
with and without them. Here you do the same for learned Tobler, on the
unseen-region test (loro: each of the 15 regions with imagery held out in
turn), and compare two versions:
    terrain   inputs = the 12 terrain measures (the Gate 2 model)
    both      inputs = the 12 terrain measures + the 16 imagery numbers
Scored with (b), the model's own Student-t spread, as in the Gate 2 write-up.

Success rule (set before looking): both - terrain > 0, with the 95%
interval (bootstrap over the 15 regions) above zero.

Run:    ../../../.venv/bin/python learned_tobler_imagery.py   (a few minutes)
        Set EMB = "satlas" below to repeat it for Track B.
Writes: ../../cache/t3_imagery/learned_loro_<EMB>.parquet
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "week10_learned_tobler"))
import learned_tobler as lt  # noqa: E402
import run_all as ra         # noqa: E402
import track_a_trees as ta   # noqa: E402

EMB = "clay"     # "clay" = Track A (Clay, 155 m squares); "satlas" = Track B (trail-centred chips)


def main():
    t, inner, terrain, emb = ta.load(EMB)
    s, y = t.slope.to_numpy(), t.y.to_numpy()
    rng = np.random.default_rng(0)        # the same draws as track_a_trees.py
    parts = []
    for f, fit, stop, cal, test in lt.folds(t, inner, "loro"):
        p, c_ref = lt.reference(s, y, fit, stop, cal, test)

        # -------------------------------------------------------- TODO 1
        # The 16 imagery numbers for this fold. ta.imagery_pcs(emb, rows, rng)
        # fits the PCA on `rows` only and returns 16 numbers for EVERY
        # segment. Which rows may the PCA learn from? Use the same training
        # rows as the trees, in the same order (fit, then stop, then cal),
        # so both models see identical numbers. Which rows must it never see?
        #
        # Answer (drafted with Claude): the fold's training rows, fit + stop +
        # cal, never `test`. The PCA decides which 16 directions of the 1,024
        # numbers to keep; fitted on the held-out region's photos, it would be
        # shaped by the test region, a leak like fitting a scaler on test data.
        rows = np.r_[fit, stop, cal]
        t[ta.PCS] = ta.imagery_pcs(emb, rows, rng)

        # -------------------------------------------------------- TODO 2
        # Each model's input columns, as a list of column names:
        # "terrain" = the 12 terrain measures (the list `terrain`);
        # "both" = those 12 plus the 16 imagery columns (the list ta.PCS).
        # Answer (drafted with Claude): the same model twice; only the inputs
        # differ, so any change in skill comes from the imagery.
        inputs = {"terrain": terrain, "both": terrain + ta.PCS}

        d = pd.DataFrame({"fold": f, "region": t.region.to_numpy()[test],
                          "crps_ref": c_ref})
        for name, cols in inputs.items():
            x = lt.features(t, cols, np.r_[fit, stop])       # as in run_all.py
            o = ra.learned(x, s, y, p, fit, stop, cal, test, seed=0)
            d[f"crps_{name}"] = o["crps_b"]                  # (b): its own spread
        parts.append(d)
        print(f"  {f}: terrain {ra.sc.skill(d.crps_terrain, d.crps_ref):+.2f}%, "
              f"both {ra.sc.skill(d.crps_both, d.crps_ref):+.2f}%", flush=True)

    d = pd.concat(parts, ignore_index=True)
    ta.OUT.mkdir(parents=True, exist_ok=True)
    d.to_parquet(ta.OUT / f"learned_loro_{EMB}.parquet", index=False)

    # ------------------------------------------------------------ TODO 3
    # (a) Each model's skill over the slope-only curve, in percent:
    #     100 * (1 - sum of its CRPS / sum of crps_ref), over all regions.
    # (b) gain = skill(both) - skill(terrain).
    # (c) Its 95% interval: 2,000 times, draw 15 regions with replacement
    #     (np.random.default_rng(0)), recompute the gain on those regions'
    #     segments, and take the 2.5th and 97.5th percentiles.
    #     Tip: first sum each CRPS column per region with
    #     d.groupby("region")[["crps_ref", "crps_terrain", "crps_both"]].sum()
    #
    # Answer (drafted with Claude): resample whole regions, because in this
    # test the region is the unit that varies (its segments are not
    # independent of each other).
    g = d.groupby("region")[["crps_ref", "crps_terrain", "crps_both"]].sum()

    def gain_of(regions):
        """Skill of terrain and of terrain + imagery (% over the slope-only
        curve) on these regions' segments, and the gain of one over the other."""
        tot = regions.sum()
        terr = 100 * (1 - tot.crps_terrain / tot.crps_ref)
        both = 100 * (1 - tot.crps_both / tot.crps_ref)
        return terr, both, both - terr

    terr, both, gain = gain_of(g)
    draws = np.random.default_rng(0).integers(0, len(g), (2000, len(g)))   # 2,000 resamples
    boot = [gain_of(g.iloc[i])[2] for i in draws]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"terrain {terr:+.2f}%, terrain + imagery {both:+.2f}%, "
          f"gain {gain:+.2f} [{lo:+.2f}, {hi:+.2f}]")

    # ------------------------------------------------------------ TODO 4
    # One sentence for the write-up: does imagery help learned Tobler in
    # regions it never saw? Quote the gain and its interval.
    #
    # Answer (drafted with Claude; Track A, Clay embeddings): No. In regions
    # it never saw, adding the imagery moves learned Tobler from +3.37% to
    # +3.81% over the slope-only curve, a gain of +0.44 points whose 95%
    # interval (-0.67 to +1.20) crosses zero. It helps a lot in some regions
    # (Adirondacks +4.1, Green Mountains +4.0) and hurts in others (Wasatch
    # -3.6, Tahoe -3.3), so it does not carry over reliably.


if __name__ == "__main__":
    main()
