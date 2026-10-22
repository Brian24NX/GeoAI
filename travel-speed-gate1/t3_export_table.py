#!/usr/bin/env python3
"""
Export the modeling table for models built outside the harness (T3 with
learned constants, docs/T3_learned_tobler_design.md): the harness's walking
segments with their covariates and the harness's own folds, de-identified.

Run on the cluster after the two --save-folds runs
(cluster/refresh_harness.sh folds15m and foldshikers):
    $PY t3_export_table.py

Writes cache/exercise/ (not in git):
  t3_table.parquet   one row per scored walking segment (289,679), in the
                     harness's order: region, outing (integer id), slope,
                     hiker (an integer per uploader; an anonymous trace is
                     its own), y = ln speed (km/h), length_m, moving_s,
                     native_interval_s, year, the OSM tag columns, the
                     terrain (5 m + 1 m) and lidar vegetation covariates, and
                     the outer fold of each split (fold_outing5, fold_block5,
                     fold_loro, fold_hiker5, fold_loro_hiker)
  t3_inner.parquet   split, fold, outing, role: the outings that fit
                     ("fit"), early-stop ("stop") and calibrate ("cal") each
                     fold's models
  t3_columns.json    which covariate column came from which source
No user names, trace or segment ids, coordinates or timestamps.
"""
import json
from pathlib import Path

import pandas as pd

import t3_harness as h

T2 = Path("data/t2")
OUT = Path("cache/exercise")
RUNS = {"results/t3_harness_terrain15m_folds": ["outing5", "block5", "loro"],
        "results/t3_harness_hikers_folds": ["hiker5", "loro_hiker"]}
SOURCES = ["terrain5m", "terrain1m", "lidarveg"]
TAGS = ["tag_surface", "tag_sac_scale", "tag_width", "tag_trail_visibility",
        "tag_smoothness", "tag_mtb_scale", "tag_highway", "permission"]


def covariates():
    """The harness's merge: stack every file, one row per (region,
    segment), first non-missing value; numeric columns outside RS_SKIP.
    Region from the file name (<kind>_<region>.parquet), because a trace
    built in two regions repeats segment ids (decision #118)."""
    groups, tables = {}, []
    for src in SOURCES:
        files = sorted(T2.glob(f"{src}_*.parquet"))
        t = pd.concat([pd.read_parquet(f).assign(
            region=f.stem.rsplit("_", 1)[-1]) for f in files],
            ignore_index=True)
        cols = [c for c in t.columns if c not in h.RS_SKIP
                and c != "region" and not c.startswith("dem1m_cover")
                and pd.api.types.is_numeric_dtype(t[c])]
        groups.update({c: src for c in cols if c not in groups})
        tables.append(t[["region", "segment_id"] + cols])
    cov = pd.concat(tables, ignore_index=True)
    cov = cov.groupby(["region", "segment_id"], sort=False).first(
        ).reset_index()
    return cov, groups


def main():
    w = h.load()
    n = len(w)
    cov, groups = covariates()
    rs = list(groups)
    w = w.merge(cov[["region", "segment_id"] + rs],
                on=["region", "segment_id"], how="left")
    assert len(w) == n
    folds = []
    for run, splits in RUNS.items():
        # by position, not by id: the harness wrote w's rows in order, and
        # a few segment ids repeat (segments inside two regions' boxes, #114)
        f = pd.read_parquet(Path(run) / "folds_segments.parquet")
        assert (f.segment_id.to_numpy() == w.segment_id.to_numpy()).all()
        for c in (f"fold_{s}" for s in splits):
            w[c] = f[c].to_numpy()
            folds.append(c)
    assert w[folds].notna().all().all()
    codes, uniques = pd.factorize(w.outing_id)
    w["outing"] = codes.astype("int32")
    w["hiker"] = pd.factorize(w.uploader)[0].astype("int32")   # no names
    inner = pd.concat([pd.read_parquet(Path(run) / "folds_inner.parquet")
                       for run in RUNS], ignore_index=True)
    inner["outing"] = pd.Index(uniques).get_indexer(inner.outing_id)
    assert (inner.outing >= 0).all()
    inner["outing"] = inner.outing.astype("int32")
    keep = ["region", "outing", "hiker", "slope", "y", "length_m", "moving_s",
            "native_interval_s", "year", *TAGS, *rs, *folds]
    OUT.mkdir(parents=True, exist_ok=True)
    w[keep].to_parquet(OUT / "t3_table.parquet", index=False)
    inner[["split", "fold", "outing", "role"]].to_parquet(
        OUT / "t3_inner.parquet", index=False)
    (OUT / "t3_columns.json").write_text(json.dumps(
        {"tags": TAGS, "folds": folds,
         "covariates": {src: [c for c in rs if groups[c] == src]
                        for src in SOURCES}}, indent=1))
    print(f"{n:,} segments, {w.outing.nunique():,} outings; "
          f"{len(rs)} covariates "
          f"({', '.join(f'{s} {sum(g == s for g in groups.values())}' for s in SOURCES)}); "
          f"{len(inner):,} inner-split rows")


if __name__ == "__main__":
    main()
