#!/usr/bin/env python3
"""
Index the lab's crawl of OSM GPS traces (runs on the cluster).

The lab folder /engrfs/project/jacobsn/OSM_data holds the ORIGINAL files of
public + identifiable OSM traces uploaded 2016-2022, parsed into Parquet:
one row per trace, with every point, its timestamp and elevation. (The OSM
API only gives "public" traces as untimed points, so this is extra data.)
The files aren't sorted by place, so finding the traces in a region means
reading every file. This script does that once, keeping only the small
columns (bbox, times, stats), so later we can count and pick traces for ANY
region in seconds.

Output (in OUT):
  index.parquet       one row per trace: trace_id, file, row, stats, bbox
  uploaders.parquet   trace_id -> OSM user name (from the crawl's URL lists)

Run:  venv/bin/python build_lab_index.py /engrfs/project/jacobsn/zhou.n/osm_lab_index
"""

import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path("/engrfs/project/jacobsn/OSM_data")
SCHEMA = pa.schema([
    ("trace_id", pa.string()), ("point_count", pa.int64()),
    ("start_time", pa.timestamp("us", tz="UTC")),
    ("end_time", pa.timestamp("us", tz="UTC")),
    ("duration_seconds", pa.float64()), ("total_distance_km", pa.float64()),
    ("avg_speed_kmh", pa.float64()), ("max_speed_kmh", pa.float64()),
    ("min_elevation", pa.float64()), ("max_elevation", pa.float64()),
    ("elevation_gain", pa.float64()),
    ("bbox_minx", pa.float64()), ("bbox_miny", pa.float64()),
    ("bbox_maxx", pa.float64()), ("bbox_maxy", pa.float64()),
    ("segment_count", pa.int64())])
URL = re.compile(r"/user/(.+)/traces/(\d+)\s*$")


def index(out):
    files = sorted(SRC.glob("20*/batch_*.parquet"))
    parts, skipped, t0 = [], [], time.time()
    for i, f in enumerate(files, 1):
        try:
            t = pq.read_table(f, columns=SCHEMA.names)
            t = pa.table([t[n].cast(SCHEMA.field(n).type) for n in
                          SCHEMA.names], schema=SCHEMA)
        except Exception as err:
            skipped.append(f"{f}: {type(err).__name__}: {err}")
            continue
        n = t.num_rows
        t = t.append_column("file", pa.array([f"{f.parent.name}/{f.name}"]
                                             * n))
        parts.append(t.append_column("row", pa.array(range(n), pa.int32())))
        if i % 250 == 0 or i == len(files):
            print(f"{i}/{len(files)} files, {sum(p.num_rows for p in parts):,}"
                  f" traces, {time.time() - t0:.0f} s", flush=True)
    pq.write_table(pa.concat_tables(parts), out / "index.parquet",
                   compression="zstd")
    print(f"skipped {len(skipped)} files", *skipped[:20], sep="\n", flush=True)


def uploaders(out):
    ids, users, lists = [], [], []
    for f in sorted(SRC.glob("traces_*.txt")):
        for line in f.open(encoding="utf-8", errors="replace"):
            m = URL.search(line)
            if m:
                users.append(unquote(m.group(1)))
                ids.append(m.group(2))
                lists.append(f.stem)
    t = pa.table({"trace_id": ids, "user": users, "list": lists})
    pq.write_table(t, out / "uploaders.parquet", compression="zstd")
    print(f"uploaders: {t.num_rows:,} URLs", flush=True)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    uploaders(out)
    index(out)
    print("INDEX DONE", flush=True)
