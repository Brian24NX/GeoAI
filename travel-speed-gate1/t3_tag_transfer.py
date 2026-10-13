#!/usr/bin/env python3
"""
Why don't OSM trail tags transfer to new regions, while terrain does? The
paper's discussion says mappers tag differently from place to place; this
tests it.

For every walking segment: the residual of ln(speed) after the pooled slope
curve (t1_findings smooth_asym), minus its outing's mean residual, so every
comparison is between segments of the SAME hike (same hiker, same day).
Then, region by region, the speed difference between segments with one tag
value and another, and between the steppiest and the smoothest fifth of
terrain (pitch_sd_5m, one set of cut points for all regions):

  terrain     steppiest fifth vs smoothest fifth
  sac_scale   mountain_hiking vs hiking; demanding_mountain_hiking or
              harder vs hiking
  visibility  intermediate vs excellent/good; bad or worse vs excellent/good
  surface     rock/stone, gravel, paved vs ground/dirt
  highway     footway vs path; steps vs path
  tagged      a trail with any sac_scale (visibility, surface) tag vs one
              without: what does a MISSING tag mean in each region?

A contrast counts in a region only with >= MIN_SEG segments and >= MIN_OUT
outings on each side; 95% intervals resample outings. A feature that
transfers has effects of one sign and similar size in every region; one
that doesn't spreads out or flips. Also: how much of each region is tagged
at all, and what the tags say in Yosemite (the one region where tags beat
terrain in the harness).

Input:  data/t1_all/segments_L50.parquet, data/t2/terrain5m_*.parquet,
        results/t1_findings/numbers.json
Output: results/t3_tag_transfer/ contrasts.csv (region x contrast),
        summary.csv (per contrast, across regions), coverage.csv,
        fig_tag_vs_terrain.png
Run (cluster): python t3_tag_transfer.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import t1_findings as tf

OUT = Path("results/t3_tag_transfer")
MIN_SEG, MIN_OUT = 200, 10
B = 500
GROUPS = {
    "sac": {"T1": {"hiking"}, "T2": {"mountain_hiking"},
            "T3+": {"demanding_mountain_hiking", "alpine_hiking",
                    "demanding_alpine_hiking", "difficult_alpine_hiking"}},
    "vis": {"good": {"excellent", "good"},
            "intermediate": {"intermediate", "medium"},
            "bad": {"bad", "poor", "intermittent", "very_bad", "horrible",
                    "no"}},
    "surface": {"ground": {"ground", "dirt", "earth", "grass", "mud",
                           "sand", "unpaved"},
                "rock": {"rock", "stone", "rocks"},
                "gravel": {"gravel", "fine_gravel", "compacted",
                           "pebblestone"},
                "paved": {"paved", "asphalt", "concrete", "paving_stones",
                          "sett", "concrete:plates"}},
    "highway": {"path": {"path"}, "footway": {"footway"},
                "steps": {"steps"}},
}
CONTRASTS = [
    ("Terrain: steppiest vs smoothest fifth", "steppy", "Q5", "Q1"),
    ("sac_scale: mountain_hiking vs hiking", "sac", "T2", "T1"),
    ("sac_scale: demanding or harder vs hiking", "sac", "T3+", "T1"),
    ("visibility: intermediate vs good", "vis", "intermediate", "good"),
    ("visibility: bad or worse vs good", "vis", "bad", "good"),
    ("surface: rock vs ground", "surface", "rock", "ground"),
    ("surface: gravel vs ground", "surface", "gravel", "ground"),
    ("surface: paved vs ground", "surface", "paved", "ground"),
    ("highway: footway vs path", "highway", "footway", "path"),
    ("highway: steps vs path", "highway", "steps", "path"),
    ("sac_scale: tagged vs untagged", "sac_any", "tagged", "untagged"),
    ("visibility: tagged vs untagged", "vis_any", "tagged", "untagged"),
    ("surface: tagged vs untagged", "surface_any", "tagged", "untagged"),
]
TAGS = {"sac": "tag_sac_scale", "vis": "tag_trail_visibility",
        "surface": "tag_surface", "highway": "tag_highway"}


def first(col):
    return col.astype("object").map(
        lambda x: x.split(";")[0].strip().lower()
        if isinstance(x, str) and x.strip() else None)


def group_of(col, groups):
    out = pd.Series(None, index=col.index, dtype="object")
    v = first(col)
    for g, values in groups.items():
        out[v.isin(values)] = g
    return out


def load():
    cols = ["region", "segment_id", "outing_id", "slope", "speed_kmh",
            "analysis_walk", *TAGS.values()]
    w = pd.read_parquet("data/t1_all/segments_L50.parquet", columns=cols)
    w = w[w.analysis_walk & (w.speed_kmh > 0)
          & w.slope.between(-0.6, 0.6)].reset_index(drop=True)
    nums = json.loads(Path("results/t1_findings/numbers.json").read_text())
    p = nums["forms_cv"]["smooth_asym"]["params_all"]
    w["res"] = np.log(w.speed_kmh) - tf.FORMS["smooth_asym"][0](
        p, w.slope.to_numpy())
    w["rd"] = w.res - w.groupby("outing_id").res.transform("mean")
    t5 = pd.concat([pd.read_parquet(f, columns=["segment_id", "pitch_sd_5m"])
                    for f in sorted(Path("data/t2").glob(
                        "terrain5m_*.parquet"))], ignore_index=True)
    w = w.merge(t5.drop_duplicates("segment_id"), on="segment_id",
                how="left")
    q1, q5 = w.pitch_sd_5m.quantile([0.2, 0.8])
    w["steppy"] = np.where(w.pitch_sd_5m <= q1, "Q1",
                           np.where(w.pitch_sd_5m > q5, "Q5", None))
    for key, col in TAGS.items():
        w[key] = group_of(w[col], GROUPS[key])
        w[f"{key}_any"] = np.where(first(w[col]).notna(), "tagged",
                                   "untagged")
    return w


def contrast(d, col, a, b, rng):
    """Mean outing-demeaned residual of group a minus group b, as % speed,
    with a 95% interval resampling outings; None if too little data."""
    A, Bd = d[d[col] == a], d[d[col] == b]
    if (len(A) < MIN_SEG or len(Bd) < MIN_SEG
            or A.outing_id.nunique() < MIN_OUT
            or Bd.outing_id.nunique() < MIN_OUT):
        return None
    g = pd.concat([A.assign(side=1), Bd.assign(side=0)]).groupby(
        ["outing_id", "side"]).rd.agg(["sum", "size"]).unstack("side",
                                                                fill_value=0)
    s1, n1 = g[("sum", 1)].to_numpy(), g[("size", 1)].to_numpy()
    s0, n0 = g[("sum", 0)].to_numpy(), g[("size", 0)].to_numpy()
    idx = rng.integers(0, len(g), (B, len(g)))
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = s1[idx].sum(1) / n1[idx].sum(1) - s0[idx].sum(1) / n0[idx].sum(1)
    eff = s1.sum() / n1.sum() - s0.sum() / n0.sum()
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    pct = lambda x: 100 * (np.exp(x) - 1)                     # noqa: E731
    return {"effect_pct": pct(eff), "lo": pct(lo), "hi": pct(hi),
            "segments_a": len(A), "segments_b": len(Bd),
            "outings_a": A.outing_id.nunique(),
            "outings_b": Bd.outing_id.nunique()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    w = load()
    rows = []
    for name, col, a, b in CONTRASTS:
        r = contrast(w, col, a, b, rng)
        if r:
            rows.append({"region": "ALL", "contrast": name, **r})
        for reg, d in w.groupby("region"):
            r = contrast(d, col, a, b, rng)
            if r:
                rows.append({"region": reg, "contrast": name, **r})
    c = pd.DataFrame(rows)
    c.to_csv(OUT / "contrasts.csv", index=False)

    summ = []
    for name, *_ in CONTRASTS:
        d = c[(c.contrast == name) & (c.region != "ALL")]
        allr = c[(c.contrast == name) & (c.region == "ALL")]
        if not len(d) or not len(allr):
            continue
        pooled = float(allr.effect_pct.iloc[0])
        sign = np.sign(pooled)
        summ.append({
            "contrast": name, "regions": len(d), "pooled_pct": pooled,
            "median_pct": float(d.effect_pct.median()),
            "min_pct": float(d.effect_pct.min()),
            "max_pct": float(d.effect_pct.max()),
            "sd_between_regions": float(d.effect_pct.std()),
            "same_sign": int((np.sign(d.effect_pct) == sign).sum()),
            "clear_same_sign": int(((d.lo > 0) if sign > 0
                                    else (d.hi < 0)).sum()),
            "clear_opposite_sign": int(((d.hi < 0) if sign > 0
                                        else (d.lo > 0)).sum())})
    s = pd.DataFrame(summ)
    s.to_csv(OUT / "summary.csv", index=False)
    print(s.round(1).to_string(index=False))

    cov = w.groupby("region").agg(
        segments=("rd", "size"),
        sac_tagged=("tag_sac_scale", lambda x: x.notna().mean()),
        visibility_tagged=("tag_trail_visibility",
                           lambda x: x.notna().mean()),
        surface_tagged=("tag_surface", lambda x: x.notna().mean()),
        sac_hiking=("sac", lambda x: (x == "T1").mean()),
        sac_mountain=("sac", lambda x: (x == "T2").mean()),
        sac_demanding=("sac", lambda x: (x == "T3+").mean()),
        paved=("surface", lambda x: (x == "paved").mean()),
        rock=("surface", lambda x: (x == "rock").mean()),
        footway=("highway", lambda x: (x == "footway").mean()))
    cov.to_csv(OUT / "coverage.csv")
    print(cov.round(2).to_string())
    print("\nYosemite:")
    print(c[c.region == "yosemite"].round(1).to_string(index=False))
    figure(c, s)


def figure(c, s):
    s = s.set_index("contrast")
    names = [n for n, *_ in CONTRASTS if n in s.index]
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(names) + 1.2))
    for i, n in enumerate(names):
        d = c[(c.contrast == n) & (c.region != "ALL")]
        col = "#2a78d6" if n.startswith("Terrain") else "#9a9893"
        ax.scatter(d.effect_pct, np.full(len(d), i), s=18, color=col,
                   alpha=0.8, zorder=3, lw=0)
        ax.scatter(s.loc[n, "pooled_pct"], i, marker="D", s=30,
                   color="#222", zorder=4)
        ax.text(1.01, i, f"{s.loc[n, 'same_sign']}/{s.loc[n, 'regions']}",
                transform=ax.get_yaxis_transform(), va="center", fontsize=8)
    ax.text(1.01, -0.9, "same sign\nas pooled", fontsize=7,
            transform=ax.get_yaxis_transform(), va="center")
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.set_yticks(range(len(names)), names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("speed difference within the same hike (%), "
                  "one dot per region; diamond: all regions")
    ax.grid(axis="x", color="#e4e3df")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_tag_vs_terrain.png", dpi=170)


if __name__ == "__main__":
    main()
