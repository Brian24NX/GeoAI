#!/usr/bin/env python3
"""
Track A of the imagery arm (week 12, pulled forward; decision #124 and
docs/T3_naip_imagery_design.md): download Clay v1.5's precomputed NAIP
embeddings for the quarter quads under our walking segments.

Input:  results/t3_naip/clay_manifest.csv, one row per (region, tile):
        segments, state, year, res, key, bytes. Built 5 Nov from the trail
        tiles on ENGR and a listing of the Clay bucket.
Output: cache/naip_clay/<key>, one parquet per quarter quad: `geometry` and
        `embeddings` (1,024 numbers per 256-pixel chip; CC-BY 4.0, Clay).
Source: https://data.source.coop/clay/<key>

Run on ENGR (cluster/t3_naip_clay_job.sh). Brian approved the download on
5 Nov: 754 files, 6.05 GB. Complete files are skipped, so a re-run resumes.
    python t3_naip_clay_download.py [--limit N]
"""
import argparse
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

BASE = "https://data.source.coop/clay/"
OUT = Path("cache/naip_clay")
UA = {"User-Agent": "travel-speed-research-script"}
WORKERS = 4                     # polite to Source Cooperative


def fetch(key, size, tries=5):
    dest = OUT / key
    if dest.exists() and dest.stat().st_size == size:
        return "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    for k in range(tries):
        try:
            req = urllib.request.Request(BASE + key, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            if tmp.stat().st_size != size:
                raise IOError(f"got {tmp.stat().st_size} bytes, expected {size}")
            tmp.rename(dest)
            return "ok"
        except Exception as e:            # network hiccup: wait and retry
            print(f"  retry {k + 1} {key}: {e}", flush=True)
            time.sleep(5 * (k + 1))
    return "failed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only the first N files (smoke test)")
    a = ap.parse_args()
    m = pd.read_csv("results/t3_naip/clay_manifest.csv").drop_duplicates("key")
    if a.limit:
        m = m.head(a.limit)
    print(f"{len(m)} files, {m.bytes.sum() / 1e9:.2f} GB -> {OUT}", flush=True)
    counts = {"ok": 0, "skip": 0, "failed": 0}
    with ThreadPoolExecutor(WORKERS) as pool:
        jobs = pool.map(lambda r: fetch(r.key, int(r.bytes)), m.itertuples())
        for i, status in enumerate(jobs, 1):
            counts[status] += 1
            if i % 50 == 0 or i == len(m):
                print(f"{i}/{len(m)} {counts}", flush=True)
    sys.exit(1 if counts["failed"] else 0)


if __name__ == "__main__":
    main()
