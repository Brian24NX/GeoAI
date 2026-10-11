# Weekly meeting — T1 dataset v0 (White Mountains)

**Brian Zhou** · CSE 5999 · Mentors: Danni Beaulieu, Tianyi Gao · Advisor: Prof. Jacobs
*9 Oct 2026 · follows Meeting_Notes_v3 (2 Oct)*

---

## What I did this week

- **Built T1 v0, the trace dataset for the White Mountains** (with Claude's
  help). It's ahead of the catch-up schedule, so T2 can start next week
  instead of week 10.
  - Downloaded every GPS trace in the national forest (12 tiles, ~3.3M
    points), plus the **original GPX file** of every identifiable trace.
  - Dropped car loggers and duplicates; joined anonymous traces that the API
    had split.
  - **HMM map-matching** of every trace to the OSM trail graph
    (`leuvenmapmatching`).
  - Cut the matched paths into **50 m and 25 m segments**. Each has: speed
    over moving time; signed slope from the 5 m USGS DEM (+ = uphill, checked
    by an automatic test); direction; trail tags; permitted modes; date and
    time; uploader.
  - A data card: `data/t1_white_mountains/data_card.md`.
- **Stop-rule sensitivity check:** every headline number is rebuilt and refit
  under 4 stop rules.
- **First looks at Q1, Q3 and Q2** (below). All intervals are 95%, from
  resampling whole traces.
- From the v3 two-week plan: full trace set ✅ · full GPX files ✅ · HMM
  map-matching ✅ (all traces, not just 5) · data card ✅ · stop-rule hand
  check ⚠️ (sensitivity check instead) · lab storage ⚠️ (permission denied).

## The dataset

| | |
|---|---|
| Hiking traces (≥ 5 moving min on trails) | **192 uploads = 235 hiking days** |
| People | 40 named uploaders + 98 anonymous traces; top uploader = 8% of the data |
| Trail segments (50 m) | **34,652** ≈ 1,733 km, 592 moving hours, 789 OSM trail ways |
| Map-matching | median trace 100% matched, median 2.9 m from the trail; 0.8% of segments flagged suspect |
| Dates | 2008–2026; 32% of moving time is in winter (Dec–Mar) |
| Tags on trail segments | `sac_scale` 51% · `surface` 48% · `width` 0.2% · foot-only 65% |

## Results

**1. Q1: Tobler is right about steep trails and ~30% too fast on gentle
ones.** Walkers only (184 traces, 31,901 segments):

| | Peak speed v0 | Slope decay k | Fastest slope |
|---|---|---|---|
| Tobler (1993) | 6.0 km/h | 3.5 | −5% |
| **T1 data** | **4.25** [4.08, 4.47] | **2.08** [1.95, 2.22] | **−5.0%** [−6.0, −4.0] |

- The fastest slope matches Tobler. On steep grades (about 15–30%) the data
  sit almost on Tobler's curve. The gap is on gentle grades, where Tobler
  expects 5–6 km/h and hikers do about 4. In the plan's §9 diagnostic, the
  curve's top is rounder than Tobler's sharp peak.
- **In hours:** Tobler's predicted moving time is **16% too short** for the
  median trace, and **82%** of traces were slower than Tobler. Refitting the
  curve (cross-validated by trace) only cuts the typical error from **19% to
  17%**. Slope alone can't explain why one hike is faster than another, and
  that remaining error is what T2/T3 must reduce.

**2. Robust to the stop rule.** The 4 rules remove 21–30% of recorded time,
but v0 stays at 4.14–4.25 and k at 2.05–2.13.

**3. Q3 first look: downhill is only ~15% faster, not 42%.** Same hiker, same
trail, both directions: 293 pairs from 107 traces. The median down/up speed
ratio is **1.15** [1.12, 1.20], and 1.22 [1.16, 1.28] on 10–20% grades.
Tobler predicts 1.42; our fitted curve predicts 1.23.

**4. Q2 teaser: tags carry information beyond slope.** At the same slope,
segments on `sac_scale=hiking` trails are **14% faster** [4, 29] than on
`mountain_hiking` trails, and untagged trails are 11% slower [6, 16]. This is
a raw comparison (no control for who walked where). Half the segments have no
`sac_scale`, and that's the gap remote sensing should fill.

## What broke / caveats

1. **A trace isn't always one hike.** 13 uploads hold several days (one holds
   16). Counts now show both. Resampling stays by trace, which is the
   cautious choice.
2. **One trace is dated 1987**, probably a GPS clock bug. Its season columns
   are wrong; it will be flagged in v1.
3. **The stop rule isn't checked by hand.** The blind labeling sheet is
   built, but I haven't done a careful labeling pass. The sensitivity check
   stands in for now.
4. **The rounder top could be real or noise.** Real, because gentle WM trails
   are rocky and summits and junctions are flat. Noise, because slope from
   the 5 m DEM blurs a sharp peak. T2's 1 m DEM will tell them apart.
5. **Lab storage:** `/engrfs/project/jacobsn/OSM_data` gives *Permission
   denied*. I need to be added to the `ENGR-Lab-jacobsn` group.

**Plots** (`meeting_plots/oct9/`): `fig_t1_dataset.png` ·
`fig_t1_slope_speed.png` · `fig_t1_stop_rules.png` · `fig_t1_out_and_back.png`

## Questions for Danni and Tianyi

1. **T1 v0 design:** is there anything to change before T2 builds on it? The
   current choices: 50 m segments along the matched path; speed = length ÷
   moving time; walkers = trace median ≤ 7 km/h; intervals by resampling
   traces.
2. **Stop rule:** is the 4-rule check enough for now, or should we label
   stops by hand (~50 moments, ~30 min)?
3. **Enough data?** One region gives 235 hiking days, and the intervals are
   already about ±5%. Do we still need a second region as a geographic
   hold-out? The Cascades I-90 corridor already has Gate 1 data.
4. **Lab storage:** who can add me to `ENGR-Lab-jacobsn`, and what's in
   `OSM_data`? Could it add traces?
5. **T2 order:** my plan is 1 m DEM terrain → canopy → LiDAR point-cloud
   metrics → imagery. Does the lab have a preferred imagery encoder, or an
   Earth Engine project?

## My plan for the next 2 weeks

| Week | What I'll do | Output |
|---|---|---|
| 12–16 Oct | **T2 v0, terrain:** 1 m DEM along every trail segment (slope at 1 m, surface roughness). Does the curve's top sharpen with 1 m slope? Add NLCD canopy per segment. Flag bad dates; freeze an OSM snapshot for the tags. | T2 v0 table; updated slope–speed curve |
| 19–23 Oct | **T2 v1, vegetation:** LiDAR point-cloud metrics (canopy height, understory density) from USGS 3DEP, one tile first. **T3 first look:** Tobler vs refit vs Tags arms on held-out traces. | First 3 arms compared |
