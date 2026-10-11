#!/usr/bin/env python3
"""
Download many T1 regions, one after another, unattended.

  --what osm   OSM traces + full GPX files (t1_download.py), ONE region at a
               time: the OSM API is run by volunteers, so never in parallel
               with another OSM download (waits until none is running).
  --what dem   5 m elevation grids (t1_prefetch_dem.py). A different server
               (USGS), so this queue can run alongside the OSM one.
  --what build when a region's OSM and elevation downloads are both done:
               build it (t1_build_dataset), re-run the travel modes over ALL
               built regions (anchors are pooled), refit its curve under the
               4 stop rules (t1_variants) and finish its data card
               (t1_finalize). Waits for the downloads; skips regions the OSM
               queue skipped.
  --probe      before an OSM download, count the region's pages cheaply
               (pages are cached, so nothing is wasted if we go ahead) and
               skip the region if it is bigger than --max-pages in total:
               boxes next to big cities are mostly car-logger pages.

Every step caches, so re-running skips whatever is already done.
Logs: logs/t1_download_<key>.log, logs/t1_dem_<key>.log, logs/t1_queue.log

Run:  python t1_queue.py --what osm --probe frontrange adk catskills ...
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import gate1_audit as g
import regions

PY = sys.executable
DEEP_PAGE = 512          # probe pages this deep that time out = a capped tile
LOG = Path("logs")


def say(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    with open(LOG / "t1_queue.log", "a") as f:
        f.write(line + "\n")


def osm_download_running():
    """PIDs of Python processes running t1_download.py (not shells that
    merely mention it)."""
    out = subprocess.run(["pgrep", "-f", r"^[^ ]*[Pp]ython[^ ]* -u "
                          r"t1_download\.py"], capture_output=True,
                         text=True).stdout.split()
    return out


def page_points(text):
    return text.count("<trkpt") if text else 0


def probe(key):
    """Upper bound on the region's API pages: per tile, fetch pages 0, 1, 2,
    4, 8, ... until one is short (each page is cached for the real run)."""
    region, total = regions.region_name(key), 0
    for box in regions.tiles(key):
        page, last, errors = 0, 0, 0
        while True:
            text, src = g.get_page("cache", region, box, page, offline=False)
            if text is None:                       # network error: retry
                errors += 1
                if page >= DEEP_PAGE:              # the API's depth limit:
                    last = page                    # the tile gets capped there
                    break
                if errors > 5:
                    return float("inf")            # can't tell: treat as big
                time.sleep(30)
                continue
            if page_points(text) < g.POINTS_PER_PAGE:
                last = page
                break
            page = 1 if page == 0 else 2 * page
        total += last + 1
        say(f"  probe {box[0]}: <= {last + 1} pages")
    return total


def _has(path, text):
    return path.exists() and text in path.read_text(errors="replace")


def _last(path, prefix):
    """The last line of a log that starts with prefix ('' if none)."""
    if not path.exists():
        return ""
    lines = [x.strip() for x in path.read_text(errors="replace").splitlines()
             if x.strip().startswith(prefix)]
    return lines[-1] if lines else ""


def download_complete(key):
    """The latest OSM pass ended DONE and no tile stopped on an error."""
    import t1_download
    return (_last(LOG / f"t1_download_{key}.log", "T1 DOWNLOAD") ==
            "T1 DOWNLOAD DONE" and not t1_download.incomplete_tiles(key))


def run(args, log):
    with open(log, "a") as f:
        return subprocess.call([PY, "-u"] + args, stdout=f,
                               stderr=subprocess.STDOUT)


def _dem_complete(key):
    import t1_prefetch_dem as tp
    region = regions.region_name(key)
    return all((Path("cache/layers") / f"{stem}_dem5m.tif").exists()
               for box in regions.tiles(key)
               for stem, _ in tp.piece_names(region, box))


def _job_id(text):
    """The job id in sbatch --parsable output. The cluster also prints
    Kerberos (auks) log lines there, so pick the line that is just a number
    (optionally ';cluster')."""
    for line in (text or "").splitlines():
        m = re.fullmatch(r"\s*(\d+)(?:;\S+)?\s*", line)
        if m:
            return m.group(1)
    return ""


def submit_build(key):
    """Cluster: elevation job (1 CPU), then the build job (8 CPUs: the
    academic-job QoS allows at most 8 per job and 4 running jobs per user).
    Build jobs share one name and run one at a time (--dependency=
    singleton): the travel-mode step rewrites every built region. A marker
    file stops a restarted queue from submitting the same region twice."""
    marker = LOG / f"build_submitted_{key}"
    if marker.exists():
        say(f"SUBMIT {key}: already submitted ({marker.read_text().strip()})")
        return
    common = ["-A", "engr-class-any", "-p", "linuxlab-project"]
    dem = subprocess.run(
        ["sbatch", "--parsable", *common, "-J", f"t1_dem_{key}", "-c", "1",
         "--mem", "8G", "-t", "12:00:00", "-o", f"logs/slurm_dem_{key}_%j.log",
         "cluster/t1_region_job.sh", "dem", key],
        capture_output=True, text=True)
    dep = _job_id(dem.stdout)
    bld = subprocess.run(
        ["sbatch", "--parsable", *common, "-J", "t1_build", "-c", "8",
         "--mem", "32G", "-t", "06:00:00",
         f"--dependency=afterok:{dep},singleton" if dep else
         "--dependency=singleton",
         "-o", f"logs/slurm_build_{key}_%j.log",
         "cluster/t1_region_job.sh", "build", key],
        capture_output=True, text=True)
    say(f"SUBMIT {key}: elevation job {dep or dem.stderr.strip()[-80:]}, "
        f"build job {_job_id(bld.stdout) or bld.stderr.strip()[-120:]}")
    if _job_id(bld.stdout):
        marker.write_text(f"dem {dep}, build {_job_id(bld.stdout)}")


def submit_labonly(key):
    """Cluster, fast path: ways + elevation (1 CPU, one prep job at a time:
    Overpass is shared), then the build from the lab crawl's traces alone.
    A later full download rebuilds the region with the API traces too."""
    marker = LOG / f"labonly_submitted_{key}"
    if marker.exists():
        say(f"LABONLY {key}: already submitted ({marker.read_text().strip()})")
        return
    common = ["-A", "engr-class-any", "-p", "linuxlab-project"]
    prep = subprocess.run(
        ["sbatch", "--parsable", *common, "-J", "t1_prep", "-c", "1",
         "--mem", "8G", "-t", "12:00:00", "--dependency=singleton",
         "-o", f"logs/slurm_prep_{key}_%j.log",
         "cluster/t1_region_job.sh", "prep", key],
        capture_output=True, text=True)
    dep = _job_id(prep.stdout)
    bld = subprocess.run(
        ["sbatch", "--parsable", *common, "-J", "t1_build", "-c", "8",
         "--mem", "32G", "-t", "06:00:00",
         f"--dependency=afterok:{dep},singleton" if dep else
         "--dependency=singleton",
         "-o", f"logs/slurm_build_{key}_%j.log",
         "cluster/t1_region_job.sh", "build", key],
        capture_output=True, text=True)
    say(f"LABONLY {key}: prep job {dep or prep.stderr.strip()[-80:]}, "
        f"build job {_job_id(bld.stdout) or bld.stderr.strip()[-120:]}")
    if _job_id(bld.stdout):
        marker.write_text(f"prep {dep}, build {_job_id(bld.stdout)}")


def build(key, fetch_dem=False):
    """Build one region once its downloads are done (see --what build).
    fetch_dem: get the elevation here, once the OSM download is done (for
    regions no DEM queue covers, so a probe-skipped region costs nothing)."""
    dem = LOG / f"t1_dem_{key}.log"
    while not download_complete(key):
        if _has(LOG / "t1_queue.log", f"OSM {key}: SKIPPED"):
            say(f"BUILD {key}: skipped (OSM download was skipped)")
            return
        time.sleep(120)
    if not fetch_dem:                  # a DEM queue covers it: wait for it
        while not _last(dem, "DEM PREFETCH DONE") and \
                not _has(LOG / "t1_queue.log", f"DEM {key}: exit"):
            time.sleep(120)
    for _ in range(3):                 # missing grids (outage): fetch here
        if _last(dem, "DEM PREFETCH DONE") and not \
                _has(dem, "Traceback") or _dem_complete(key):
            break
        say(f"DEM {key}: (re)start from the build queue")
        run(["t1_prefetch_dem.py", "--region", key], dem)
        if not _dem_complete(key):
            time.sleep(600)
    if not _dem_complete(key):
        say(f"BUILD {key}: elevation grids still missing, skipped for now")
        return
    log = LOG / f"t1_build_{key}.log"
    say(f"BUILD {key}: start")
    rc = run(["t1_build_dataset.py", "--region", key], log)
    if rc:
        say(f"BUILD {key}: build FAILED (exit {rc}), see {log}")
        return
    built = [str(regions.data_dir(k)) for k in regions.CANDIDATES
             if (regions.data_dir(k) / "segments_L50.parquet").exists()]
    rc = run(["t1_modes.py"] + built, log)
    rc = rc or run(["t1_variants.py", "--region", key], log)
    rc = rc or run(["t1_finalize.py", "--region", key], log)
    say(f"BUILD {key}: {'done' if not rc else f'FAILED (exit {rc})'}"
        f" ({len(built)} regions built so far)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", choices=["osm", "dem", "build"], required=True)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--fetch-dem", action="store_true",
                    help="build queue: download elevation itself")
    ap.add_argument("--labonly", action="store_true",
                    help="cluster: submit fast lab-only builds and exit")
    ap.add_argument("--submit-builds", action="store_true",
                    help="on the cluster: after each region's OSM download "
                         "is complete, sbatch its elevation + build jobs")
    ap.add_argument("--max-pages", type=int, default=6000)
    ap.add_argument("keys", nargs="+", choices=sorted(regions.CANDIDATES))
    args = ap.parse_args()
    LOG.mkdir(exist_ok=True)
    if args.labonly:
        for key in args.keys:
            submit_labonly(key)
        return
    for key in args.keys:
        if args.what == "build":
            build(key, args.fetch_dem)
            continue
        if args.what == "dem":
            say(f"DEM {key}: start")
            with open(LOG / f"t1_dem_{key}.log", "a") as f:
                rc = subprocess.call([PY, "-u", "t1_prefetch_dem.py",
                                      "--region", key], stdout=f,
                                     stderr=subprocess.STDOUT)
            say(f"DEM {key}: exit {rc}")
            continue
        while osm_download_running():
            time.sleep(60)                         # one OSM stream at a time
        if download_complete(key):
            say(f"OSM {key}: already complete")
            if args.submit_builds and not (regions.data_dir(key)
                                           / "modes.csv").exists():
                submit_build(key)
            continue
        if args.probe:
            pages = probe(key)
            say(f"OSM {key}: probe says <= {pages:,} pages")
            if pages > args.max_pages:
                say(f"OSM {key}: SKIPPED (more than {args.max_pages:,} "
                    f"pages; use the lab traces or a smaller box)")
                continue
        say(f"OSM {key}: start")
        with open(LOG / f"t1_download_{key}.log", "a") as f:
            rc = subprocess.call([PY, "-u", "t1_download.py", "--region",
                                  key], stdout=f, stderr=subprocess.STDOUT)
        say(f"OSM {key}: exit {rc}"
            f"{'' if download_complete(key) else ' (INCOMPLETE)'}")
        if args.submit_builds and download_complete(key):
            submit_build(key)
    if args.what == "build":            # anchors moved: refresh all cards
        for k in regions.CANDIDATES:
            if (regions.data_dir(k) / "modes.csv").exists():
                run(["t1_finalize.py", "--region", k],
                    LOG / f"t1_build_{k}.log")
    say(f"QUEUE {args.what} DONE: {' '.join(args.keys)}")


if __name__ == "__main__":
    main()
