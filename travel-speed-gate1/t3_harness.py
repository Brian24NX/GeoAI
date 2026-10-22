#!/usr/bin/env python3
"""
The T3 evaluation harness, run on the T1 data now (plan sec. 10;
docs/NEXT_STEPS.md sec. 5). Every arm predicts the DISTRIBUTION of log
speed of a walking trail segment, and every arm is scored the same way on
the same held-out segments.

Arms (T1 features only for now; the remote-sensing arms plug into ARMS
when T2's covariates exist):
  tobler         Tobler 1993, published constants, nothing fitted
  campbell       Campbell, Dennison & Thompson 2022 (CEUS 97:101866), the
                 published median (50th percentile) Lorentz curve from
                 ~2,000 AllTrails hikes in Utah and California (Table A3)
  stride         STRIDE (Campbell, Cutler & Dennison 2024; R package
                 `stride`, bld_tm): Lorentz(slope) / (1 + 15.265 density +
                 16.505 roughness), m/s, from field walks; needs the 1 m
                 covariate rough_stride; density = 0 here.
                 stride_refit: the same form fitted to our hikes.
                 stride_dns / stride_dns_refit: the full model, with the
                 lidar understory density nrd (t2_lidarveg.py) when the
                 covariates include it
  terrain_curve  Tobler's form with peak speed and slope sensitivity
                 linear in steppiness (SD of 5 m pitches, pitch_sd_5m):
                 ln v = a0 + a1 z - (k0 + k1 z)|s + s0|, z = steppiness /
                 0.10 (t4_terrain_curve.py); 5 numbers, a drop-in Tobler
  tobler_refit   Tobler's tent shape, refitted (= the T1 slope fit)
  slope_curve    our rounded-top asymmetric curve (t1_findings
                 smooth_asym), refitted: the slope-only baseline
  lorentz_refit  a Lorentz-shaped curve (Campbell et al.), refitted
  lin_tags       the slope curve + additive offsets per OSM tag value
                 (ridge, penalty picked on held-out outings): the
                 structured Tags arm, Wood et al. style
  gbm_slope      gradient-boosted trees on slope alone
  gbm_tags       gradient-boosted trees on slope + OSM trail tags: the
                 Tags arm
  place_memory   the slope curve + how much faster or slower OTHER hikers
                 went in the same 100 m cell (outing-demeaned residuals,
                 shrunk; penalty picked on held-out outings). Not a usable
                 model in a new region (there it equals slope_curve); within
                 a region it is the CEILING for anything place-based
                 (tags, remote sensing)
Reference (LORO only): slope_curve_local = the slope curve fitted on
other outings of the SAME region: what local data would buy.

Personal pace ("+me" rows, subset "rest"): for traces with >= 2 km of
walking trail, the first 1 km (20 segments, in time order) tells the
hiker's pace that day (median residual); the rest of the trace is then
predicted with that offset. Shows how much is the hiker, not the trail.

Splits (never by segment):
  outing5   5 folds of outings, all regions pooled
  block5    5 folds of 10 km blocks
  loro      leave one region out (17 folds): the paper's headline
  time      (on request) train on outings up to TIME_CUT, test on the later
            ones: does a model from older hikes hold for newer ones?
            Outings with a doubtful date are in neither part.
  macro     (on request) leave one ZONE out (5 folds: Northeast, Southern
            Appalachians, Rockies, Pacific Northwest, California): no
            neighbouring region in training
  eastwest  (on request) train on the West, test on the East, and back
  hiker5    (on request) 5 folds of uploaders: hikers the model never saw
            (an anonymous trace is its own uploader). outing5 can put a
            hiker's other outings in training.
  loro_hiker (on request) leave one region out AND drop from training every
            outing by an uploader who walked in the held-out region

Spread. Each arm's predictive distribution = its point prediction + the
quantiles of its residuals on held-out outings of the TRAINING data
(outings split 70 / 15 / 15: fit, early stopping, calibration), so every
arm is calibrated the same honest way, and under LORO the calibration
must transfer too.

Subsets: all; tagged (sac_scale, visibility, smoothness or mtb_scale
present); rest (segments after a trace's first km, where "+me" applies);
gps_le2 / gps_2to10 / gps_gt10 (the trace's recording interval in s: is a
gain still there where speeds are measured best?); down_steep / down /
level / up / up_steep (slope in the walking direction: < -15%, -15 to
-5%, -5 to 5%, 5 to 15%, >= 15%). skill_ci_subsets.csv has their
bootstrap intervals.
Metrics (log speed unless noted): RMSE, MAE, MAE km/h, CRPS (log and
km/h), coverage of the central 50% and 90% intervals, PIT histogram, and
moving-time errors over 1 km stretches (20 consecutive segments of one
trace) and whole hikes (traces with >= 2 km of walking trail segments).
Single segments are noisy (GPS); stretch and hike times are what matters
to a hiker.

Output: results/t3_harness/ metrics.csv, loro_by_region.csv, pit.csv,
        importance.csv (gbm_tags, LORO), tag_effects.csv (lin_tags on all
        data), summary.json, fig_harness.png
Run (cluster, 8 CPUs; after t1_combine.py):  python t3_harness.py
     (python t3_harness.py --quick: 15% of outings, a smoke test)
T2 covariates: --covariates file.parquet ... (segment_id + numeric
columns) adds the remote-sensing arms lin_rs, lin_both, gbm_rs, gbm_both.
Pilot in one region: --regions wm --splits outing5 block5 --out <dir>
"""

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

import regions
import t1_findings as tf

SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("results/t3_harness")
SEED = 0
QL = (np.arange(100) + 0.5) / 100           # residual quantile levels
MIN_TRACE_KM = 2.0                          # whole-hike time error
ME_SEGS = 20                 # personal pace from a trace's first 1 km
PLACE_M = 100                # place-memory cell size (m, UTM grid)
KAPPAS = [2, 5, 10, 20, 50, 100]   # place-memory shrinkage (segments)
SPLITS = ["outing5", "block5", "loro"]
TIME_CUT, TIME_TEST = 2019, "after"      # time split: test = after 2019
ZONES = {"wm": "northeast", "adk": "northeast", "catskills": "northeast",
         "greenmtn": "northeast", "shenandoah": "southeast",
         "smokies": "southeast", "pisgah": "southeast",
         "frontrange": "rockies", "wasatch": "rockies",
         "cascades": "pacific_nw", "gorge": "pacific_nw",
         "olympic": "pacific_nw", "northshore": "pacific_nw",
         "bayarea": "california", "sangabriel": "california",
         "yosemite": "california", "tahoe": "california"}
REGION_SPLITS = ("loro", "loro_hiker", "macro", "eastwest")  # units = regions
GPS_SUBSETS = {"gps_le2": (0, 2), "gps_2to10": (2, 10),
               "gps_gt10": (10, np.inf)}  # recording interval (s], per trace
SLOPE_SUBSETS = {"down_steep": (-1, -0.15), "down": (-0.15, -0.05),
                 "level": (-0.05, 0.05), "up": (0.05, 0.15),
                 "up_steep": (0.15, 1)}   # slope [lo, hi), walking direction
EXTRA_SUBSETS = [*GPS_SUBSETS, *SLOPE_SUBSETS]

# ------------------------------------------------------------ features
SAC = {"strolling": 0, "hiking": 1, "mountain_hiking": 2,
       "demanding_mountain_hiking": 3, "alpine_hiking": 4,
       "demanding_alpine_hiking": 5, "difficult_alpine_hiking": 6}
VIS = {"excellent": 1, "good": 2, "medium": 3, "intermediate": 3,
       "intermittent": 4, "poor": 4, "bad": 4, "very_bad": 5,
       "horrible": 5, "no": 6}
SMOOTH = {"excellent": 1, "good": 2, "intermediate": 3, "bad": 4,
          "very_bad": 5, "horrible": 6, "very_horrible": 7,
          "impassable": 8}
MIN_LEVEL = 200          # rarer category values are pooled into "other"


def _first(col):
    return col.astype("object").map(
        lambda x: x.split(";")[0].strip() if isinstance(x, str) else None)


def _num(x):
    m = re.match(r"\s*([0-9]*\.?[0-9]+)", x) if isinstance(x, str) else None
    return float(m.group(1)) if m else np.nan


def _cat(col):
    col = _first(col)
    counts = col.value_counts()
    keep = set(counts[counts >= MIN_LEVEL].index)
    return pd.Categorical(col.map(lambda x: x if x is None or x in keep
                                  else "other"))


def tag_features(s):
    """OSM tags as model inputs; missing stays missing (trees use it)."""
    X = pd.DataFrame(index=s.index)
    X["sac_scale"] = _first(s.tag_sac_scale).map(SAC).astype(float)
    X["trail_visibility"] = _first(s.tag_trail_visibility).map(VIS) \
        .astype(float)
    X["smoothness"] = _first(s.tag_smoothness).map(SMOOTH).astype(float)
    X["mtb_scale"] = _first(s.tag_mtb_scale).map(_num)
    X["width_m"] = _first(s.tag_width).map(_num).clip(upper=10)
    X["surface"] = _cat(s.tag_surface)
    X["highway"] = _cat(s.tag_highway)
    X["permission"] = _cat(s.permission)
    return X


def onehot(X):
    """Tag frame -> 0/1 columns, one per value and one per "missing"
    (width in bins), for the additive arms. Columns: (feature, value)."""
    parts, keys = [], []
    for c in X.columns:
        col = X[c]
        if c == "width_m":
            col = pd.cut(col, [0, 0.5, 1.0, 2.0, np.inf], right=False)
        col = col.astype("object").where(col.notna(), "missing")
        d = pd.get_dummies(col.astype(str), dtype=float)
        keys += [(c, v) for v in d.columns]
        parts.append(d)
    out = pd.concat(parts, axis=1)
    out.columns = pd.MultiIndex.from_tuples(keys, names=["feature", "value"])
    return out


def varying(X):
    """Drop columns with fewer than 2 distinct values (e.g. a tag nobody
    uses in the regions kept): trees can't bin them."""
    return X[[c for c in X.columns if X[c].nunique(dropna=True) >= 2]]


def binned(X, q=10):
    """Continuous covariates -> decile bins (missing stays missing), so
    the additive arms can learn any shape."""
    out = pd.DataFrame(index=X.index)
    for c in X.columns:
        out[c] = pd.qcut(X[c], q, duplicates="drop")
    return out


def ridge(Z, e, lam):
    """Ridge regression with an unpenalized intercept: (coef, intercept)."""
    mz, me = Z.mean(0), e.mean()
    Zc = Z - mz
    b = np.linalg.solve(Zc.T @ Zc + lam * np.eye(Z.shape[1]),
                        Zc.T @ (e - me))
    return b, me - mz @ b


# ---------------------------------------------------------------- arms
# kind: fixed (published), form (a t1_findings curve, refitted), lin (the
# slope curve + additive offsets, ridge on one-hot features: the
# structured, Wood-style model) or gbm (trees on the named feature
# blocks). T2 adds e.g.
#   "lin_rs":   ("lin", ["rs"]),       "gbm_rs":   ("gbm", ["slope", "rs"]),
#   "lin_both": ("lin", ["tags_1h", "rs"]),  "gbm_both": (...)
ARMS = {
    "tobler": ("fixed", "tobler"),
    "campbell": ("fixed", "campbell"),
    "tobler_refit": ("form", "tobler"),
    "slope_curve": ("form", "smooth_asym"),
    "lorentz_refit": ("form", "lorentz"),
    "lin_tags": ("lin", ["tags_1h"]),
    "gbm_slope": ("gbm", ["slope"]),
    "gbm_tags": ("gbm", ["slope", "tags"]),
    "place_memory": ("place", None),
}
BASELINE = "slope_curve"
RS_ARMS = {                      # added when --covariates are given
    "lin_rs": ("lin", ["rs_1h"]),
    "lin_both": ("lin", ["tags_1h", "rs_1h"]),
    "gbm_rs": ("gbm", ["slope", "rs"]),
    "gbm_both": ("gbm", ["slope", "tags", "rs"]),
}
RS_SKIP = {"segment_id", "dem1m_cover", "slope_1m",   # not terrain beyond
           "n_pts"}                       # (lidar points: the flight, not the trail)
                                                      # slope
LAMBDAS = [1e-4, 1e-3, 1e-2, 1e-1, 1.0]   # ridge penalty per segment


def tobler(s):
    return np.log(6.0) - 3.5 * np.abs(s + 0.05)


def campbell(s):
    """ln km/h of Campbell et al. 2022's 50th percentile model:
    r = c / (pi b (1 + ((S - a) / b)^2)) + d + e S, r in m/s, S = slope in
    degrees (Table A3: a -1.4579, b 22.0787, c 76.3271, d 0.0525,
    e -3.2002e-4). Peak 1.15 m/s (4.15 km/h) near -1.5 degrees."""
    a, b, c, d, e = -1.4579, 22.0787, 76.3271, 0.0525, -3.2002e-4
    deg = np.degrees(np.arctan(s))
    r = c / (np.pi * b * (1 + ((deg - a) / b) ** 2)) + d + e * deg
    return np.log(3.6 * np.clip(r, 0.05, None))


FIXED = {"tobler": tobler, "campbell": campbell}
STRIDE = (-2.320, 26.315, 147.362, 16.505)   # a, b, c, e (bld_tm.R)
STRIDE_D = 15.265                             # d, the density term


def terrain_curve(s, z, a0, a1, k0, k1, s0):
    return a0 + a1 * z - (k0 + k1 * z) * np.abs(s + s0)


def stride(s, rgh, a, b, c, e, d=0.0, dns=0.0):
    """ln km/h of the STRIDE form, slope s as rise/run, roughness rgh in m,
    understory density dns (share of returns at 0.85-1.20 m)."""
    deg = np.degrees(np.arctan(s))
    r = c / (np.pi * b * (1 + ((deg - a) / b) ** 2)) / (1 + d * dns
                                                         + e * rgh)
    return np.log(3.6 * np.clip(r, 1e-3, None))


def gbm():
    return HistGradientBoostingRegressor(
        learning_rate=0.05, max_iter=1000, max_leaf_nodes=31,
        min_samples_leaf=200, l2_regularization=1.0, early_stopping=True,
        n_iter_no_change=30, random_state=SEED)


class Arm:
    """Fit on (fit, stop) rows, residual quantiles on the cal rows."""

    def __init__(self, name, blocks):
        self.name = name
        self.kind, self.spec = ARMS[name]
        self.blocks = blocks

    def X(self, idx):
        return pd.concat([self.blocks[b].iloc[idx] for b in self.spec],
                         axis=1)

    def Z(self, idx):
        return np.hstack([self.blocks[b][idx] for b in self.spec])

    def fit(self, s, y, fit, stop, cal, lambdas=LAMBDAS):
        if self.kind == "form":
            both = np.r_[fit, stop]
            self.p = tf.fit_form(self.spec, s[both], y[both])
        elif self.kind == "lin":
            curve = tf.FORMS["smooth_asym"][0]
            both = np.r_[fit, stop]
            self.p = tf.fit_form("smooth_asym", s[both], y[both])
            ef, es = y[fit] - curve(self.p, s[fit]), \
                y[stop] - curve(self.p, s[stop])
            Zf, Zs = self.Z(fit), self.Z(stop)
            mse = []
            for lam in lambdas:
                b, b0 = ridge(Zf, ef, lam * len(fit))
                mse.append(np.mean((es - Zs @ b - b0) ** 2))
            self.lam = lambdas[int(np.argmin(mse))]
            self.b, self.b0 = ridge(np.vstack([Zf, Zs]), np.r_[ef, es],
                                    self.lam * len(both))
        elif self.kind == "place":
            curve = tf.FORMS["smooth_asym"][0]
            both = np.r_[fit, stop]
            self.p = tf.fit_form("smooth_asym", s[both], y[both])
            cell = self.blocks["cell"]
            base = y[stop] - curve(self.p, s[stop])
            mse = [np.mean((base - self._cells(s, y, fit, k)[cell[stop]])
                           ** 2) for k in KAPPAS]
            self.kappa = KAPPAS[int(np.argmin(mse))]
            self.v = self._cells(s, y, both, self.kappa)
        elif self.kind == "stride":
            rgh = self.blocks["stride_rgh"]
            dns = self._dns()
            if self.spec.startswith("published"):
                self.p = STRIDE + ((STRIDE_D,) if self.spec.endswith("dns")
                                   else ())
            else:
                from scipy.optimize import least_squares
                both = np.r_[fit, stop]
                x0, lo, hi = list(STRIDE), [-15, 5, 1, 0], [15, 80, 2000, 200]
                if self.spec.endswith("dns"):
                    x0, lo, hi = x0 + [STRIDE_D], lo + [0], hi + [500]
                res = least_squares(
                    lambda q: stride(s[both], rgh[both], *q,
                                     dns=dns[both]) - y[both],
                    x0=x0, loss="soft_l1", f_scale=0.3, bounds=(lo, hi))
                self.p = tuple(res.x)
        elif self.kind == "tcurve":
            from scipy.optimize import least_squares
            z, both = self.blocks["steppy"], np.r_[fit, stop]
            self.p = tuple(least_squares(
                lambda q: terrain_curve(s[both], z[both], *q) - y[both],
                [1.45, -0.1, 1.8, 0.2, 0.05], loss="soft_l1",
                f_scale=0.3).x)
        elif self.kind == "gbm":
            Xf = self.X(fit)
            # a numeric column with < 2 values in THIS fold's training rows
            # can't be binned (e.g. a tag nobody uses in the eastern regions)
            self.cols = [c for c in Xf.columns
                         if isinstance(Xf[c].dtype, pd.CategoricalDtype)
                         or Xf[c].nunique(dropna=True) >= 2]
            self.m = gbm().fit(Xf[self.cols], y[fit],
                               X_val=self.X(stop)[self.cols], y_val=y[stop])
        self.r = np.quantile(y[cal] - self.predict(s, cal), QL)
        if self.kind == "fixed" or (self.kind == "stride"
                                    and self.spec.startswith("published")):
            # a published curve keeps its level:
            self.r -= np.median(self.r)   # spread from data, no recentering
        return self

    def _dns(self):
        """STRIDE's understory density for the _dns variants, else 0."""
        if self.spec.endswith("dns"):
            return self.blocks["stride_dns"]
        return np.zeros(len(self.blocks["stride_rgh"]))

    def _cells(self, s, y, rows, kappa):
        """Shrunken mean residual per cell, each outing's mean removed
        first (so a cell walked by one fast hiker doesn't look fast)."""
        cell, out = self.blocks["cell"], self.blocks["outing"]
        e = y[rows] - tf.FORMS["smooth_asym"][0](self.p, s[rows])
        o, c = out[rows], cell[rows]
        n_o = np.bincount(o, minlength=out.max() + 1)
        e = e - (np.bincount(o, e, minlength=len(n_o))
                 / np.maximum(n_o, 1))[o]
        m = cell.max() + 1
        return np.bincount(c, e, minlength=m) / (
            np.bincount(c, minlength=m) + kappa)

    def predict(self, s, idx):
        if self.kind == "fixed":
            return FIXED[self.spec](s[idx])
        if self.kind == "stride":
            return stride(s[idx], self.blocks["stride_rgh"][idx], *self.p,
                          dns=self._dns()[idx])
        if self.kind == "tcurve":
            return terrain_curve(s[idx], self.blocks["steppy"][idx],
                                 *self.p)
        if self.kind == "form":
            return tf.FORMS[self.spec][0](self.p, s[idx])
        if self.kind == "lin":
            return (tf.FORMS["smooth_asym"][0](self.p, s[idx])
                    + self.Z(idx) @ self.b + self.b0)
        if self.kind == "place":
            return (tf.FORMS["smooth_asym"][0](self.p, s[idx])
                    + self.v[self.blocks["cell"][idx]])
        return self.m.predict(self.X(idx)[self.cols])


HET_ARMS = ["slope_curve", "lin_tags", "lin_rs", "gbm_rs"]


def heteroscedastic(arm, s, y, cal, te, blocks, rng):
    """A spread that depends on the segment: log |residual| modeled by
    small trees on slope (+ the arm's own tag / remote-sensing features)
    on half of the calibration outings; the residuals standardized by it
    on the other half give the quantiles. Returns (scale on te, quantiles)."""
    names = ["slope"] + (["tags"] if "tags" in str(arm.spec) else []) \
        + (["rs"] if "rs" in str(arm.spec) and "rs" in blocks else [])
    X = pd.concat([blocks[b] for b in names], axis=1)
    out = blocks["outing"]
    u = rng.permutation(np.unique(out[cal]))
    a_ = np.isin(out[cal], u[: len(u) // 2])
    ca, cb = cal[a_], cal[~a_]
    ea = np.abs(y[ca] - arm.predict(s, ca)) + 1e-3
    m = HistGradientBoostingRegressor(learning_rate=0.05, max_iter=200,
                                      max_leaf_nodes=15, min_samples_leaf=500,
                                      l2_regularization=1.0,
                                      random_state=SEED)
    m.fit(X.iloc[ca], np.log(ea))
    sb = np.exp(m.predict(X.iloc[cb]))
    sb /= np.median(sb)
    r = np.quantile((y[cb] - arm.predict(s, cb)) / sb, QL)
    st = np.exp(m.predict(X.iloc[te])) / np.median(np.exp(m.predict(
        X.iloc[cb])))
    return st, r


def first_km(arm, s, y, rows, blocks):
    """The "rest" rows among `rows` and, for each, its trace's median
    residual on the trace's first ME_SEGS segments (the hiker's pace)."""
    calib, rest, trace = blocks["calib"], blocks["rest"], blocks["trace"]
    c, r = rows[calib[rows]], rows[rest[rows]]
    if not len(c) or not len(r):
        return r, np.empty(0)
    off = pd.Series(y[c] - arm.predict(s, c)).groupby(trace[c]).median()
    off = off.reindex(trace[r]).to_numpy()
    keep = ~np.isnan(off)            # first km in another fold (blocks)
    return r[keep], off[keep]


def personal(arm, s, y, cal, te, blocks):
    """Personal-pace predictions for the test "rest" rows. The first-km
    offset is noisy, so it is shrunk: rest-of-trace mean residual = a +
    beta * offset, fitted on the calibration outings. Returns test rows,
    predictions, residual quantiles, beta."""
    rc, oc = first_km(arm, s, y, cal, blocks)
    rt, ot = first_km(arm, s, y, te, blocks)
    if len(rc) < 1000 or not len(rt):
        return rt, None, None, None
    pc = arm.predict(s, rc)
    g = pd.DataFrame({"t": blocks["trace"][rc], "e": y[rc] - pc, "o": oc}) \
        .groupby("t").mean()
    beta, a = np.polyfit(g.o, g.e, 1)
    r_me = np.quantile(y[rc] - (pc + a + beta * oc), QL)
    return rt, arm.predict(s, rt) + a + beta * ot, r_me, beta


# ------------------------------------------------------------- scoring
def score_rows(pred, r, y, scale=None):
    """Per-segment CRPS (log, km/h), PIT and interval hits for the
    predictive distribution pred + scale * r (r = residual quantiles;
    scale = 1 everywhere unless a per-segment spread is given)."""
    n, M = len(y), len(r)
    r = np.sort(r)
    sc = np.ones(n) if scale is None else np.asarray(scale, float)
    crps_log, crps_kmh, pit = np.empty(n), np.empty(n), np.empty(n)
    tf_ = np.empty(n)
    w = (2 * np.arange(1, M + 1) - M - 1) / M ** 2   # E|X - X'| / 2 for
    half_r = float(r @ w)                            # sorted samples
    v = np.exp(y)
    for a in range(0, n, 20000):
        b = slice(a, a + 20000)
        q = sc[b, None] * r[None, :]                  # per-row quantiles
        z = pred[b, None] + q
        crps_log[b] = np.abs(z - y[b, None]).mean(1) - sc[b] * half_r
        eq = np.exp(q)                                # sorted per row
        ez = np.exp(pred[b])
        crps_kmh[b] = (np.abs(ez[:, None] * eq - v[b, None]).mean(1)
                       - ez * (eq @ w))
        pit[b] = (z <= y[b, None]).mean(1)
        tf_[b] = np.exp(-q).mean(1)
    lo50, hi50, lo90, hi90 = np.quantile(r, [0.25, 0.75, 0.05, 0.95])
    e = (y - pred) / sc
    return {"crps_log": crps_log, "crps_kmh": crps_kmh, "pit": pit,
            "in50": (e >= lo50) & (e <= hi50),
            "in90": (e >= lo90) & (e <= hi90),
            "time_factor": tf_}


def summarize(d):
    """Metrics of one arm on a set of scored segments (a DataFrame)."""
    e = d.y - d.pred
    out = {"segments": len(d),
           "rmse_log": float(np.sqrt(np.mean(e ** 2))),
           "mae_log": float(np.mean(np.abs(e))),
           "mae_kmh": float(np.mean(np.abs(np.exp(d.pred) - np.exp(d.y)))),
           "bias_log": float(np.mean(e)),
           "r2_log": float(1 - np.mean(e ** 2) / np.var(d.y)),
           "crps_log": float(d.crps_log.mean()),
           "crps_kmh": float(d.crps_kmh.mean()),
           "cov50": float(d.in50.mean()), "cov90": float(d.in90.mean())}
    # whole-hike moving time on the trace's walking trail segments
    t = d.assign(t_pred=3.6 * d.length_m * np.exp(-d.pred) * d.time_factor)
    g = t.groupby("trace_id").agg(km=("length_m", "sum"),
                                  t=("moving_s", "sum"),
                                  t_pred=("t_pred", "sum"))
    g = g[g.km >= MIN_TRACE_KM * 1000]
    err = g.t_pred / g.t - 1
    st = t.groupby("stretch").agg(n=("length_m", "size"),
                                  t=("moving_s", "sum"),
                                  t_pred=("t_pred", "sum"))
    lr = np.log(st.t_pred / st.t)[st.n == ME_SEGS]
    out.update({"stretches_1km": int(len(lr)),
                "stretch_rmse_log": float(np.sqrt(np.mean(lr ** 2)))
                if len(lr) else np.nan,
                "stretch_ape_median": float(np.median(np.abs(np.expm1(lr))))
                if len(lr) else np.nan})
    out.update({"hikes": len(g),
                "time_ape_median": float(np.median(np.abs(err)))
                if len(g) else np.nan,
                "time_err_median": float(np.median(err))
                if len(g) else np.nan})
    return out


# -------------------------------------------------------------- splits
def outer_folds(w, how, rng):
    if how in ("loro", "loro_hiker"):
        return w.region.to_numpy()
    if how == "macro":
        return w.region.map(ZONES).to_numpy(dtype=object)
    if how == "eastwest":
        east = w.region.map(ZONES).isin(["northeast", "southeast"])
        return np.where(east, "east", "west").astype(object)
    if how == "time":            # None = doubtful date: in neither part
        o = w.groupby("outing_id")
        later = o.year.transform("min").to_numpy() > TIME_CUT
        bad = o.date_suspect.transform("max").to_numpy(bool)
        return np.where(bad, None, np.where(later, TIME_TEST, "until"))
    groups = {"outing5": w.outing_id, "hiker5": w.uploader}.get(
        how, w.block_10km)
    u = rng.permutation(np.asarray(groups.unique(), dtype=object))
    return groups.map({g: i % 5 for i, g in enumerate(u)}).to_numpy()


def inner_split(outings, rng):
    """Outings of the training rows -> fit / stop / cal masks (70/15/15)."""
    u = rng.permutation(np.asarray(outings.unique(), dtype=object))
    part = dict(zip(u, (np.arange(len(u)) * 20 // len(u))))
    k = outings.map(part).to_numpy()
    return k < 14, (k >= 14) & (k < 17), k >= 17


def load():
    cols = ["region", "segment_id", "trace_id", "outing_id", "block_10km",
            "uploader",
            "slope",
            "speed_kmh", "length_m", "moving_s", "permission",
            "tag_surface", "tag_sac_scale", "tag_width",
            "tag_trail_visibility", "tag_smoothness", "tag_mtb_scale",
            "tag_highway", "analysis_walk", "lat0", "lon0", "lat1",
            "lon1", "t_start", "year", "date_suspect", "native_interval_s"]
    w = pd.read_parquet(SEG, columns=cols)
    w = w[w.analysis_walk & (w.speed_kmh > 0)
          & w.slope.between(-0.6, 0.6)].reset_index(drop=True)
    w["y"] = np.log(w.speed_kmh)
    for name, (lo, hi) in GPS_SUBSETS.items():
        w[name] = (w.native_interval_s > lo) & (w.native_interval_s <= hi)
    for name, (lo, hi) in SLOPE_SUBSETS.items():
        w[name] = (w.slope >= lo) & (w.slope < hi)
    w["tagged"] = w[["tag_sac_scale", "tag_trail_visibility",
                     "tag_smoothness", "tag_mtb_scale"]].notna().any(axis=1)
    return w


def place_cells(w):
    """Code of the PLACE_M x PLACE_M UTM cell holding each segment's
    midpoint."""
    cell = np.empty(len(w), dtype=object)
    for key, idx in w.groupby("region").indices.items():
        to_utm = Transformer.from_crs(4326, regions.utm_epsg(key),
                                      always_xy=True)
        x, yy = to_utm.transform(((w.lon0 + w.lon1) / 2).to_numpy()[idx],
                                 ((w.lat0 + w.lat1) / 2).to_numpy()[idx])
        cell[idx] = [f"{key}_{a}_{b}" for a, b in
                     zip((x // PLACE_M).astype(int),
                         (yy // PLACE_M).astype(int))]
    return pd.factorize(cell)[0]


def personal_flags(w):
    """calib = a trace's first ME_SEGS segments in time order, rest = the
    others; only traces with >= 2 * ME_SEGS segments."""
    o = w.sort_values(["trace_id", "t_start"])
    rank = o.groupby("trace_id").cumcount().to_numpy()
    size = o.groupby("trace_id").trace_id.transform("size").to_numpy()
    ok = size >= 2 * ME_SEGS
    calib, rest = np.zeros(len(w), bool), np.zeros(len(w), bool)
    calib[o.index[ok & (rank < ME_SEGS)]] = True
    rest[o.index[ok & (rank >= ME_SEGS)]] = True
    stretch = np.empty(len(w), dtype=np.int64)       # 1 km stretches
    stretch[o.index] = pd.factorize(o.trace_id)[0] * 100000 + rank // ME_SEGS
    return calib, rest, stretch


# ---------------------------------------------------------------- main
def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--figure", action="store_true",
                    help="only redraw fig_harness.png from the CSVs")
    ap.add_argument("--regions", nargs="*", help="only these regions")
    ap.add_argument("--splits", nargs="*", default=SPLITS,
                    choices=SPLITS + ["time", "macro", "eastwest",
                                      "hiker5", "loro_hiker"])
    ap.add_argument("--covariates", nargs="*", default=[],
                    help="T2 covariate tables: segment_id + numeric columns")
    ap.add_argument("--features", nargs="*",
                    help="use only these covariate columns")
    ap.add_argument("--hetero", action="store_true",
                    help="add +het arms: a spread that depends on the "
                         "segment (slope, tags, remote sensing)")
    ap.add_argument("--region-fe", action="store_true",
                    help="add arms with a shrunken offset per region (a "
                         "check: does a covariate add more than the "
                         "region's mean speed?)")
    ap.add_argument("--save-folds", action="store_true",
                    help="also write the folds for models built outside the "
                         "harness: folds_segments.parquet (each segment's "
                         "outer fold per split) and folds_inner.parquet (the "
                         "fit / stop / cal outings of every fold)")
    ap.add_argument("--out", help="output folder (default results/t3_harness)")
    args = ap.parse_args()
    quick, splits = args.quick, args.splits
    if args.out:
        OUT = Path(args.out)
    if args.figure:
        met = pd.read_csv(OUT / "metrics.csv")
        figure(met[~met.arm.str.endswith("+me")],
               pd.read_csv(OUT / "loro_by_region.csv"), SPLITS)
        return
    t0 = time.time()
    w = load()
    if args.regions:
        w = w[w.region.isin(args.regions)].reset_index(drop=True)
    rs_cols = []
    if args.covariates:
        # stack every file (columns may differ: kinds, or a region with
        # no data), then one row per (region, segment), first non-missing
        # value. The region comes from the file name (<kind>_<region>); a
        # segment id alone is not unique: a trace built in two regions
        # repeats ids (decision #118)
        cov = pd.concat([pd.read_parquet(f).assign(
            region=Path(f).stem.rsplit("_", 1)[-1]) for f in args.covariates],
            ignore_index=True)
        cov = cov.groupby(["region", "segment_id"], sort=False
                          ).first().reset_index()
        rs_cols = [c for c in cov.columns if c not in RS_SKIP
                   and c != "region"
                   and not c.startswith("dem1m_cover")
                   and pd.api.types.is_numeric_dtype(cov[c])
                   and (not args.features or c in args.features)]
        w = w.merge(cov[["region", "segment_id"] + rs_cols],
                    on=["region", "segment_id"], how="left"
                    ).reset_index(drop=True)
        ARMS.update(RS_ARMS)
    rng = np.random.default_rng(SEED)
    if quick:
        keep = rng.permutation(np.asarray(w.outing_id.unique(), dtype=object))
        keep = set(keep[:len(keep) * 15 // 100])
        w = w[w.outing_id.isin(keep)].reset_index(drop=True)
        OUT = OUT.with_name(OUT.name + "_quick")
    OUT.mkdir(parents=True, exist_ok=True)
    blocks = {"slope": w[["slope"]], "tags": varying(tag_features(w))}
    oh = onehot(blocks["tags"])
    blocks["tags_1h"] = oh.to_numpy()
    if "pitch_sd_5m" in rs_cols:             # the terrain-adjusted curve
        z = w["pitch_sd_5m"] / 0.10
        blocks["steppy"] = z.fillna(z.median()).to_numpy()
        ARMS["terrain_curve"] = ("tcurve", None)
    if "rough_stride" in rs_cols:            # STRIDE needs its roughness
        r = w["rough_stride"]
        blocks["stride_rgh"] = r.fillna(r.median()).to_numpy()
        ARMS["stride"] = ("stride", "published")
        ARMS["stride_refit"] = ("stride", "refit")
        if "nrd" in rs_cols:                 # ... and its density
            d = w["nrd"]
            blocks["stride_dns"] = d.fillna(d.median()).to_numpy()
            ARMS["stride_dns"] = ("stride", "published_dns")
            ARMS["stride_dns_refit"] = ("stride", "refit_dns")
    if rs_cols:
        blocks["rs"] = varying(w[rs_cols])
        blocks["rs_1h"] = onehot(binned(w[rs_cols])).to_numpy()
        print(f"remote-sensing covariates: {rs_cols}; present for "
              f"{w[rs_cols].notna().all(axis=1).mean():.0%} of segments",
              flush=True)
    if args.region_fe:
        blocks["region_1h"] = pd.get_dummies(w.region).to_numpy(float)
        ARMS["lin_region"] = ("lin", ["region_1h"])
        ARMS["lin_tags_region"] = ("lin", ["tags_1h", "region_1h"])
        if rs_cols:
            ARMS["lin_rs_region"] = ("lin", ["rs_1h", "region_1h"])
    blocks["cell"] = place_cells(w)
    blocks["outing"] = pd.factorize(w.outing_id)[0]
    blocks["trace"] = pd.factorize(w.trace_id)[0]
    blocks["calib"], blocks["rest"], w["stretch"] = personal_flags(w)
    w["rest"] = blocks["rest"]
    s, y = w.slope.to_numpy(), w.y.to_numpy()
    print(f"{len(w):,} walking segments, {w.outing_id.nunique():,} outings,"
          f" {w.region.nunique()} regions; tag share "
          f"{w.tagged.mean():.0%} (sac_scale / visibility / smoothness / "
          "mtb_scale)", flush=True)

    scored, imp, lams, knobs = [], [], [], []
    fold_cols, inner_roles = {}, []      # --save-folds
    het_rng = np.random.default_rng(SEED + 1)   # keeps the other arms' folds
    for split in splits:
        fold = outer_folds(w, split, rng)
        if args.save_folds:
            fold_cols[f"fold_{split}"] = pd.array(
                [None if v is None else str(v) for v in fold], dtype="string")
        tests = [TIME_TEST] if split == "time" else pd.unique(fold)
        for f in tests:
            te = np.nonzero(fold == f)[0]
            tr = np.nonzero(pd.notna(fold) & (fold != f))[0]
            if split == "loro_hiker":     # ... and none of its hikers
                seen = set(w.uploader.iloc[te])
                tr = tr[~w.uploader.iloc[tr].isin(seen).to_numpy()]
            fit_m, stop_m, cal_m = inner_split(w.outing_id.iloc[tr], rng)
            fit, stop, cal = tr[fit_m], tr[stop_m], tr[cal_m]
            if args.save_folds:
                for role, idx in (("fit", fit), ("stop", stop), ("cal", cal)):
                    inner_roles.append(pd.DataFrame({
                        "split": split, "fold": str(f), "role": role,
                        "outing_id": pd.unique(w.outing_id.iloc[idx])}))
            for name in ARMS:
                arm = Arm(name, blocks).fit(s, y, fit, stop, cal)
                if arm.kind == "lin":
                    lams.append(arm.lam)
                pred = arm.predict(s, te)
                sc = score_rows(pred, arm.r, y[te])
                scored.append(pd.DataFrame({
                    "split": split, "fold": str(f), "arm": name, "row": te,
                    "pred": pred, **sc}))
                if args.hetero and name in HET_ARMS:
                    st, rh = heteroscedastic(arm, s, y, cal, te, blocks,
                                             het_rng)
                    scored.append(pd.DataFrame({
                        "split": split, "fold": str(f), "arm": name + "+het",
                        "row": te, "pred": pred,
                        **score_rows(pred, rh, y[te], scale=st)}))
                rt, pt, r_me, beta = personal(arm, s, y, cal, te, blocks)
                if pt is not None:
                    knobs.append({"split": split, "fold": str(f),
                                  "arm": name, "beta": beta,
                                  "lam": getattr(arm, "lam", None),
                                  "kappa": getattr(arm, "kappa", None)})
                    scored.append(pd.DataFrame({
                        "split": split, "fold": str(f), "arm": name + "+me",
                        "row": rt, "pred": pt,
                        **score_rows(pt, r_me, y[rt])}))
                if split == "loro" and name == "gbm_tags":
                    pi = permutation_importance(
                        arm.m, arm.X(te)[arm.cols], y[te], n_repeats=3,
                        random_state=SEED, scoring="neg_mean_squared_error",
                        max_samples=min(len(te), 20000))
                    imp.append(pd.DataFrame({
                        "region": f, "feature": arm.cols,
                        "mse_increase": pi.importances_mean}))
            if split == "loro":    # reference: other outings, same region
                ofold = outer_folds(w.iloc[te], "outing5", rng)
                curve = tf.FORMS["smooth_asym"][0]
                for k in range(5):
                    a, b = te[ofold != k], te[ofold == k]
                    p = tf.fit_form("smooth_asym", s[a], y[a])
                    r = np.quantile(y[a] - curve(p, s[a]), QL)
                    pred = curve(p, s[b])
                    scored.append(pd.DataFrame({
                        "split": split, "fold": str(f),
                        "arm": "slope_curve_local", "row": b, "pred": pred,
                        **score_rows(pred, r, y[b])}))
            print(f"  {split} fold {f}: {time.time() - t0:.0f} s",
                  flush=True)

    if args.save_folds:
        pd.DataFrame({"segment_id": w.segment_id.to_numpy(), **fold_cols}
                     ).to_parquet(OUT / "folds_segments.parquet", index=False)
        pd.concat(inner_roles, ignore_index=True).to_parquet(
            OUT / "folds_inner.parquet", index=False)
    tag_effects(s, y, blocks, oh.columns, float(np.median(lams)))
    knobs = pd.DataFrame(knobs)
    knobs.to_csv(OUT / "knobs.csv", index=False)
    sc = pd.concat(scored, ignore_index=True)
    base = w[["region", "trace_id", "outing_id", "uploader", "length_m",
              "moving_s", "y",
              "tagged", "rest", "stretch", *EXTRA_SUBSETS]
             ].reset_index(names="row")
    sc = sc.merge(base, on="row")

    rows = []
    for (split, arm), d in sc.groupby(["split", "arm"], sort=False):
        subsets = (["rest"] if arm.endswith("+me")
                   else ["all", "tagged", "rest", *EXTRA_SUBSETS])
        for sub in subsets:
            dd = d if sub == "all" else d[d[sub]]
            rows.append({"split": split, "arm": arm, "subset": sub,
                         **summarize(dd)})
    met = pd.DataFrame(rows)
    ref = met.loc[met.arm == BASELINE, ["split", "subset", "crps_log"]]
    met = met.merge(ref.rename(columns={"crps_log": "ref"}),
                    on=["split", "subset"], how="left")
    met["crps_skill_vs_slope_pct"] = 100 * (1 - met.crps_log / met.ref)
    met = met.drop(columns="ref")
    met.to_csv(OUT / "metrics.csv", index=False)
    hike_times(sc).to_csv(OUT / "hike_times.csv", index=False)
    ci = skill_intervals(sc, splits)
    ci.to_csv(OUT / "skill_ci.csv", index=False)
    print(ci.round(2).to_string(index=False))
    for split in [s for s in splits if s in ("macro", "eastwest")]:
        z = sc[(sc.split == split) & ~sc.arm.str.endswith("+me")]
        bz = pd.DataFrame([{"held_out": f, "arm": arm, **summarize(d)}
                           for (f, arm), d in z.groupby(["fold", "arm"])])
        ref = bz[bz.arm == BASELINE].set_index("held_out").crps_log
        bz["crps_skill_vs_slope_pct"] = 100 * (1 - bz.crps_log
                                               / bz.held_out.map(ref))
        bz.to_csv(OUT / f"{split}_by_zone.csv", index=False)
    pd.concat([skill_intervals(sc, splits, subset=k).assign(subset=k)
               for k in EXTRA_SUBSETS], ignore_index=True
              ).to_csv(OUT / "skill_ci_subsets.csv", index=False)

    lo = sc[(sc.split == "loro") & ~sc.arm.str.endswith("+me")]
    by = pd.DataFrame([{"region": reg, "arm": arm, **summarize(d)}
                       for (reg, arm), d in lo.groupby(["region", "arm"])])
    if len(by):
        bref = by[by.arm == BASELINE].set_index("region").crps_log
        by["crps_skill_vs_slope_pct"] = 100 * (1 - by.crps_log
                                               / by.region.map(bref))
        by.to_csv(OUT / "loro_by_region.csv", index=False)

    edges = np.linspace(0, 1, 11)
    ref_split = "loro" if "loro" in splits else splits[0]
    pit = pd.DataFrame({arm: np.histogram(d.pit, edges)[0] / len(d)
                        for arm, d in sc[sc.split == ref_split]
                        .groupby("arm")},
                       index=[f"{a:.1f}-{b:.1f}" for a, b in
                              zip(edges[:-1], edges[1:])])
    pit.to_csv(OUT / "pit.csv")
    if imp:
        imp = pd.concat(imp)
        imp.to_csv(OUT / "importance.csv", index=False)

    summary = {
        "walking_segments": len(w), "outings": int(w.outing_id.nunique()),
        "regions": int(w.region.nunique()),
        "tagged_share": round(float(w.tagged.mean()), 3),
        "minutes": round((time.time() - t0) / 60, 1),
        "personal_beta_median": round(float(knobs.beta.median()), 3),
        "place_kappa_median": float(knobs.kappa.dropna().median()),
        "ridge_lambda_median": float(np.median(lams)),
        "metrics": met.round(4).to_dict("records"),
        "loro_macro": by.groupby("arm")[["crps_log", "rmse_log",
                                         "time_ape_median",
                                         "crps_skill_vs_slope_pct"]]
        .mean().round(4).to_dict("index") if len(by) else {},
        "remote_sensing_covariates": rs_cols,
        "skill_ci": ci.round(3).to_dict("records")}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    figure(met[~met.arm.str.endswith("+me")], by, splits)
    show = met[met.subset == "all"][["split", "arm", "rmse_log", "crps_log",
                                     "crps_kmh", "cov50", "cov90",
                                     "stretch_ape_median", "time_ape_median",
                                     "crps_skill_vs_slope_pct"]]
    print(show.round(4).to_string(index=False))
    rest = met[(met.subset == "rest") & (met.split != "block5")]
    print("\nafter each trace's first km (subset rest; +me = personal pace):")
    print(rest[["split", "arm", "rmse_log", "crps_log", "cov90",
                "stretch_ape_median", "time_ape_median",
                "crps_skill_vs_slope_pct"]]
          .round(4).to_string(index=False))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


HIKE_ARMS = ["tobler", "campbell", "slope_curve", "lin_tags", "lin_rs",
             "gbm_rs", "terrain_curve", "slope_curve+me", "lin_rs+me",
             "gbm_rs+me"]


def hike_times(sc):
    """Predicted vs actual moving time per hike (trace) in held-out regions,
    on the segments after each trace's first km (so the personal-pace rows
    are comparable): one row per trace x arm."""
    d = sc[(sc.split == "loro") & sc.rest & sc.arm.isin(HIKE_ARMS)]
    d = d.assign(t_pred=3.6 * d.length_m * np.exp(-d.pred) * d.time_factor)
    g = d.groupby(["arm", "region", "trace_id"]).agg(
        km=("length_m", "sum"), t_h=("moving_s", "sum"),
        t_pred_h=("t_pred", "sum")).reset_index()
    g["km"] /= 1000
    g["t_h"] /= 3600
    g["t_pred_h"] /= 3600
    g = g[g.km >= MIN_TRACE_KM]
    g["err_pct"] = 100 * (g.t_pred_h / g.t_h - 1)
    return g


def skill_intervals(sc, splits, B=2000, subset=None):
    """95% bootstrap intervals of each arm's CRPS skill vs the baseline,
    resampling outings (outing, block and time folds) or whole regions
    (leave one region out: the honest unit for a transfer claim), plus
    paired intervals for the remote-sensing arms minus the matching tags
    arm. subset: only the scored rows flagged in that column."""
    rng = np.random.default_rng(SEED)
    pairs = [("lin_rs", "lin_tags"), ("gbm_rs", "gbm_tags"),
             ("lin_both", "lin_tags"), ("gbm_both", "gbm_tags")]
    rows = []
    for split in splits:
        unit = ("region" if split in REGION_SPLITS
                else "uploader" if split == "hiker5" else "outing_id")
        d = sc[(sc.split == split) & ~sc.arm.str.endswith("+me")
               & (sc.arm != "slope_curve_local")]
        if subset:
            d = d[d[subset]]
        g = d.groupby([unit, "arm"]).crps_log.sum().unstack("arm")
        if BASELINE not in g:
            continue
        idx = rng.integers(0, len(g), (B, len(g)))
        base = g[BASELINE].to_numpy()[idx].sum(1)
        skill = {a: 100 * (1 - g[a].to_numpy()[idx].sum(1) / base)
                 for a in g.columns if a != BASELINE}
        for a, s in skill.items():
            lo, hi = np.percentile(s, [2.5, 97.5])
            rows.append({"split": split, "unit": unit, "units": len(g),
                         "arm": a, "skill_lo": lo, "skill_hi": hi})
        for a, b in pairs:
            if a in skill and b in skill:
                dlt = skill[a] - skill[b]
                lo, hi = np.percentile(dlt, [2.5, 97.5])
                rows.append({"split": split, "unit": unit, "units": len(g),
                             "arm": f"{a} - {b}", "skill_lo": lo,
                             "skill_hi": hi,
                             "share_draws_above_0": float((dlt > 0).mean())})
    return pd.DataFrame(rows)


def tag_effects(s, y, blocks, names, lam):
    """The additive tags model fitted on ALL walking segments (penalty =
    the median chosen in the folds): each tag value's effect on speed,
    relative to that tag being missing."""
    every = np.arange(len(y))
    arm = Arm("lin_tags", blocks).fit(s, y, every, every, every,
                                      lambdas=[lam])
    b = pd.Series(arm.b, index=names)
    n = blocks["tags_1h"].sum(0)
    rows = []
    for (feat, value), coef in b.items():
        rel = coef - b.get((feat, "missing"), 0.0)
        rows.append({"feature": feat, "value": value,
                     "segments": int(n[list(names).index((feat, value))]),
                     "speed_effect_pct": round(100 * (np.exp(rel) - 1), 1)})
    pd.DataFrame(rows).to_csv(OUT / "tag_effects.csv", index=False)
    print(f"tag effects written (ridge penalty {lam:g} per segment)")


def figure(met, by, splits):
    """Left: CRPS skill vs the slope-only curve, per split. Right: LORO
    skill per region (when LORO ran)."""
    BLUE, ORANGE, AQUA, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#9a9893"
    arms = [a for a in ARMS if a != BASELINE] + ["slope_curve_local"]
    arms = [a for a in arms if a in set(met.arm)]
    colors = {"tobler": GRAY, "gbm_tags": ORANGE, "gbm_slope": BLUE,
              "lin_tags": "#e87ba4", "slope_curve_local": AQUA}
    if not len(by):
        fig, a0 = plt.subplots(figsize=(6.5, 5.2))
        ax = [a0]
    else:
        fig, ax = plt.subplots(1, 2, figsize=(12, 5.2),
                               gridspec_kw={"width_ratios": [1, 1.4]})
    m = met[met.subset == "all"]
    for i, split in enumerate(splits):
        d = m[m.split == split].set_index("arm")
        for j, arm in enumerate(arms):
            if arm in d.index:
                ax[0].scatter(d.loc[arm, "crps_skill_vs_slope_pct"],
                              j + (i - (len(splits) - 1) / 2) * 0.2, s=36,
                              color=["#9ec5f0", "#4f97e3", "#1b4f8f",
                                     "#0d2a4f"][i],
                              label=split if j == 0 else None, zorder=3)
    ax[0].set_yticks(range(len(arms)), arms)
    ax[0].axvline(0, color="#52514e", lw=1)
    ax[0].set_xlabel("CRPS skill vs slope-only curve (%)")
    ax[0].set_title("All splits", fontsize=11)
    ax[0].legend(frameon=False, fontsize=9)
    if not len(by):
        ax[0].grid(axis="x", color="#e4e3df")
        ax[0].spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(OUT / "fig_harness.png", dpi=150)
        return
    regs = by[by.arm == "lin_tags"].sort_values(
        "crps_skill_vs_slope_pct").region.tolist()
    for arm in ["tobler", "gbm_slope", "lin_tags", "gbm_tags",
                "slope_curve_local"]:
        d = by[by.arm == arm].set_index("region").reindex(regs)
        ax[1].scatter(d.crps_skill_vs_slope_pct, range(len(regs)), s=30,
                      color=colors[arm], label=arm, zorder=3)
    ax[1].set_yticks(range(len(regs)), regs)
    ax[1].axvline(0, color="#52514e", lw=1)
    ax[1].set_xlabel("CRPS skill vs slope-only curve (%), region held out")
    ax[1].set_title("Leave one region out, per region", fontsize=11)
    ax[1].legend(frameon=False, fontsize=9, loc="upper center",
                 bbox_to_anchor=(0.5, -0.12), ncol=5)
    for a in ax:
        a.grid(axis="x", color="#e4e3df")
        a.spines[["top", "right"]].set_visible(False)
    lo = min(-30, float(by.crps_skill_vs_slope_pct.min()) - 2)
    ax[1].set_xlim(left=lo)
    fig.tight_layout()
    fig.savefig(OUT / "fig_harness.png", dpi=150)


if __name__ == "__main__":
    main()
