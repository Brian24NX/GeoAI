#!/usr/bin/env python3
"""
The OSM trail network (Overpass) for every tile of a region, without the GPS
pages. For the fast lab-only builds (11 Oct 2026): the builder needs the
ways to map-match, but not the OSM API trackpoints. Cached exactly where
t1_download.py would put them, so a later full download reuses them.

Run:  python t1_ways.py --region bayarea
"""

import argparse

import gate1_audit as g
import regions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True,
                    choices=sorted(regions.CANDIDATES))
    key = ap.parse_args().region
    region = regions.region_name(key)
    for box in regions.tiles(key):
        ways = g.get_ways("cache", region, box)
        print(f"{box[0]}: {len(ways) if ways else 0} ways", flush=True)
        if ways is None:
            raise SystemExit(f"no ways for {box[0]}")
    print("WAYS DONE")


if __name__ == "__main__":
    main()
