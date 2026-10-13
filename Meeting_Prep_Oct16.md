# Meeting prep: weekly sync with Danni & Tianyi, 16 Oct 2026

*Updated Monday 12 Oct, 03:00, with the FINAL numbers from the complete
T1. About 10 minutes to read. **Part 1 is the must-read.** The visual
version is section 10 of `Project_Explainer.html`; the paper figures are in
`paper/figures/`.*

---

**One page to keep next to the slides:** `meeting_plots/oct16/presenter_card.pdf` (opening line,
numbers, what's new, the questions, short answers to hard questions).

## 1. If you only read one thing

**What happened since 9 Oct.** You asked for "as many regions as possible,
then T2". **T1 is complete and T2 tier 1 is done.**

- **T1: 17 regions** across the US and Canada.
  - 16 regions from full OSM downloads plus the lab crawl. The Bay Area
    uses lab data only: the OSM server times out on its freeway-dense
    tiles.
  - **2,876 hiking traces, 1,992 walking outings, 4,702 walking hours.**
  - **290,640 walking segments of 50 m.**
  - One combined dataset with a data card. It stays on the cluster
    because it has user names.
- **T3's evaluation harness exists and runs.** Every model predicts a speed
  *range* for each 50 m of trail and is graded only on hikes, map squares
  or **whole regions** it never saw.
- **T2 tier 1 is done for all regions:**
  - terrain from USGS elevation (5 m and 1 m lidar);
  - 30 m vegetation;
  - AlphaEarth satellite embeddings.

**The lead result (put this on screen; `paper/figures/fig_skill.png`):**

| In a region the model has never seen | Better than a slope-only curve by [95% CI] |
|---|---|
| Tobler's 1993 formula | −12.5% (worse) |
| STRIDE 2024 lidar model (published) | −16.8% (worse); refitted +0.2% |
| Campbell et al. 2022's published curve | −0.5% (a tie) |
| OSM trail tags (sac_scale, surface, visibility, width ...) | +0.9% [0.1, 1.7] (simple model); +0.4% (trees) |
| Vegetation from 30 m maps | −0.1% (nothing) |
| Satellite embeddings (AlphaEarth) | +1.1% [0.1, 2.6] |
| **Terrain from elevation data** (how "steppy" the trail profile is) | **+2.1% [1.5, 3.1] (simple); +2.8% (trees)** |
| Terrain + embeddings + tags | up to +3.9% [2.7, 5.7] |
| The hiker's own pace from their first km (+ terrain) | +8.4% (+10.7 to 11.6%) |

- **Terrain beats tags in 16 of 17 unseen regions.** Terrain minus tags is
  above zero in every bootstrap draw.
- **In plain speed:** the smoothest fifth of trail profiles is ~9% faster
  than slope alone predicts, and the steppiest fifth ~8% slower. Every
  region shows the same direction.
- **Embeddings** are strong within regions but less reliable in new ones
  (−5.6% to +8.3% by region). Physical terrain is what transfers.

**Speed vs slope** (the plan's claims 2 and 4; `paper/figures/fig_curve.png`):
- Real hikers peak near 4.2 km/h on level to gently descending trail;
  Tobler says 6.
- Tobler is ~20% too fast on gentle grades and ~18% too slow on climbs
  steeper than 25%. Campbell's curve is right near level but ~20% too
  fast on steep climbs.
- **Same hiker, same trail** (2,763 out-and-back pairs): going down is 8%
  faster than going up at 3–10% grade and 22–23% faster above 20%.
  Tobler says 42% at every grade.

**Two practical outputs:**
- A **terrain-adjusted Tobler formula** with one DEM input (steppiness).
  Smooth trails peak at 4.60 km/h, steppy ones at 3.84 (Tobler: 6.0). It
  gets +1.0% in unseen regions with 5 numbers
  (`travel-speed-gate1/results/t4_terrain_curve/fig_curves.png`). Be
  upfront: it travels less well than the full terrain models (+0.6% with a
  whole zone held out; fitted on the East only, it misses the West).
- **Whole-hike time error** (`paper/figures/fig_hike_time.png`, 1,354
  hikes): Tobler 13.7%, slope curve 13.6%, + terrain 13.0%, + the hiker's
  own pace 10.0%, + own pace + terrain 9.6%.

**Checks a reviewer will ask about (all done):**
- **Not a region proxy:** terrain still adds ~1.9 points after each
  region's own speed offset.
- **Not a hiker proxy:** it still adds ~2.3 points once the hiker's pace is
  known.
- **Newer hikes:** trained on hikes up to 2019 and tested on 2020–2026,
  terrain still adds +2.2% (tags +0.9%). No drift over time.
- **No neighbours in training:** with a whole zone held out (Northeast,
  Southern Appalachians, Rockies, Pacific Northwest, California), terrain
  adds +1.9% (tags +0.7%); trained on the West and tested on the East and
  back, +2.6% (tags +1.5%). Terrain beats tags in every bootstrap draw.
- **Season and time of day:** they add nothing in new regions (−0.3%;
  −1.3% with trees), and added to terrain they lower its gain. Seasonal
  effects differ by region (winter faster in the San Gabriels, slower in
  the Bay Area). Afternoon vs morning on the same hike: +0.1%.
- **Where it helps:** most on descents and level trail (+2.3% to +2.8%),
  least on steep climbs (+0.8%). Footing limits you going down; effort
  limits you going up.
- **GPS quality:** the same gain on traces recorded every ≤ 2 s, 2–10 s
  and > 10 s (+1.7%, +2.4%, +1.9%), so it is not an artifact of sparse
  GPS points. Side finding: sparse traces read ~10% slow. Thinning dense
  walks to 30 s between points reproduces it (straight lines cut corners,
  short stops hide between points), so it is how we measure, not slower
  hikers.
- **Travel mode** (plan question 4): on held-out hikes, a constant ×2.5
  is as good as a curve of their own for runners; bikes and skis need
  their own curve (3.8% better).
- **Uneven grade:** about 60% of the gain is uneven grade *inside* the 50 m
  segment, which an average slope or a tag can't see; the rest is
  difficulty beyond grade.
- **1 m vs 5 m:** 1 m lidar ≈ 5 m for this signal.
- **STRIDE:** its roughness measure adds ~nothing on trails.
- **Travel mode:** our labels match the hikers' own app labels (327
  labeled traces); 5% of "walkers" are labeled bike or ski.

**Be upfront about:**
- These are 50 m-segment scores. Effects are a few % per segment because
  GPS noise and the hiker dominate; over whole hikes they add up.
- A few busy API tiles can't reach their oldest uploads (Shenandoah, San
  Gabriels); the lab crawl fills 2016–2022.
- The Bay Area is lab-only.
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
3. **Vegetation from lidar points** (STRIDE's 0.85–1.2 m understory band;
   the reader is built and tested):
   - The White Mountains alone needs ~1.3 billion points (~12 GB, ~24,000
     block reads).
   - All 17 regions would be ~100+ GB.
   - A small pilot has too few hikes (43) to test.
   - Worth doing it for 1–3 regions, given that 30 m canopy showed
     nothing?
4. **Data release** with the paper? A de-identified copy is ready on the
   cluster (`data/t1_release/`: no user names, hashed ids, month/hour
   only). It needs a license decision (OSM-derived data falls under the
   ODbL) and the lab's data policy.
5. **Slurm account:** keep `engr-class-any` (≤ 8 CPUs/job) or the lab's?
6. **Sparse GPS traces** read up to ~11% slow (a measurement effect; up
   to 27% of segments). Fix it in a T1 v2 (distance along the trail
   between matched points, plus an interval correction), use only traces
   logged every ≤ 10 s for absolute speeds, or just report it?
7. **Figures:** the paper draft runs to 5 pages with 6 figures. Which 3–4
   to keep (suggestion in `paper/OUTLINE.md`)?

---

## 2. A 10-minute script

Slides: `meeting_plots/oct16/slides.pdf` (14 slides; the numbers match
`docs/NEXT_STEPS.md` §1a).

1. **Status (slides 1–2, 1 min).** "T1 is done in 17 regions. I built the
   test harness for T3 and finished T2 tier 1. The first result already
   answers the paper's main question."

2. **The dataset (slide 3, 30 s).** "17 regions, ~2,900 hiking traces,
   290k walking segments. Each segment has a speed, a slope, OSM tags,
   travel mode, outing and 10 km block for the splits."

3. **Speed vs slope (slide 4, 1 min).** "Real hikers peak near 4.2 km/h,
   not Tobler's 6. Tobler is too fast on gentle grades and too slow on
   steep climbs. On the same trail, the same hiker goes down only 8–22%
   faster than up; Tobler says 42%."

4. **How we test (slide 5, 1 min).** "New hikers, new 10 km squares, and a
   whole region the model never saw. The third one is the headline. Scores
   are CRPS, which grades the predicted *range*, plus whole-hike time
   error."

5. **The scoreboard (slide 6, 2 min).**
   - "Tobler is 13% worse than a curve refitted to our data. Campbell's
     2022 curve ties it. STRIDE's published curve is 17% worse."
   - "Tags help a bit in regions they were learned on, but not in new
     ones."
   - "Terrain from elevation data keeps its value in new regions."

6. **Per region (slide 7, 30 s).** "Terrain beats tags in 16 of 17
   held-out regions. The exception is Yosemite."

7. **What terrain means (slide 8, 1 min).** "Steppier trail profiles are
   slower in every region, about 17 points from the smoothest fifth to the
   steppiest."

8. **Checks (slide 9, 1 min).** Region proxy, hiker proxy, newer hikes,
   GPS rate, the hidden-climbing control, vegetation null.

9. **Practical results (slides 10–13, 1 min; skip if time is tight).** The
   formula with one DEM number, pace on every White Mountains trail,
   travel modes, whole-hike time.

10. **Questions (slide 14, 1 min).** The list in Part 1.

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
way, and the calibration must transfer too (90% ranges hold 88–90%).

**Baselines.**
- Tobler 1993.
- Campbell et al. 2022's published median curve (Table A3 of the paper).
- STRIDE 2024 (Campbell, Cutler & Dennison; coefficients from their R
  package): published −16.8%, form refitted +0.2%.
- Our own refitted curves (tent, rounded, Lorentz) all score within 0.5% of
  each other.

**Why tags fail in new regions** (tested 12 Oct,
`travel-speed-gate1/results/t3_tag_transfer/fig_tag_vs_terrain.png`).
- Not because tags mean different things. Within the same hike, harder
  sac_scale is slower in every region where it's used (10 of 10), and
  paved is faster (10 of 10).
- It's that tags are missing unevenly. sac_scale is on 96% of walked trail
  in the Adirondacks and 1% in the Green Mountains, so tags can only help
  on part of each region's trails. Whether a trail is tagged at all says
  different things in different regions (untagged trails are faster in
  some, slower in others).
- The flexible tag model (trees) loses most in a new region (+1.5% →
  +0.4%), as if it learned region-specific tag combinations.
- Terrain is on every trail, with the same effect in all 17 regions.

**Personal pace.** The hiker's median speed (relative to the curve) over
their first km, shrunk ×0.6 because one km is noisy. It cuts whole-hike
time error by ~30%. HikingTTE (2024) personalizes too; we do it per
segment and with terrain.

**Where everything is.**
- `DECISIONS_LOG.md` #78–100: every choice and number.
- `docs/NEXT_STEPS.md` §1a: final numbers (§1b–1c: first pass).
- `paper/OUTLINE.md`: the 4-page plan.
- GitHub `Brian24NX/GeoAI`.

## 4. Likely questions

- **"Isn't +2% small?"** Per 50 m segment, yes: GPS noise and who is
  hiking dominate a single segment. But it is consistent (16 of 17
  regions), its interval excludes zero even when resampling whole regions,
  and it's more than twice what tags manage (2.3× for the simple models,
  7× for the trees). Over a hike it lowers time error.
- **"Why not deep learning?"** About 2,000 outings is a small sample. The
  plan uses frozen pretrained embeddings (AlphaEarth) instead of training a
  network. Result: they help within regions but transfer less reliably than terrain.
- **"Is the uneven-grade part real terrain or an artifact?"** It comes from
  the DEM along the mapped trail, not from GPS noise. A finer slope can't
  replace it, because 10 m speeds are too noisy to measure.
- **"What about the Campbell/Wood overlap?"** Campbell fit curves in two
  states; we test transfer across 17 regions and beat tags with remote
  sensing. Wood used OSM classes + lidar in the UK but never held out
  regions, and found no whole-route gain (13.5–15.5% error for every
  model).
- **"Anything new in 2026?"** Huang et al. (Applied Geography, 2026):
  boosted trees with 16 factors, weather included, on 7,913 Hong Kong
  tracks, tested with a random split in one city. Same tool family, no
  transfer test, and no remote sensing vs tags. They have weather; we
  don't yet. Date and time of day add nothing in our new-region test
  (season differs by region). Every reference is checked:
  `paper/RELATED_WORK.md`.
