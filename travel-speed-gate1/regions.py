#!/usr/bin/env python3
"""
The candidate regions for T1 (9 Oct 2026: "as many regions as possible
across the US / North America", Danni).

Each region is one box (west, south, east, north) around a hiking area with
real relief (plan sec. 7). The boxes avoid big cities where they can: car
loggers there swamp the OSM API pages (Gate 1, Boulder). Which candidates
become T1 regions is decided by scout_regions.py (trace counts) and by the
1 m LiDAR coverage check (region_layers.py), not by this list.

  key: short name used in file names (data/t1_<key>/, tiles <key>_r0_c0)
  tz:  local time zone (for time of day / day of year)
  utm: NAD83 / UTM zone EPSG code (computed from the box center)
"""

import math
from pathlib import Path

# key: (label, (west, south, east, north), time zone, vegetation / notes)
CANDIDATES = {
    # --- East: dense forest, rocky trails
    "wm": ("White Mountains, NH", (-71.95, 43.80, -70.95, 44.50),
           "America/New_York", "northern hardwood + spruce-fir; rocky"),
    "adk": ("Adirondack High Peaks, NY", (-74.25, 43.95, -73.70, 44.35),
            "America/New_York", "northern hardwood + spruce-fir; rocky"),
    "catskills": ("Catskills, NY", (-74.60, 41.90, -74.00, 42.30),
                  "America/New_York", "hardwood forest"),
    "greenmtn": ("Green Mountains, VT", (-73.00, 44.15, -72.60, 44.60),
                 "America/New_York", "hardwood + spruce-fir"),
    "acadia": ("Acadia, ME", (-68.45, 44.22, -68.15, 44.45),
               "America/New_York", "coastal spruce, granite"),
    "shenandoah": ("Shenandoah, VA", (-78.70, 38.20, -78.15, 38.95),
                   "America/New_York", "oak-hickory forest"),
    "smokies": ("Great Smoky Mountains, TN/NC", (-84.00, 35.45, -83.05,
                                                 35.80),
                "America/New_York", "dense deciduous + spruce-fir"),
    "pisgah": ("Asheville / Pisgah, NC", (-82.95, 35.25, -82.40, 35.75),
               "America/New_York", "deciduous forest; MTB trails"),
    # --- Rocky Mountains / Intermountain West
    "frontrange": ("Colorado Front Range (Boulder-Golden)",
                   (-105.75, 39.55, -105.15, 40.15), "America/Denver",
                   "ponderosa + grassland; mixed-use trails"),
    "cosprings": ("Colorado Springs / Pikes Peak, CO",
                  (-105.10, 38.70, -104.80, 38.95), "America/Denver",
                  "ponderosa, scrub; mixed-use"),
    "wasatch": ("Wasatch Front (Salt Lake City), UT",
                (-111.85, 40.45, -111.55, 40.90), "America/Denver",
                "scrub oak + conifer; semi-arid"),
    "tetons": ("Grand Teton, WY", (-110.95, 43.60, -110.60, 43.95),
               "America/Denver", "conifer + alpine"),
    "glacier": ("Glacier NP, MT", (-114.10, 48.50, -113.50, 48.95),
                "America/Denver", "conifer + alpine"),
    "sedona": ("Sedona / Flagstaff, AZ", (-111.90, 34.75, -111.55, 35.40),
               "America/Phoenix", "arid red rock + ponderosa"),
    "boise": ("Boise Foothills, ID", (-116.30, 43.55, -116.00, 43.75),
              "America/Boise", "sagebrush steppe; mixed-use"),
    # --- Pacific
    "cascades": ("Cascades I-90 + Alpine Lakes, WA",
                 (-122.10, 47.20, -120.60, 47.90), "America/Los_Angeles",
                 "temperate rainforest -> dry pine east of the crest"),
    "gorge": ("Columbia River Gorge, OR/WA", (-122.30, 45.50, -121.40,
                                              45.75),
              "America/Los_Angeles", "Douglas-fir forest; steep"),
    "olympic": ("Olympic NP (north), WA", (-123.90, 47.75, -123.10, 48.10),
                "America/Los_Angeles", "temperate rainforest + alpine"),
    "bayarea": ("Bay Area hills (Marin, East Bay, Peninsula), CA",
                (-122.65, 37.30, -121.95, 38.00), "America/Los_Angeles",
                "grassland, chaparral, redwood; mixed-use"),
    "sangabriel": ("San Gabriel Mountains (LA), CA",
                   (-118.30, 34.15, -117.60, 34.40), "America/Los_Angeles",
                   "chaparral; steep, arid"),
    "yosemite": ("Yosemite Valley + High Sierra, CA",
                 (-119.80, 37.65, -119.30, 37.95), "America/Los_Angeles",
                 "conifer + granite"),
    "tahoe": ("Lake Tahoe, CA/NV", (-120.25, 38.85, -119.85, 39.30),
              "America/Los_Angeles", "conifer + granite"),
    # --- Canada (no USGS 3DEP; BC has its own open lidar)
    "northshore": ("North Shore Mountains (Vancouver), BC",
                   (-123.30, 49.30, -122.90, 49.48), "America/Vancouver",
                   "temperate rainforest; steep"),
}


# tiles left out of a region: low relief, few trails, and thousands of OSM
# pages of car-logger data (plan sec. 7: "real relief")
EXCLUDE_TILES = {
    "cascades_r2_c0": "lowland suburbs east of Redmond: >750 pages of car "
                      "loggers, little relief (10 Oct 2026)",
    # 11 Oct 2026: no hike-like traces in the lab crawl, highway traffic
    "shenandoah_r0_c2": "Piedmont east of the park, US-29: >750 pages of "
                        "car loggers, 0 hike-like lab traces",
    "shenandoah_r1_c0": "Shenandoah Valley floor: 0 hike-like lab traces",
    "shenandoah_r2_c0": "valley west of the park: 0 hike-like lab traces",
    "pisgah_r1_c0": "Asheville west: 0 hike- or ride-like lab traces",
    "pisgah_r1_c1": "Asheville city: 0 hike- or ride-like lab traces",
}


def utm_epsg(key):
    """NAD83 / UTM north EPSG code for the zone at the box center."""
    w, s, e, n = CANDIDATES[key][1]
    return 26900 + int(math.floor(((w + e) / 2 + 180) / 6)) + 1


def tiles(key, max_deg=0.25):
    """The box cut into tiles no bigger than max_deg on a side (OSM API),
    named <key>_r<row>_c<col> (rows south to north, columns west to east).
    For "wm" these are exactly the 12 tiles T1 v0 used."""
    w, s, e, n = CANDIDATES[key][1]
    cols, rows = math.ceil((e - w) / max_deg - 1e-9), \
        math.ceil((n - s) / max_deg - 1e-9)
    dx, dy = (e - w) / cols, (n - s) / rows
    return [(f"{key}_r{r}_c{c}", round(w + c * dx, 4), round(s + r * dy, 4),
             round(w + (c + 1) * dx, 4), round(s + (r + 1) * dy, 4))
            for r in range(rows) for c in range(cols)
            if f"{key}_r{r}_c{c}" not in EXCLUDE_TILES]


def region_name(key):
    """Cache / results name. The White Mountains keep their T1 v0 name."""
    return "t1_white_mountains" if key == "wm" else f"t1_{key}"


GATE1 = {"white_mountains": "wm", "cascades": "cascades",
         "front_range": "frontrange"}      # Gate 1 sample regions -> key


def key_of(name):
    """Inverse of region_name; Gate 1 sample regions map to their key."""
    if name == "t1_white_mountains":
        return "wm"
    if name in GATE1:
        return GATE1[name]
    key = name[3:] if name.startswith("t1_") else None
    return key if key in CANDIDATES else None


def data_dir(key):
    return Path("data") / region_name(key)


def tz(key):
    return CANDIDATES[key][2]


if __name__ == "__main__":
    for k, (label, box, tz, veg) in CANDIDATES.items():
        w, s, e, n = box
        area = (e - w) * 111.32 * math.cos(math.radians((s + n) / 2)) \
            * (n - s) * 111.32
        print(f"{k:11s} {label:48s} {area:7,.0f} km2  {len(tiles(k)):3d} "
              f"tiles  EPSG:{utm_epsg(k)}  {tz}")
