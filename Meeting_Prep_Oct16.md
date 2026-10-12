# Meeting prep: weekly sync with Danni & Tianyi, 16 Oct 2026

*DRAFT written Sunday 11 Oct; the numbers get refreshed on Thursday, after
the last city regions are rebuilt and the 1 m lidar and satellite-embedding
tests are in. About 10 minutes to read. **Part 1 is the must-read.** The
visual version is section 10 of `Project_Explainer.html`; the paper figures
are in `paper/figures/`.*

---

## 1. If you only read one thing

**What happened since 9 Oct.** You asked for "as many regions as possible,
then T2". Both are done or well underway.

- **T1 is done in 17 regions** across the US and Canada (12 from full OSM
  downloads plus the lab crawl; the last city regions are finishing their
  full downloads and rebuild automatically).
  - 2,805 hiking traces, 1,935 walking outings, ~4,600 walking hours.
  - 260k walking segments of 50 m.
  - One combined dataset with a data card. It stays on the cluster
    because it has user names.
- **The evaluation harness for T3 exists and runs.** Every model predicts a
  speed *range* for each 50 m of trail. Each one is graded only on hikes,
  map squares or **whole regions** it never saw.
- **T2 started** with terrain from elevation data, and it produced the
  paper's lead result.

**The lead result (put this on screen):**

| In a region the model has never seen | Better than a slope-only curve by |
|---|---|
| Tobler's 1993 formula | −13% (worse) |
| Campbell et al. 2022's published curve | −0.6% (a tie) |
| OSM trail tags (sac_scale, surface, visibility, width ...) | +0.2% (95% interval −0.5 to +1.0) |
| **Terrain from elevation data** (how "steppy" the trail profile is) | **+1.6% to +2.2%** (interval +0.8 to +2.8) |
| The hiker's own pace from their first km | +8.5% |

- **Terrain beats tags in 15 of 17 unseen regions**; the other two are
  ties. Terrain minus tags is above zero in every bootstrap draw.
- **In plain speed:** the smoothest fifth of trail profiles is ~9% faster
  than slope alone predicts, and the steppiest fifth ~8% slower. Every
  region shows this.
- **Whole-hike time error:** 13.7% with slope alone → 9.4% with the
  hiker's pace plus terrain.

**Two practical outputs:**
- A **terrain-adjusted Tobler formula** with one DEM input (steppiness):
  smooth trails peak at 4.56 km/h, steppy ones at 3.82. It beats tags in
  unseen regions with 5 numbers (`results/t4_terrain_curve/fig_curves.png`).
- **Whole-hike time error** (`paper/figures/fig_hike_time.png`): Tobler
  14.0%, terrain 13.0%, the hiker's own pace + terrain 9.5%.

**Checks a reviewer will ask about (all done):**
- Terrain isn't a proxy for the region. It still adds ~1.8 points after
  each region's own speed offset.
- It isn't a proxy for the hiker. It still adds ~1.8 points once the
  hiker's pace is known.
- About 60% of the gain is uneven grade *inside* the 50 m segment, which an
  average slope or a tag can't see; the rest is difficulty beyond grade.
- Vegetation from national 30 m maps (tree canopy, land cover) adds
  nothing.
- Our travel-mode labels match the hikers' own app labels: only 3% of
  "walkers" were labeled bike or ski.

**Be upfront about:**
- These are 50 m-segment scores. Effects are a few % per segment because
  GPS noise and the hiker dominate. Over whole hikes they add up.
- Most "elevation data" here is USGS 5 m (resampled from 1 m lidar). The
  1 m lidar version (with STRIDE's roughness) arrives this week.
- A few busy API tiles can't reach their oldest uploads (Shenandoah, San
  Gabriels); the lab crawl fills 2016–2022.
- The stop rule is still not hand-checked (my 15-minute task).

**Walk out with:**
1. **Paper framing:** lead with "terrain from remote sensing transfers to
   new regions; map tags don't", with Tobler, Campbell and STRIDE as
   baselines. Agree?
2. **Satellite embeddings:** AlphaEarth (free mirror, all 17 regions done)
   is strong within regions but doesn't transfer reliably to new ones
   (+0.7%; +5% to −5% by region), while terrain does. Present it as "helps
   locally, transfers poorly"? Try another embedding (e.g. TESSERA), or
   ways to make embeddings region-robust?
3. **Vegetation:** worth processing lidar point clouds for understory
   density (STRIDE's 0.85–1.2 m band), given that 30 m canopy showed
   nothing?
4. **Data release** with the paper (segments without user names)?
5. **Slurm account:** keep `engr-class-any` (≤ 8 CPUs/job) or the lab's?

---

## 2. A 10-minute script

1. **Status (1 min).** "T1 is done in 17 regions. I built the test harness
   for T3 and started T2. The first T2 result already answers the paper's
   main question."

2. **The dataset (1 min).** Open `Project_Explainer.html` → section 8, the
   map. "17 regions, ~2,800 hiking traces, 260k walking segments. Each
   segment has a speed, a slope, OSM tags, travel mode, outing and 10 km
   block for the splits."

3. **How we test (1 min).** Section 10, the three panels. "New hikers, new
   10 km squares, and a whole region the model never saw. The third one is
   the headline. Scores are CRPS, which grades the predicted *range*, plus
   whole-hike time error."

4. **The scoreboard (3 min).** `paper/figures/fig_skill.png`.
   - "Tobler is 13% worse than a curve refitted to our data. Campbell's
     2022 curve ties it."
   - "Tags help a bit in regions they were learned on, but not in new
     ones."
   - "Terrain from elevation data keeps its value in new regions."

5. **Per region (1 min).** `paper/figures/fig_regions.png`. "Terrain beats
   tags in 15 of 17 held-out regions; the other two tie."

6. **What terrain means (1 min).**
   `travel-speed-gate1/results/t2_terrain_effects/fig_quintiles.png`.
   "Steppier trail profiles are slower in every region, about 17 points
   from smoothest to steppiest."

7. **Checks (1 min).** Region proxy, hiker proxy, the hidden-climbing
   control, vegetation null.

8. **Questions (1 min).** The list in Part 1.

---

## 3. Backup: details if asked

**What "terrain" is.** Along each segment's map-matched path, every 1 m,
read the elevation; then:
- the spread and maximum of 5 m pitches;
- relief along the line of travel;
- side slope;
- a control for uneven grade ("hidden climbing").
Source: USGS 3DEP (5 m grids for all regions; 1 m lidar where available).

**How each model's range is made.** Prediction + the spread of its errors
on held-out training hikes. So every model is calibrated the same honest
way, and the calibration must transfer too (90% ranges hold 88%).

**Baselines.**
- Tobler 1993.
- Campbell et al. 2022's published median curve (Table A3 of the paper).
- STRIDE 2024 (Campbell, Cutler & Dennison; coefficients from their R
  package), published and refitted. Results this week.
- Our own refitted curves (tent, rounded, Lorentz) all score within 0.5% of
  each other.

**Why tags fail in new regions.** Mappers tag differently by region and
community. The tag effects we measured (e.g. easy trails ~7% faster, poor
visibility up to ~10% slower) don't carry over.

**Personal pace.** The hiker's median speed (relative to the curve) over
their first km, shrunk ×0.6 because one km is noisy. It cuts whole-hike
time error by ~30%. HikingTTE (2024) personalizes too; we do it per
segment and with terrain.

**Where everything is.**
- `DECISIONS_LOG.md` #78–88: every choice and number.
- `docs/NEXT_STEPS.md` §1b–1c: the plan with results.
- `paper/OUTLINE.md`: the 4-page plan.
- GitHub `Brian24NX/GeoAI`.

## 4. Likely questions

- **"Isn't +1.6% small?"** Per 50 m segment, yes: GPS noise and who is
  hiking dominate a single segment. But it is consistent (15 of 17
  regions), its interval excludes zero even when resampling whole regions,
  and it's 8× what tags manage. Over a hike it lowers time error.
- **"Why not deep learning?"** About 1,900 outings is a small sample. The
  plan uses frozen pretrained embeddings (AlphaEarth) instead of training a
  network; the pilot is running.
- **"Is the uneven-grade part real terrain or an artifact?"** It comes from
  the DEM along the mapped trail, not from GPS noise. A finer slope can't
  replace it, because 10 m speeds are too noisy to measure.
- **"What about the Campbell/Wood overlap?"** Campbell fit curves in two
  states; we test transfer across 17 regions and beat tags with remote
  sensing. Wood used OSM classes + lidar in the UK but never held out
  regions.
