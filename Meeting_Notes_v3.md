# Weekly meeting — Gate 1 results

**Brian Zhou** · CSE 5999 · Mentors: Danni Beaulieu, Tianyi Gao · Advisor: Prof. Jacobs
*2 Oct 2026 · replaces Meeting_Notes_v2*

---

## What I did

- **Ran Gate 1 on real OSM data** (with Claude's help): 3 candidate regions × 4
  sample boxes, ~6.5M GPS points. Every download is cached.
- **Rewrote the Gate 1 script (v2)** after real data exposed bugs the fake
  test couldn't (below). Self-test: 29 checks, all pass.
- **Matched GPS points to OSM ways.** This separates hikers from cars, ski
  lifts, the Cog Railway and sidewalks, and breaks trail time down by
  **permitted mode** and **tag coverage** (plan §6).
- **Filled the non-trace columns** for every box: 3DEP 1 m coverage, LiDAR
  QL and dates, relief, NLCD canopy.
- **First, unvalidated slope–speed curve** vs. Tobler for all three regions.
- Found **STRIDE** (Campbell, Cutler & Dennison 2024, *Sci. Reports*), a LiDAR
  travel-rate model for on- *and* off-path walking.
- From the v2 two-week plan: Gate 1 on all 3 regions ✅, non-trace columns ✅.
  Reading the 4 core papers in full is still to do.

## Gate 1 numbers (4 sample boxes per region)

| | White Mountains | Cascades | Front Range |
|---|---|---|---|
| Usable points: all / **on trails** | 58% / **~46%** | 82% / **~44%** | 82% / **~54%** |
| Hiking traces (≥ 5 min on trails) | 54 | 80 | 82 |
| People (named + anonymous traces) | 17 + 26 | 25 + 34 | 19 + 20 (one person = 23) |
| Hours on trails · median speed | 254 h · 2.7 km/h | 191 h · 3.2 km/h | 185 h · 4.1 km/h |
| Cyclists · bike/horse-permitted trail time | 0 · 5% / ~0% | 4 · 3% / 17% | 7 · 10% / 57% |
| 1 m DEM (boxes / region) · LiDAR QL | 100% / 100% · QL2 | 56% / 70% · QL1 | 98% / 100% · QL1–2 |
| Canopy · `sac_scale` tagged | 79% · 40% | 46% · 55% | 23% · 24% |
| First look: peak speed, slope decay k (Tobler 6.0, 3.5) | 4.3, 2.2 | 4.6, 1.6 | 4.9, 1.8 |

## What broke

1. **The old script would have reported ~100% usable.** The API sends all
   timestamped points first, and it stopped at 10 pages. Mt Washington is
   really 60%.
2. **It threw away multi-hike uploads** (recordings stored out of date order)
   as "shuffled".
3. **10 Hz car loggers read at walking pace** (whole-second timestamps).
4. **Car loggers dominate "identifiable" uploads** (sunnypilot/dragonpilot)
   in the Cascades and Front Range. Sidewalks attracted car points too. So I
   now report the **usable share of trail points** and exclude sidewalks.
5. **3DEP 1 m isn't everywhere:** the Rainier box has none (~3 m, 2007–08),
   Cascade Pass 23%.

**Plots:** `meeting_plots/region_comparison.png` · `meeting_plots/first_look_slope_speed.png`

## Questions for Danni and Tianyi

*(None of the v2 questions have been answered yet; they're all folded in
below.)*

1. **Where does the project stand on the lab side, and what's mine?** Has
   anyone already worked on a trace dataset, a region, or the off-road
   travel-time model this feeds? Is the whole pipeline (T1 → T3) mine?
2. **Gate 1: go? Which region?** I lean **White Mountains**: forest, 100%
   1 m, the most trail hours, but foot-only and QL2. The **Cascades I-90
   corridor** (Snoqualmie + Mt Si: QL1, more tags, newer traces) is the
   alternative. Or pool both for a geographic hold-out.
3. **Is "a few hundred hikes" enough?** That's ~50–80 per region in the
   sample boxes, maybe 150–400 for a full region. The plan imagined tens of
   thousands.
4. **How do we position against STRIDE (2024) and Cutler et al. (2026)?**
   Should STRIDE be a baseline arm next to Tobler?
5. **Access:** what's the process for Earth Engine (does the lab have a
   Cloud project?), lab compute + storage, and swipe? Needed for T2 (~week
   10).
6. OK to drop Question 4 (mode) to a limitations paragraph if we pick the
   White Mountains?
7. Lab GitHub / standard Python env / shared storage? Is RasterNet's code
   in the lab? Canvas milestone dates?

## My plan for the next 2 weeks

| Week | What I'll do | Output |
|---|---|---|
| This week | Gate 1 decision; send access requests; read the 4 core papers in full + STRIDE, Cutler 2026, Newson & Krumm | Region + go; access requested |
| Next week | T1: pull every trace tile for the region, plus full GPX files of identifiable traces; hand-check ~20 stops to tune the stop rule; try HMM map-matching on 5 traces | Full trace set + data card draft; stop-rule plot |
