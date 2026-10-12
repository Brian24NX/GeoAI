#!/usr/bin/env python3
"""
A release-ready copy of the T1 dataset, WITHOUT personal identifiers.
NOT published: it stays on the cluster until the mentors decide on a
release (licensing: OSM-derived data falls under the ODbL; see the card).

What changes from data/t1_all/:
  - user names dropped;
  - trace, outing and segment ids replaced by salted hashes (the salt is a
    random secret kept outside the release, so nobody can re-create the
    keys by hashing public OSM trace ids);
  - time reduced to local month and hour (no exact timestamps);
  - coordinates rounded to 5 decimals (~1 m).
Kept: the walking analysis set (the rows every result uses), speeds,
slopes, OSM tags, mode, grouping keys, and the T2 covariates (terrain 5 m
and 1 m, land cover, AlphaEarth embeddings) joined on the new key.

Output: data/t1_release/ segments.parquet, covariates_*.parquet,
        DATA_CARD_RELEASE.md (draft)
Run (cluster): python t1_release.py
"""

import hashlib
import secrets
from pathlib import Path

import pandas as pd

SRC = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t1_release")
SALT = Path("cache/release_salt.txt")          # never published
KEEP = ["region", "piece", "seg_index", "length_m", "elapsed_s",
        "moving_s", "speed_kmh", "stopped_frac", "slope", "z0_m", "z1_m",
        "lat0", "lon0", "lat1", "lon1", "geometry_wkt", "way_class",
        "osm_way_id", "way_dir", "permission", "tag_surface",
        "tag_sac_scale", "tag_width", "tag_trail_visibility",
        "tag_smoothness", "tag_mtb_scale", "tag_incline", "tag_highway",
        "tag_name", "match_err_m", "n_points", "native_interval_s",
        "year", "date_suspect", "mode", "mode_conf",
        "foot_anchor", "trail_network", "block_10km"]


def keyer(salt):
    def key(x, n=16):
        return hashlib.sha256((salt + str(x)).encode()).hexdigest()[:n]
    return key


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not SALT.exists():
        SALT.write_text(secrets.token_hex(32))
    key = keyer(SALT.read_text().strip())
    s = pd.read_parquet(SRC)
    s = s[s.analysis_walk].reset_index(drop=True)
    r = s[KEEP].copy()
    r.insert(0, "seg_key", s.segment_id.map(key))
    r.insert(1, "trace_key", s.trace_id.map(lambda x: key(x, 12)))
    r.insert(2, "outing_key", s.outing_id.map(lambda x: key(x, 12)))
    lt = pd.to_datetime(s.local_time, errors="coerce")
    r["local_month"] = lt.dt.strftime("%Y-%m")
    r["local_hour"] = lt.dt.hour.astype("Int64")
    for c in ("lat0", "lon0", "lat1", "lon1"):
        r[c] = r[c].round(5)
    r["geometry_wkt"] = r.geometry_wkt.str.replace(
        r"(-?\d+\.\d{5})\d+", r"\1", regex=True)
    r.to_parquet(OUT / "segments.parquet", index=False)
    ids = pd.DataFrame({"segment_id": s.segment_id, "seg_key": r.seg_key})
    for kind in ("terrain5m", "terrain1m", "landcover", "aef2022"):
        files = sorted(Path("data/t2").glob(f"{kind}_*.parquet"))
        if not files:
            continue
        c = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        c = ids.merge(c, on="segment_id", how="inner").drop(
            columns="segment_id")
        c.to_parquet(OUT / f"covariates_{kind}.parquet", index=False)
    write_card(r)
    print(f"wrote {OUT}: {len(r):,} segments, "
          f"{r.trace_key.nunique():,} traces, {r.outing_key.nunique():,} "
          f"outings, {r.region.nunique()} regions")


def write_card(r):
    lines = [
        "# Hiking speeds on trails, 17 North American regions: release "
        "draft", "",
        "**DRAFT, NOT RELEASED.** Built by `t1_release.py` from the T1 "
        "dataset. Before any release, the mentors decide the license and "
        "the terms (see below).", "",
        f"- {len(r):,} walking traversals of 50 m trail segments, "
        f"{r.trace_key.nunique():,} GPS traces, {r.outing_key.nunique():,} "
        f"outings, {r.region.nunique()} regions (US and Canada).",
        "- One row = one traversal of one 50 m piece of trail by one walker; "
        "target `speed_kmh` (moving speed).",
        "- Covariates in separate files joined on `seg_key`: terrain from "
        "USGS 3DEP elevation (5 m and 1 m), NLCD 2021 canopy and land "
        "cover, AlphaEarth 2022 satellite embeddings.", "",
        "## Privacy steps", "",
        "- No user names. Trace, outing and segment ids are salted hashes "
        "(the salt is kept private).",
        "- Time only as local month and hour; coordinates rounded to ~1 m.",
        "- The underlying GPS traces were uploaded to OpenStreetMap as "
        "public or identifiable, so a determined person could still match "
        "a row to its public OSM trace. State this.", "",
        "## Licensing (to decide)", "",
        "- Derived from OpenStreetMap data and GPS traces: OpenStreetMap "
        "contributors, ODbL 1.0. A database derived from OSM data is "
        "normally shared under the ODbL with attribution "
        "(\"Contains information from OpenStreetMap\").",
        "- USGS 3DEP and NLCD: public domain. AlphaEarth embeddings: CC-BY "
        "4.0, attribution \"The AlphaEarth Foundations Satellite Embedding "
        "dataset is produced by Google and Google DeepMind.\"",
        "- **TODO (mentors):** license choice, the lab's data policy, "
        "whether hashed keys and month/hour granularity are enough.", "",
        "## Columns", "",
        "As in `data/t1_all/DATA_CARD.md`, except: `seg_key`, `trace_key`, "
        "`outing_key` (hashed ids), `local_month`, `local_hour`; dropped "
        "`uploader`, `trace_id`, `outing_id`, `segment_id`, `t_start`, "
        "`local_time`, `day_of_year`, `doy_sin`, `doy_cos` (exact day).", ""]
    (OUT / "DATA_CARD_RELEASE.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
