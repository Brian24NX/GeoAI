#!/usr/bin/env python3
"""
First findings from the multi-region T1 data (walking hikes, 50 m trail
segments), before any remote sensing. Four cheap analyses that shape what
the paper says and what T2 has to explain.

1. FORM. Is Tobler's exponential the right shape? In log space Tobler is
   log v = a - k |s + s0| (a sharp tent). Compared, with 5-fold
   cross-validation over OUTINGS (never segments of the same hike on both
   sides):
     tobler     a - k |s + s0|
     smooth     a - k (sqrt((s + s0)^2 + e^2) - e)    rounded top of width e;
                                                      e -> 0 is Tobler
     asym       a - ku max(s + s0, 0) - kd max(-(s + s0), 0)
     smooth_asym  both
     lorentz    a - log(1 + ((s + s0) / w)^2)          (Campbell et al. 2019)
   Scored by out-of-fold RMSE of log speed and MAE of speed.
2. WHO vs WHERE. Of the variance left after the best curve, how much is
   between outings (the hiker, that day) vs within an outing (the trail)?
   One-way random-effects ANOVA estimate (unbalanced groups).
3. FATIGUE. Within an outing, does speed (relative to the curve) fall with
   hours since the start? Outing-demeaned residuals vs elapsed time.
4. ASYMMETRY. Out-and-back pairs (same hiker, same OSM way, both
   directions) across all regions: median down/up speed ratio by grade,
   95% intervals resampling outings. Tobler predicts 1.42 at >= 5% grade.

Input: every built region (data/t1_<key>/ with modes.csv).
Output: results/t1_findings/numbers.json, slope_bins.csv (speed quartiles
        per 2% slope bin, for the paper's curve figure), fig_forms.png,
        fig_fatigue.png, fig_asymmetry.png
Run:   python t1_findings.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import least_squares

import regions
import t1_variants as v

OUT = Path("results/t1_findings")
FOLDS = 5
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = ("#2a78d6", "#eb6834", "#1baf7a",
                                       "#eda100", "#e87ba4")
MUTED, GRID = "#52514e", "#e4e3df"


# ------------------------------------------------------------------ data
def walking_segments():
    parts = []
    for key in regions.CANDIDATES:
        d = regions.data_dir(key)
        if not (d / "modes.csv").exists():
            continue
        seg = pd.read_parquet(d / "segments_L50.parquet")
        tr = pd.read_csv(d / "traces.csv")
        w = v.walker_trail_segments(seg, set(tr.loc[tr.hiking_trace,
                                                    "trace_id"]),
                                    pd.read_csv(d / "modes.csv"))
        parts.append(w.assign(region=key))
    w = pd.concat(parts, ignore_index=True)
    return w[(w.speed_kmh > 0) & w.slope.between(-0.6, 0.6)]


# ----------------------------------------------------------------- forms
def _tobler(p, s):
    a, k, s0 = p
    return a - k * np.abs(s + s0)


def _smooth(p, s):
    a, k, s0, e = p
    e = abs(e)
    return a - k * (np.sqrt((s + s0) ** 2 + e ** 2) - e)


def _asym(p, s):
    a, ku, kd, s0 = p
    x = s + s0
    return a - ku * np.maximum(x, 0) - kd * np.maximum(-x, 0)


def _smooth_asym(p, s):
    a, ku, kd, s0, e = p
    x, e = s + s0, abs(e)
    r = np.sqrt(x ** 2 + e ** 2) - e
    return a - np.where(x >= 0, ku, kd) * r


def _lorentz(p, s):
    a, s0, w = p
    return a - np.log1p(((s + s0) / w) ** 2)


FORMS = {
    "tobler": (_tobler, [1.4, 2.0, 0.05]),
    "smooth": (_smooth, [1.45, 2.5, 0.05, 0.05]),
    "asym": (_asym, [1.4, 2.0, 2.0, 0.05]),
    "smooth_asym": (_smooth_asym, [1.45, 2.5, 2.5, 0.05, 0.05]),
    "lorentz": (_lorentz, [1.45, 0.05, 0.25]),
}


def fit_form(name, s, y):
    f, p0 = FORMS[name]
    res = least_squares(lambda p: f(p, s) - y, p0, loss="soft_l1",
                        f_scale=0.3)
    return res.x


def cv_forms(w, rng):
    """Out-of-fold scores per form, folds = groups of outings."""
    outs = w.outing_id.unique()
    rng.shuffle(outs)
    fold_of = {o: i % FOLDS for i, o in enumerate(outs)}
    fold = w.outing_id.map(fold_of).to_numpy()
    s, y = w.slope.to_numpy(), np.log(w.speed_kmh.to_numpy())
    scores = {}
    for name, (f, _) in FORMS.items():
        pred = np.empty_like(y)
        for k in range(FOLDS):
            tr, te = fold != k, fold == k
            pred[te] = f(fit_form(name, s[tr], y[tr]), s[te])
        scores[name] = {
            "rmse_log": float(np.sqrt(np.mean((pred - y) ** 2))),
            "mae_kmh": float(np.mean(np.abs(np.exp(pred) - np.exp(y)))),
            "params_all": [float(x) for x in fit_form(name, s, y)]}
    return scores


# ------------------------------------------------------- who vs where
def variance_split(res, groups):
    """One-way random-effects ANOVA (unbalanced): sigma_between^2,
    sigma_within^2 of residuals grouped by outing."""
    df = pd.DataFrame({"r": res, "g": groups})
    n_i = df.groupby("g").size().to_numpy()
    m_i = df.groupby("g").r.mean().to_numpy()
    N, k = len(df), len(n_i)
    grand = df.r.mean()
    ssb = np.sum(n_i * (m_i - grand) ** 2)
    ssw = np.sum((df.r - df.g.map(df.groupby("g").r.mean())) ** 2)
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - np.sum(n_i ** 2) / N) / (k - 1)
    sb2 = max((msb - msw) / n0, 0.0)
    return {"between_outings_var": float(sb2),
            "within_outing_var": float(msw),
            "share_between_pct": float(100 * sb2 / (sb2 + msw)),
            "outings": int(k), "segments": int(N)}


# ------------------------------------------------------------- figures
def style(ax):
    ax.grid(color=GRID, lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    w = walking_segments()
    nums = {"regions": sorted(w.region.unique()),
            "walking_segments": int(len(w)),
            "walking_outings": int(w.outing_id.nunique())}
    print(nums, flush=True)

    # 1. functional form
    nums["forms_cv"] = cv_forms(w, rng)
    best = min(nums["forms_cv"], key=lambda n: nums["forms_cv"][n]
               ["rmse_log"])
    nums["best_form"] = best
    print(json.dumps(nums["forms_cv"], indent=1), flush=True)
    s_all, y_all = w.slope.to_numpy(), np.log(w.speed_kmh.to_numpy())
    grid = np.linspace(-0.45, 0.45, 181)
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    edges = np.arange(-0.45, 0.4501, 0.02)
    b = pd.cut(w.slope, edges)
    med = w.groupby(b, observed=False).speed_kmh.median().to_numpy()
    gb = w.groupby(b, observed=False)
    pd.DataFrame({"slope_mid": edges[:-1] + 0.01, "segments": gb.size(),
                  "outings": gb.outing_id.nunique(),
                  "q25_kmh": gb.speed_kmh.quantile(0.25),
                  "median_kmh": med,
                  "q75_kmh": gb.speed_kmh.quantile(0.75)}
                 ).to_csv(OUT / "slope_bins.csv", index=False)
    ax.plot(100 * (edges[:-1] + 0.01), med, "o", color="#9a9893", ms=4,
            label="median per 2% slope bin (all walkers)")
    ax.plot(100 * grid, 6 * np.exp(-3.5 * np.abs(grid + 0.05)), "--",
            color=MUTED, lw=1.3, label="Tobler (1993) as published")
    for name, c in (("tobler", BLUE), ("smooth", ORANGE),
                    ("lorentz", AQUA)):
        p = nums["forms_cv"][name]["params_all"]
        ax.plot(100 * grid, np.exp(FORMS[name][0](p, grid)), color=c, lw=2,
                label=f"{name} fit (CV RMSE log "
                      f"{nums['forms_cv'][name]['rmse_log']:.4f})")
    ax.set_xlabel("slope along direction of travel (%), + = uphill")
    ax.set_ylabel("walking speed (km/h)")
    ax.set_ylim(0, 6.5)
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title(f"Slope-speed shape, {nums['walking_outings']:,} walking "
                 f"outings in {len(nums['regions'])} regions", fontsize=9)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / "fig_forms.png", dpi=170)
    plt.close(fig)

    # 2. who vs where (residuals from the best form, fitted on all)
    f, _ = FORMS[best]
    res = y_all - f(nums["forms_cv"][best]["params_all"], s_all)
    nums["variance_split_outing"] = variance_split(res, w.outing_id)
    reg = variance_split(res, w.region)
    nums["variance_between_regions_pct_of_total"] = float(
        100 * reg["between_outings_var"] / np.var(res))
    print(nums["variance_split_outing"], flush=True)

    # 3. fatigue: hours since the outing's first segment vs residual
    w = w.assign(res=res)
    t0 = w.groupby("outing_id").t_start.transform("min")
    w["hours"] = (w.t_start - t0) / 3600
    w["res_dm"] = w.res - w.groupby("outing_id").res.transform("mean")
    hb = pd.cut(w.hours, [0, 1, 2, 3, 4, 5, 6, 8, 10])
    fat = w.groupby(hb, observed=True).agg(n=("res_dm", "size"),
                                           res=("res_dm", "mean"))
    fat = fat[fat.n >= 200]
    keep = w.hours.between(0, 10)
    slope_per_h = float(np.polyfit(w.hours[keep], w.res_dm[keep], 1)[0])
    nums["fatigue"] = {"speed_change_pct_per_hour": 100 * (np.exp(
        slope_per_h) - 1),
        "by_hour": {str(k): [int(r.n), float(100 * (np.exp(r.res) - 1))]
                    for k, r in fat.iterrows()}}
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    mids = [i.mid for i in fat.index]
    ax.plot(mids, 100 * (np.exp(fat.res) - 1), "o-", color=BLUE, lw=2)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("hours since the start of the outing")
    ax.set_ylabel("speed vs the hike's own average (%),\nafter slope")
    ax.set_title(f"Fatigue: {nums['fatigue']['speed_change_pct_per_hour']:+.1f}"
                 "% per hour (within outings)", fontsize=9)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / "fig_fatigue.png", dpi=170)
    plt.close(fig)

    # 4. asymmetry: out-and-back pairs, all regions
    pairs = []
    sw = w[w.way_dir != 0]
    for (oid, wid), d in sw.groupby(["outing_id", "osm_way_id"]):
        a, c = d[d.way_dir == 1], d[d.way_dir == -1]
        if len(a) < 2 or len(c) < 2:
            continue
        sa, sc = a.slope.mean(), c.slope.mean()
        va = a.length_m.sum() / a.moving_s.sum() * 3.6
        vc = c.length_m.sum() / c.moving_s.sum() * 3.6
        (vu, su), (vd, sd) = ((va, sa), (vc, sc)) if sa > sc else \
            ((vc, sc), (va, sa))
        grade = (abs(sa) + abs(sc)) / 2
        if grade >= 0.03 and su > 0 and sd < 0:
            pairs.append({"outing_id": oid, "region": d.region.iloc[0],
                          "grade": grade, "ratio": vd / vu})
    p = pd.DataFrame(pairs)

    def boot_med(df, n=1000):
        g = {o: x.ratio.to_numpy() for o, x in df.groupby("outing_id")}
        ids = list(g)
        meds = [np.median(np.concatenate([g[i] for i in rng.choice(
            ids, len(ids))])) for _ in range(n)]
        return [float(x) for x in np.percentile(meds, [2.5, 97.5])]
    asym = {"pairs": int(len(p)), "outings": int(p.outing_id.nunique()),
            "all": [float(p.ratio.median()), boot_med(p)], "by_grade": {}}
    for lo, hi in ((0.03, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 1.0)):
        q = p[(p.grade >= lo) & (p.grade < hi)]
        if q.outing_id.nunique() >= 10:
            asym["by_grade"][f"{lo:.2f}-{hi:.2f}"] = [
                float(q.ratio.median()), boot_med(q), int(len(q))]
    asym["by_region"] = {r: [float(q.ratio.median()), int(len(q))]
                         for r, q in p.groupby("region") if len(q) >= 20}
    nums["asymmetry"] = asym
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    gb = asym["by_grade"]
    xs = np.arange(len(gb))
    for i, (k, (m, (lo, hi), n)) in enumerate(gb.items()):
        ax.errorbar(i, m, yerr=[[m - lo], [hi - m]], fmt="o", color=BLUE,
                    ms=7, capsize=4, lw=2)
        ax.text(i + 0.1, m, f"{n} pairs", fontsize=7.5, va="center")
    ax.axhline(np.exp(0.35), color=MUTED, ls="--", lw=1.2)
    ax.text(len(gb) - 0.6, np.exp(0.35) + 0.01, "Tobler 1.42", fontsize=8,
            color=MUTED)
    ax.axhline(1, color=GRID, lw=1)
    ax.set_xticks(xs)
    ax.set_xticklabels([k.replace("-", "–") for k in gb])
    ax.set_xlabel("trail grade")
    ax.set_ylabel("speed down / speed up\n(same hiker, same trail)")
    ax.set_title(f"Out-and-back pairs, all regions: {asym['pairs']:,} "
                 f"pairs from {asym['outings']:,} outings", fontsize=9)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / "fig_asymmetry.png", dpi=170)
    plt.close(fig)

    (OUT / "numbers.json").write_text(json.dumps(nums, indent=2))
    print(json.dumps({k: nums[k] for k in ("best_form",
                                           "variance_split_outing",
                                           "variance_between_regions_pct_of_total",
                                           "fatigue", "asymmetry")},
                     indent=1))


if __name__ == "__main__":
    main()
