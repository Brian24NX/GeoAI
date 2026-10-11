#!/usr/bin/env python3
"""
Pull the full traces for some regions out of the lab crawl (runs on the
cluster, as a Slurm job: it reads a lot of data).

index.parquet (build_lab_index.py) says which file and row each trace is in
and its bounding box. For each region box this takes every trace whose bbox
overlaps the box, is < MAX_SPAN_DEG across (that drops long road trips) and
averages <= MAX_AVG_KMH (that drops most car trips). It reads each source
file once and writes one Parquet per region: one row per
trace with all its points, timestamps, elevations and segment numbers.
The T1 build clips the points to the region and decides what's a hike.

Run:  venv/bin/python extract_lab_traces.py OUT_DIR key:w,s,e,n [key:...]
"""

import sys
import time
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path("/engrfs/project/jacobsn/OSM_data")
IDX = Path("/engrfs/project/jacobsn/zhou.n/osm_lab_index/index.parquet")
MAX_SPAN_DEG = 1.0
MAX_AVG_KMH = 30.0
UTC_US = pa.timestamp("us", tz="UTC")
SCHEMA = pa.schema([
    ("trace_id", pa.string()), ("start_time", UTC_US),
    ("point_count", pa.int64()),
    ("point_coordinates", pa.list_(pa.list_(pa.float64()))),
    ("point_timestamps", pa.list_(UTC_US)),
    ("point_elevations", pa.list_(pa.float64())),
    ("point_segment_indices", pa.list_(pa.int64()))])


def main(out, specs):
    regions = {}
    for spec in specs:
        key, box = spec.split(":")
        regions[key] = tuple(float(v) for v in box.split(","))
    ix = pq.read_table(IDX, columns=[
        "trace_id", "file", "row", "bbox_minx", "bbox_miny", "bbox_maxx",
        "bbox_maxy", "avg_speed_kmh"]).to_pandas()
    small = ((ix.bbox_maxx - ix.bbox_minx < MAX_SPAN_DEG)
             & (ix.bbox_maxy - ix.bbox_miny < MAX_SPAN_DEG)
             & ~(ix.avg_speed_kmh > MAX_AVG_KMH))
    want = defaultdict(lambda: defaultdict(list))     # file -> key -> rows
    for key, (w, s, e, n) in regions.items():
        hit = small & (ix.bbox_maxx >= w) & (ix.bbox_minx <= e) \
            & (ix.bbox_maxy >= s) & (ix.bbox_miny <= n)
        for f, r in zip(ix.file[hit], ix.row[hit]):
            want[f][key].append(int(r))
        print(f"{key}: {int(hit.sum()):,} traces", flush=True)
    print(f"reading {len(want):,} files", flush=True)

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    parts, bad, t0 = defaultdict(list), [], time.time()
    for i, (f, by_key) in enumerate(sorted(want.items()), 1):
        try:
            t = pq.read_table(SRC / f, columns=SCHEMA.names)
            t = pa.table([t[c].cast(SCHEMA.field(c).type)
                          for c in SCHEMA.names], schema=SCHEMA)
        except Exception as err:                 # keep going, report at end
            bad.append(f"{f}: {type(err).__name__}: {err}")
            continue
        for key, rows in by_key.items():
            parts[key].append(t.take(rows))
        if i % 100 == 0 or i == len(want):
            print(f"{i:,}/{len(want):,} files, {time.time() - t0:.0f} s",
                  flush=True)
    for key in regions:
        tab = pa.concat_tables(parts[key]) if parts[key] else SCHEMA.empty_table()
        pq.write_table(tab, out / f"{key}.parquet", compression="zstd")
        print(f"{key}: {tab.num_rows:,} traces written", flush=True)
    print(f"unreadable files: {len(bad)}", *bad[:20], sep="\n")
    print("EXTRACT DONE", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
