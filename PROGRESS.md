# Progress log

One entry per working day: what was done, the numbers, decisions, what's
next. Details and reasons for every decision: `DECISIONS_LOG.md`.

## Status (12 Oct 2026, 03:00 CDT)

**Stage: T1 complete; T2 tier 1 done; T3 harness running on everything.**
- **T1:** 17 regions, 16 from full OSM downloads plus the lab crawl, and the
  Bay Area from the lab crawl only.
- **T2:** elevation terrain at 5 m and 1 m, vegetation, satellite
  embeddings.
- **Lead result:** terrain from elevation data beats OSM tags in unseen
  regions (`docs/NEXT_STEPS.md` §1a).

| Region | Data | Hiking traces | Walking outings | Peak speed v0 (km/h) | Slope sensitivity k | 1 m lidar under trails |
|---|---|---|---|---|---|---|
| White Mountains, NH | API + lab | 235 | 189 | 4.23 | 2.10 | 100% |
| Adirondack High Peaks, NY | API + lab | 103 | 74 | 4.06 | 2.21 | 99% |
| Catskills, NY | API + lab | 73 | 60 | 4.19 | 1.91 | 100% |
| Green Mountains, VT | API + lab | 56 | 25 | 4.52 | 2.46 | 100% |
| Shenandoah, VA | API + lab | 83 | 41 | 4.57 | 1.14 | 100% |
| Great Smoky Mountains, TN/NC | API + lab | 69 | 58 | 3.95 | 1.06 | 88% |
| Asheville / Pisgah, NC | API + lab | 75 | 38 | 4.02 | 1.21 | 90% |
| Colorado Front Range (Boulder–Golden) | API + lab | 206 | 97 | 4.46 | 1.94 | 96% |
| Wasatch Front (Salt Lake City), UT | API + lab | 131 | 91 | 4.80 | 2.06 | 92% |
| Cascades I-90 + Alpine Lakes, WA | API + lab | 684 | 528 | 4.37 | 1.72 | 83% |
| Columbia River Gorge, OR/WA | API + lab | 104 | 67 | 4.63 | 1.55 | 27% (mostly 3 m) |
| Olympic NP (north), WA | API + lab | 175 | 163 | 4.08 | 1.10 (coarse DEM) | 34% |
| Bay Area hills, CA | lab only | 177 | 102 | 4.42 | 1.37 | 98% |
| San Gabriel Mountains (LA), CA | API + lab | 141 | 116 | 4.08 | 1.93 | 100% |
| Yosemite Valley + High Sierra, CA | API + lab | 92 | 86 | 4.17 | 1.88 | 70% |
| Lake Tahoe, CA/NV | API + lab | 230 | 94 | 4.17 | 1.67 | 95% |
| North Shore Mountains (Vancouver), BC | API + lab | 242 | 165 | 4.38 | 1.64 (coarse DEM) | 0% |
| **All 17 pooled** | | **2,876** | **1,994** (sum; 1,992 unique) | **4.31** | **1.80** | |

Tobler (1993): v0 = 6.0 km/h, k = 3.5, fastest slope −5%. Walking analysis
set: 290,640 segments of 50 m, 1,992 outings, 4,702 moving hours, 14,532
km.

---

## Mon 26 Oct 2026

- **Week 10 started: Tobler with learned constants, TODO 1 (the model)**
  (`travel-speed-gate1/exercises/week10_learned_tobler/learned_tobler.py`).
  A small network (two hidden layers of 32, SiLU) maps the 12 terrain
  covariates (plus missing flags) to each segment's a, k_up, k_down
  (softplus), s0 and log_sigma; e stays the reference's. The last layer
  starts with zero weights and the reference constants as biases, so the
  untrained model is the reference curve: on outing5 it matches to ≤ 3e-7
  in all five folds. Claude filled the blanks at Brian's request.
- **TODO 2 (the loss):** mean Student-t negative log-likelihood (nu = 5) of
  the log speeds, centre = the curve with each segment's constants, spread
  = exp(log_sigma). Before training it equals the reference curve's loss on
  the stop rows to five decimals in every fold (0.525, 0.465, 0.443, 0.494,
  0.508). The starting spread is too wide for a Student-t: in fold 0 the
  spread alone would take the loss to ~0.497, so only the drop below that
  is terrain. Blanks filled by Claude at Brian's request.
- **TODO 3 (training):** Adam on mini-batches of the fit rows (2,048, lr
  1e-3); early stopping on the stop rows (patience 5), keeping the best
  weights; test rows untouched. All five outing5 folds in ~12 s on the
  laptop CPU: 13–23 passes, stop loss e.g. 0.525 → 0.457 in fold 0 (the
  spread alone gets ~0.497, so terrain does the rest). Each segment now
  gets its own constants: k_up ~2.0–2.85 and peak speed ~3.6–4.6 km/h
  (10th–90th percentile) instead of 2.6 and 4.2 for all.
  - Reproducibility fix: PyTorch starts from a random seed, so fold 0's
    starting weights changed every run; the model is now seeded before it
    is built and runs are identical. Across starting seeds the loss barely
    moves (~0.001) but the k_up range shifts by ~0.1, so week 11's k(x)
    plots should average a few seeds.
  Blanks filled by Claude at Brian's request. Next: TODO 4, scoring.

## Sun 25 Oct 2026

- **Week 9 log-linear diagnostic** (plan week 9; `travel-speed-gate1/
  exercises/week09_loglinear/`): TODOs 1–3 done together (Claude filled
  the blanks at Brian's request); `fig_loglinear.png`. Median log speed vs
  |slope + 0.05| is not Tobler's straight line: the top is flat (fastest
  bin −0.5% slope, 4.26 km/h vs Tobler's 6 at −5%). Past it, both sides
  fall at about −2.35 (Tobler −3.5); the downhill side sits ~5% lower.
  Real hikers match Tobler near ±15–20% grades and are faster than it on
  the steepest bins. TODO 4's four sentences drafted by Claude at Brian's
  request (in the script, marked as drafted with Claude).

## Fri 23 Oct 2026

- **Lab deck: plain-words speaker notes** for slides 2–7 (Brian asked, one
  slide at a time), each with short answers to likely follow-ups. Slide 6's
  chart now names its zero line ("slope alone"). The PDF backup predates
  that change: Brian had the deck open in PowerPoint, so it wasn't
  re-exported.
- **Q&A sheet corrected:** "2–3% sounds small" had said most of the
  leftover variation is the person and the day, but only ~26% is between
  hikes (`results/t1_findings/numbers.json`); and the cut-details list had
  the tag numbers swapped (+0.9% additive / +0.4% trees). Added answers on
  what terrain is, why tags don't carry over, and whether terrain's lead
  is real.
- **Lab deck simplified for a 5–6 min talk plus 4 min of questions**
  (Brian asked): one message per slide, at most two numbers each. The
  details moved to the speaker notes and to `QA_prep.md` ("Cut from the
  slides"). `make_assets.py` draws three new slide-sized charts with large
  type: speed vs slope (real hikers vs Tobler), terrain vs tags in each
  held-out region, and a map of the 17 regions (circle area = walking
  hours).
  - Removed: the tag-coverage bar chart, the four prior-work cards, the
    downhill panel and its stat, the nine-model bar chart, and the T1–T4
    chips.
  - The scripted notes are about 580 words: ~4 min at 150 words a minute,
    ~5 min with pauses.
  - Validated, rendered in PowerPoint; PDF backup updated.

- **Lab meeting held** (Prof. Jacobs' lab, afternoon); feedback to be
  logged when Brian shares it (the encoder question for week 12).
- **Explainer: section 14 removed** (Brian asked, before sharing the link
  with Danni): his to-do list, the 16 Oct questions for the mentors and
  the "if a mentor asks" answers. The Glossary is now section 14. Rebuilt
  from `docs/explainer_template.html` and republished to the same private
  link (version 3); nothing else on the page changed.

## Thu 22 Oct 2026

- **Lab-meeting deck for 23 Oct** (Prof. Jacobs' lab meeting; Brian asked):
  `meeting_plots/oct23_lab/Zhou_LabMeeting_23Oct.pptx` (+ PDF), 7 slides for
  ~5 min following Dan's outline (problem, prior work, goal, what's done,
  findings, next steps), speaker notes on every slide. Built by
  `build_deck.js` (pptxgenjs 3.12.0, installed locally) from the paper's
  figures, a native chart of sac_scale coverage, and Mt Washington contours
  from the 1 m lidar cells (`make_assets.py`); checked with the PPTX
  validator and a render in PowerPoint.
- **Lab-meeting Q&A sheet** (`meeting_plots/oct23_lab/QA_prep.md`): twelve
  likely questions with short answers. Checked one new fact for it: plain
  RMSE tells the same story as CRPS (unseen regions: terrain −2.1 / −3.1%,
  tags −0.7%, Tobler +12.7% vs the slope curve).
- **Re-paced to the semester plan** (decision #117, Brian's call): we are
  in plan week 9; draft 0 of the paper is five weeks early and becomes the
  safety net. The rest follows the plan's schedule, with Brian doing more
  of the hands-on work (`docs/NEXT_STEPS.md` §7).
- **Week 9 exercise set up for Brian:** the plan's log-linear diagnostic
  (`travel-speed-gate1/exercises/week09_loglinear/`: README + starter
  script; data = a de-identified table of the 289,679 walking segments in
  `cache/exercise/`, not in git). His "one plot" for the 23 Oct meeting.
- **Weeks 10–11 design:** `docs/T3_learned_tobler_design.md`: Tobler with
  constants learned from the covariates plus a Student-t variance head,
  scored on the harness's folds against boosted trees (Gate 2's last box).
  Brian builds it in PyTorch.
- **PyTorch 2.14.1 installed** in the Mac's `.venv` (Brian asked; 127 MB
  from the Python package index). The Apple GPU (MPS) works, and a test fit
  recovered Tobler's v0 and k from synthetic data.
- Meeting brief updated (the week-9 plot, the re-paced plan).
- **Week 10 prepared** (Claude's side of T3): the harness can now save its
  exact folds (`--save-folds`; the reruns reproduce Table I to 5e-14);
  `t3_export_table.py` writes a de-identified modeling table to
  `cache/exercise/` (289,679 segments, 16 covariates, five splits' folds,
  per-fold fit/stop/cal outings, integer hiker ids); `t3_scoring.py` holds
  the harness's CRPS plus Gaussian / Student-t closed forms and a torch
  loss, all checked against 1M-sample brute force; Brian's starter
  (`exercises/week10_learned_tobler/`) reproduces Table I's baseline on all
  five splits to ~1e-12.
- **Bug found and fixed** (decision #118): one hike built in two regions
  shared 363 segment ids, so 363 Gorge segments carried Cascades terrain.
  The join is now on (region, segment id). Rerun measured the effect:
  every number moves ≤ 0.06 points, no conclusion changes; the paper keeps
  its frozen numbers.
- **Understory in three height layers** (plan T2 item, Campbell et al.
  2018; decision #119): computed for all 15 lidar regions from the cached
  point clouds (no downloads). The layers add nothing beyond STRIDE's
  single band (unseen regions +0.03 / +0.01 points), so "lidar vegetation
  adds little" holds with the plan's fuller measure. T2 item closed.
- **Slack note for Danni drafted** (Brian asked): a plain-words walk-through
  of the explainer's "What we've found" figures for Brian to send.
- **Explainer refreshed** before Brian shares it: Finding 7 ("winter isn't
  slower") replaced by the weather result (heat −3%, snow on the ground −4%,
  no gain in new regions); Finding 3's caption ~24% → ~23%. Brian's
  screenshots came from an older copy of the page (the current one already
  had the final numbers: ×1.08 / 1.17 / 1.22 / 1.23, peak 4.31 km/h).
- **Explainer published as a private link** (Brian asked):
  https://claude.ai/artifact/3s5rKBVbtfrbdx5F84S7RK, named "Hiking Speed
  Study"; dark mode now also follows a viewer's explicit theme choice.
  Danni can open it once Brian shares it from the page's Share menu.

## Wed 21 Oct 2026

- **16 Oct meeting with Danni went well.** She said to keep going and do
  whatever is needed next.
- **T1 v2 test, distance along the trail** (decision #109,
  `t1_route_check.py`, White Mountains): measuring distance along the
  trail between matched GPS points removes the corner-cutting loss of
  sparse traces (thinned to 30 s: 99.8% of the full distance kept, vs
  97.4% with straight lines). It would add only 0.6–1.7% distance to most
  traces, so no full rebuild for this alone; a sensitivity check comes
  next.
- **Along-trail distance in all 17 regions** (decision #110): the fix works
  everywhere (thinned to 30 s: 99.3–100.5% of the distance kept, vs
  93.5–97.7% with straight lines). Even dense traces lose 1–3% to straight
  lines on winding trails, so a T1 v2 would raise speeds ~1–3%. Plan: one
  v2 rebuild together with the stop-rule decision from Brian's stop-check
  sheet, then a numbers freeze for the paper.
- **Lidar understory, White Mountains:** Brian approved the ~12 GB download.
  `t2_lidarveg.py` rewritten for it (8 blocks in parallel with an on-disk
  cache, a buffer grid then a KD-tree to find trail points, ground height
  from the 6 nearest ground returns, per-project checkpoints); a 1,500-
  segment pilot ran in under a minute with plausible values. STRIDE's full
  model, with its density term, added to the harness.
- **Lidar vegetation result, White Mountains** (decision #111): the full run
  took 46 min (7.5 GB). Within the same hike, the densest understory fifth
  is 7.5% slower and the sparsest 6% faster, even at similar steppiness.
  Added to terrain it improves predictions in new 10 km squares (+3.6% →
  +5.0%; about +1 point beyond terrain and elevation together), less for
  new hikers. STRIDE's published density term badly over-penalises trails
  (−37%).
- **Lidar vegetation in 15 regions** (decision #112; Brian approved option B,
  all 14 remaining regions with point clouds; 72 GB in total on ENGR, 4
  parallel jobs, ~1 h): it **does not transfer**. In unseen regions it adds
  +0.2 points to terrain (interval −0.2 to +0.5), helping in 9 of 15
  regions; even among the 7 eastern forests, +0.4 (−0.4 to +1.5). Like the
  satellite embeddings, it knows places. Of everything tested, only terrain
  transfers. STRIDE's density term: −18% → −35% in all 15 regions.
- **Numbers frozen on T1 v1** (decision #113): no v2 rebuild before the
  paper. Along-trail distance (~1–3% faster speeds, the same for every
  model) goes into the paper's limits; Brian's stop-check sheet now
  validates the stop rule rather than tuning it. A v2 can come with a data
  release later.
- **Paper fits 4 pages** with the TODO notes, references included, half a
  column to spare. The skill chart and the per-region chart are now one
  figure across both columns (Fig. 3); the whole-hike times and the trail
  map are one sentence each (figures kept); Table I has a lidar vegetation
  row.
- **Check:** 2 of 1,992 walking outings cross from one region into the
  next (0.5% of segments, decision #114); too few to matter.
- **Introduction drafted by Claude** (Brian asked), marked for rewriting
  like Data and Methods: why walking time matters and Tobler; what
  crowdsourced GPS and covariate models found; the gap (no test in unseen
  regions; tags vs remote sensing); three contributions with the headline
  numbers. Three new references (firefighter escape routes, personal
  accessibility, the lab's probabilistic traffic model). Still 4 pages.
- **Results and Discussion drafted by Claude** (Brian asked), marked for
  rewriting like the other drafts. Every number re-checked against the
  harness outputs and the decision log (e.g. Tobler worse in all 17
  regions; 90% intervals cover ~89% for every model; Tobler 21% too fast
  within ±10% grade, 18% too slow above 25%). Wording kept to what the
  tests show (why tags fail; weather). To stay at 4 pages including
  references (older IGARSS kits count them), Fig. 2 and Fig. 3 are a little
  shorter and the drafts were tightened; Fig. 2b's legend no longer covers
  Tobler's line and Fig. 3a's cut-bar labels are readable. Every section is
  now drafted; the abstract is left for Brian.
- **Abstract drafted by Claude** (Brian asked; ~145 words, marked for
  rewriting). To keep 4 pages: the Introduction's sentence of side findings
  went (the abstract carries them) and a few lines were tightened. Methods
  now defines the lidar vegetation inputs that Table I and the Results
  report (group f: understory density, canopy cover and height within 3 m
  of the path, 15 regions), which it had missed.
- **Next steps** (`Meeting_Prep_Oct23.md`): we are ~5 weeks ahead of the
  plan (full draft was due 27 Nov; Gate 2 answered early), so the mentors'
  review moves from December to now. Brian sends the draft (email draft in
  the brief), does the stop-check sheet and starts rewriting; questions for
  Friday: authors, Student Paper Competition, data release, theme, title,
  the freeze (#113), review timeline.
- **IGARSS 2027 call for papers checked:** full 4-page papers only for IEEE
  Xplore and the Student Paper Competition; papers, the competition and
  travel support all due 11 Jan; decisions 12 Mar; conference 11–16 Jul.
  Themes SP.6 / SP.5 / L.7 fit. The reference rule comes with the paper kit
  (10 Nov). Three reference titles fixed (capitals in 3D Elevation Program,
  National Land Cover Database, North America).
- **Independent check of the draft** (decision #115): a fresh Claude
  reviewer read the paper against the results; every point was re-verified
  in the code and result files before changing anything. Main fixes: "new
  hikers" → "new hikes" (that split holds out outings, not people); "tags
  do not transfer" → "transfer less well" (additive tags keep two thirds of
  their gain); lidar vegetation adds ~+0.2 everywhere, not "only within a
  region" (that was a one-region result); 14 of 17 regions with trees;
  match rate 85–99% by region; Eq. (1) coefficients printed; Table I cell
  +0.4 → +0.3. Paper still 4 pages (travel-mode result and one reference
  cut). Brief, outline and explainer updated to match.
- **New hikers, and unseen regions with unseen hikers** (decision #116):
  47 uploaders walked in several regions (24% of segments), so the
  headline test could keep a held-out region's hikers in training. Two new
  tests on the cluster (10 min): holding out whole uploaders changes almost
  nothing (terrain +2.2 / +3.2, tags +1.3 / +1.5); leaving out a region
  together with everyone who hiked there (0.1–8.5% of the training data)
  lowers every model a little and tags most (terrain +1.8 / +2.4, tags
  +0.5 / −0.4; terrain above tags in every draw). The paper now says the
  result holds for regions and hikers the model never saw; still 4 pages.

## Mon 12 Oct 2026

- **Overnight refresh on the complete T1** (00:00–02:34, decision #95):
  rebuilt the combined dataset, checks, all covariates and all 8 harness
  runs.
- **Final unseen-region scores** (CRPS skill vs our refitted slope curve):
  - Tobler −12.5%; Campbell −0.5%; STRIDE −16.8%.
  - Tags +0.9% / +0.4%.
  - **Terrain +2.1% / +2.8%**, beating tags in 16 of 17 regions.
  - Embeddings +1.1%; terrain + embeddings +2.6% / +2.8%; with tags too,
    up to +3.9%.
  - Personal pace + terrain +10.7% / +11.6%.
- **Whole-hike time** (median error): 13.6% (slope) → 13.0% (+ terrain) →
  10.0% (+ personal pace) → 9.6% (+ personal pace + terrain).
- **Terrain formula:** smooth trails 4.60 km/h, steppy ones 3.84 km/h;
  +1.0% in unseen regions with 5 numbers.
- Paper figures, explainer, outline and the 16 Oct brief now use these
  numbers.
- **Speed by travel mode** (T4, decision #96):
  - walking 4.31 km/h, running 10.8, bike/ski 18.0 (peak speeds);
  - bikes are much more slope-sensitive (k 4.6 vs 1.8);
  - the bike-to-walk ratio falls from ~4× on descents to ~1.6× on climbs,
    so a constant mode multiplier (Tobler's approach) fails for bikes;
    runners stay ~2.5×.
- **Uncertainty that depends on terrain** (decision #98): no gain over a
  fixed spread in log speed; ranges are already honest (~89% in 90%
  ranges).
- **Lidar understory pilot sized, not run** (decision #97): reader built
  for USGS point clouds on AWS. The White Mountains alone needs ~12 GB,
  and a small pilot has too few hikes. Question for Danni on 16 Oct.
- **Pace on every trail** (decision #99,
  `results/t4_trail_map/fig_wm_pace.png`):
  - The terrain function, trained on the other 16 regions, predicts pace on
    all 3,369 km of White Mountains trail, 77% of which nobody in our data
    walked.
  - Median 15.2 min/km vs Tobler's 12.8.
  - Tobler is too fast on gentle trails and too slow on steep ones.
- **Paper skeleton** (`paper/main.tex`, compiles to 4 pages): IEEE two-column
  stand-in template, section files with the points to make (TODO notes),
  Table I with the final numbers, the figures, checked references. The
  prose is Brian's.
- **De-identified copy of the dataset** ready on the cluster (decision #100;
  not published; needs the mentors' license decision).
- **Fig. 1 for the paper** (`paper/figures/fig_map.png`): the 17 regions on a
  US/Canada map (Natural Earth outlines), circle area = walking hours, with
  an inset of the White Mountains' segments colored by speed. Wired into
  the paper (still 4 pages).
- **Explainer updated** (`Project_Explainer.html`):
  - new section 11 "What it's good for": the terrain-adjusted formula
    (curves by steppiness), pace on every White Mountains trail, bike/run
    vs walk ratios by slope, whole-hike time errors;
  - plan status, timeline (through 12 Oct), questions for Danni and the
    glossary refreshed;
  - first-pass numbers corrected to the final ones.
- **Slides for 16 Oct** (`meeting_plots/oct16/slides.pdf`, 13 slides,
  beamer): status, dataset map, how we test, the scoreboard, per region,
  what terrain means, checks, the formula, the every-trail map, modes,
  whole hikes, questions. The 10-minute script in `Meeting_Prep_Oct16.md`
  now follows them.
- Whole-hike numbers in the paper notes and the brief had mixed in the 5 m
  run; now all from the final run (13.0% terrain, 10.0% pace, 9.6% both).
- **Two robustness checks** (decision #101,
  `results/t3_harness_robust/robust_summary.md`):
  - **Newer hikes:** trained on hikes up to 2019, tested on 2020–2026:
    terrain +2.2% / +2.9%, tags +0.9%. Same as random new hikers.
  - **GPS recording rate:** in unseen regions the terrain gain is the same
    for traces recorded every ≤ 2 s, 2–10 s and > 10 s (+1.7%, +2.4%,
    +1.9%). Not an artifact of sparse GPS points.
  - Side finding: sparse traces read ~10% slow on flat ground, probably
    because short stops hide between points.
- Paper outline R1–R3c refreshed to the final numbers (some were first-pass:
  "15 of 17", Campbell "−10% in the Adirondacks", embeddings "+0.7%").
- **Paper Fig. 2, speed vs slope** (`paper/figures/fig_curve.png`; the
  plan's claims 2 and 4, missing from the skeleton until now):
  - real hikers peak near 4.2 km/h on level to gently descending trail;
    Tobler is ~20% too fast on gentle grades and ~18% too slow on climbs
    steeper than 25%; Campbell's curve is ~20% too fast on steep climbs;
  - same hiker, same trail (2,763 out-and-back pairs): down/up 1.08 at
    3–10% grade, 1.23 above 30% (Tobler 1.42). Our pooled curve implies
    the same ratios.
  - Added as slide 4; the brief's script now has 14 slides.
- **Where terrain helps** (decision #102): most on descents and level
  trail (+2.3% to +2.8%, additive), least on steep climbs (+0.8%). Footing
  limits descents; effort limits climbs. Tags add ≤ 1.4% at every slope.
- **Travel mode, the plan's test** (decision #103): one shared curve times
  a per-mode multiplier vs a curve per mode, scored on held-out outings.
  Runners: the multiplier (×2.5) is enough. Bikes/skis: their own curve
  predicts 3.8% better; a ×3.2 multiplier is 15% too slow on descents and
  35% too fast on climbs.
- **Sparse traces explained** (decision #104, `t1_sampling_check.py`):
  thinning 1,020 dense walking traces to 30 s between points lowers
  measured speed by 11% (cut corners: −6% distance; hidden stops: +8%
  moving time). Real sparse traces show the same pattern, so it is how we
  measure, not slower hikers. Without traces logged every > 10 s the
  curve peaks at 4.28 km/h (vs 4.17). Data card updated; a T1 v2 fix is a
  question for the mentors.
- **Pipeline guide** (`travel-speed-gate1/PIPELINE.md`): how to re-run
  everything from raw downloads to the paper PDF, with commands, outputs,
  run times, what to re-run after a change, and where each paper number
  comes from. Gaps closed on the way: pinned packages
  (`requirements-pipeline.txt`), the env recipe (`cluster/make_env.sh`),
  a script for the Fig. 1 inset data (`make_paper_data.py`), and the
  `hetero` run in `cluster/refresh_harness.sh`.
- **References checked** (`paper/refs.bib`, `paper/RELATED_WORK.md`):
  - every entry verified against Crossref or arXiv; incomplete ones fixed
    (Wood et al. 2023, HikingTTE, Campbell 2018, AlphaEarth);
  - new: **Huang et al. 2026** (Applied Geography; Hong Kong, 7,913
    tracks, 16 factors incl. weather, boosted trees, random split), Šerić
    et al. 2022 (Sentinel-2, one Croatian range), Higgins 2021, Goodwin et
    al. 2025, Pagneux et al. 2023 (findings not read yet);
  - none of the prior work tests transfer to unseen regions; Wood et al.
    found no whole-route gain over existing functions (13.5–15.5% for
    every model);
  - a related-work sheet for Brian's Introduction; the paper's
    Introduction notes now cite them.
- **Why tags don't transfer, tested** (decision #105, `t3_tag_transfer.py`):
  the paper's explanation ("the same tag means different things in
  different places") was wrong. Within the same hike, tag values act the
  same in every region (harder sac_scale slower in 10/10, paved faster in
  10/10). What differs is presence: sac_scale is on 1–96% of walked trail
  by region, and an untagged trail is faster than a tagged one in some
  regions and slower in others. Terrain: same sign in 17/17 regions.
  In unseen regions the tag model scores about the same on untagged and
  tagged trail (+0.8% / +0.9%), so missing tags aren't where it loses on
  average; trees on tags lose most (+1.5% → +0.4%). Paper, outline, brief
  and explainer corrected.
- **Season and time of day** (decision #106, `t3_season_time.py`; harness
  runs `context`, `contextterrain`): they add nothing for new hikers
  (+0.1%) and hurt in new regions (−0.3%, trees −1.3%); added to terrain
  they lower its unseen-region gain (+2.1% → +1.8%, trees +2.8% → +1.7%).
  Seasonal effects are region-specific (winter hikes +6% in the San
  Gabriels, −5% in the Bay Area), so they don't transfer. Within a hike,
  afternoon vs morning +0.1%; the first hour is ~3% faster and hours 1–3
  ~3% slower, which follows the route (approach, then the climb).
- **No neighbours in training** (decision #107; harness splits `macro`
  and `eastwest`, run `zones`): with a whole zone held out, terrain +1.9%
  / +2.7% (tags +0.7% / −0.1%); trained on the West and tested on the East
  and back, +2.6% / +3.3% (tags +1.5% / −0.3%). Terrain beats tags in every
  bootstrap draw, in all 5 zones and both directions. Caveat: the
  5-number formula travels less well (+0.6% for a zone; fitted on the East
  it misses the West, −0.8%). Harness fix: trees drop columns that are
  constant in a fold's training rows (the main run reproduces to 1e-16).
- **Weather** (decision #108, `t2_weather.py`: Daymet, each hike's day and
  place, 1,921 of 1,992 outings; harness runs `weather`, `weatherterrain`):
  hot days (> 25 °C) 3% slower and snow on the ground 4% slower than the
  region's average hike, rain and humidity nothing clear. But weather
  doesn't improve predictions: alone −0.0% (trees −1.9%) in new regions,
  with terrain +1.9% / +1.4% instead of +2.1% / +2.8%, on top of the
  hiker's own pace +0.0%. The paper's last untested limitation is now a
  result.
- **Paper: Data and Methods drafted by Claude** (Brian asked, 13 Oct), from
  the pipeline code and the final numbers; marked in red as drafts to
  rewrite in his own words, with AI disclosure. NLCD 2021 reference added
  (checked on DataCite). The paper now renders in Times with bold run-in
  heads (`fontenc` T1 under tectonic).
- **Backup slides** (4, after the questions) and a sparse-trace figure.
- **Presenter's card** (`meeting_plots/oct16/presenter_card.pdf`, one page):
  opening line, numbers to know, what's new since 9 Oct, the 7 questions
  (now including which figures to keep), short answers to hard questions.

## Sun 11 Oct 2026

- Shenandoah and Pisgah: left out 5 tiles with highway traffic and no
  hiking signal in the lab crawl (decision #75). Saves ~5–7 h of OSM API time.
- **Two paths in parallel** (Brian's idea): fast *lab-only* builds for the 5
  city regions now (trail maps + elevation + lab traces; ~15–30 min each),
  while their full OSM downloads continue; a finished full download rebuilds
  the region with everything. North Shore built (lab-only): 91 hiking
  traces, 65 walking hikes.
- The size probe now counts tiles that hit the API's depth limit as capped
  instead of skipping the whole region.
- GitHub repo created (private): the whole GeoAI folder except `.venv/` and
  the 12 GB download cache; renamed to **GeoAI** to match the folder.
- **First multi-region findings** (12 regions, 237k walking segments, 1,503
  outings; `results/t1_findings/`):
  - a rounded-top curve beats Tobler's sharp peak;
  - downhill advantage grows 1.08 → 1.24 with grade (Tobler: 1.42);
  - variance after slope: 26% hiker/day, 74% along the trail, 2% region;
  - no fatigue effect.
- **Literature + data survey** (research agent). Our peak speed and rounded
  curve replicate Campbell et al. 2019/2022; Wood et al. 2023 (UK, OSM +
  lidar) is the closest analog; STRIDE (2024) is the lidar baseline. No
  prior work tests transfer to unseen regions, so the paper should lead
  with that: remote sensing vs map tags under leave-one-region-out. Free
  data: AlphaEarth embeddings (Source Cooperative mirror), Meta 1 m canopy
  height (AWS), 3DEP point clouds (AWS), MODIS/SNODAS snow. IGARSS: deadline
  11 Jan 2027 confirmed, portal opens 10 Nov.
- Plan to the paper written: **`docs/NEXT_STEPS.md`**.
- **`Project_Explainer.html`**: one visual page explaining the whole project
  (basics, design, plan, story, pipeline, dataset map, findings, literature,
  next steps, glossary), drawn from the real numbers. Rebuild with
  `make_explainer_data.py` (cluster) + `make_explainer.py`.
- All 5 lab-only builds finished (North Shore, San Gabriels, Columbia Gorge,
  Wasatch, Bay Area): **15 regions built**, 2,375 hiking traces, 1,666
  walking outings, ~4,100 walking hours, 387 bike/ski traces; pooled walking
  curve v0 4.27 km/h, k 1.78. Full downloads continue.
- **Shenandoah built** (full download, 05:50): 83 hiking traces, 41 walking
  outings; one tile capped by the API's time limit (reaches back only to May
  2023; decision #77). **16 regions built**: 2,458 hiking traces, 1,707
  walking outings, 4,172 h; pooled v0 4.28 km/h, k 1.78.
- **Pisgah built** (08:50): 75 hiking traces, 38 walking outings, 32
  bike/ski. **All 17 planned regions are built** (12 full + 5 lab-only):
  2,533 hiking traces, 1,745 walking outings, 4,227 walking hours, 446
  bike/ski traces; pooled v0 4.27 [4.21, 4.33] km/h, k 1.78. Left for T1:
  upgrading the 5 lab-only city regions with their full downloads (North
  Shore running), plus the optional stop-rule hand check.
- **T1 close-out** (morning):
  - Elevation source under the trails, all 17 regions (decision #78): 1 m
    lidar under ≥ 83% of walked trail in 13 regions; weak in Yosemite
    (70%), Olympic (29%), the Columbia Gorge (21%, mostly 3 m) and the North
    Shore (0%: USGS has only ~10 m in Canada).
  - **Mode check** (decision #79): 246 hiking traces whose own GPS app
    named the activity (Garmin "hiking", Strava "Afternoon Ride", ...). 93%
    of labeled hikes were called walking; only 3% of the traces we call
    walking were labeled bike or ski.
  - **One combined dataset** (decision #80): `data/t1_all/` on the cluster.
    It holds 627k segments of hiking traces, with the walking analysis set
    flagged: 261k segments, 1,744 outings, 4,227 h, 13,054 km. One data
    card explains every column (`results/t1_all/DATA_CARD.md`).
- **T3 evaluation harness, first results** (`t3_harness.py`, decisions #81,
  #82). Each model predicts a speed distribution for every 50 m walking
  segment; scored on held-out outings, held-out 10 km blocks, and **held-out
  regions** (leave one of 17 out):
  - **Tobler as published is 13% worse** (CRPS) than a slope-only curve
    refitted to our data, and explains none of the variance (R² −0.07 vs
    0.17).
  - Curve shape barely matters once refitted (tent, rounded, Lorentz:
    within 0.5%).
  - **OSM tags help little:**
    - within a region: +1%;
    - in an unseen region: +0.2% (additive model);
    - boosted trees on tags get worse in unseen regions (−0.9%).
  - **The hiker matters more than the map.** Knowing a hiker's pace from
    their first km cuts whole-hike moving-time error from 13.7% to 9.9%
    (median) in unseen regions. 1 km stretch error drops from 17% to 14%.
  - **Place memory** (how fast *other* hikers went in the same 100 m
    cell) adds +1.3% within a region. Tags reach ~75% of that there, but
    keep little of it in new regions. That gap is what remote sensing has
    to close.
  - Calibrated: 90% intervals cover 88% of held-out speeds.
- **First remote-sensing result** (White Mountains pilot, decision #83):
  - Terrain from the 1 m lidar DEM along each segment's path: roughness,
    "steppiness" of the profile, side slope.
  - Raw pattern: the smoothest fifth of segments is ~14% faster than the
    slope curve says; the steppiest fifth ~11% slower.
  - CRPS skill, new hikers: **lidar +3.8%**, tags +1.7%, place memory
    +1.5%.
  - New 10 km squares: **lidar +3.1%**, tags +0.7%.
  - So lidar beats tags 2–4× in this region and holds up in unseen map
    squares.
- **1 m elevation for all 16 US regions downloading** on the cluster
  (decision #84): ~12.5 GB from USGS 3DEP, ~9 h, in parallel with the OSM
  queue. It feeds the leave-one-region-out test of lidar vs tags, the
  paper's lead.
- **The lead result, all 17 regions** (decision #85):
  - The same terrain profile, read from the 5 m elevation T1 already had (in
    the White Mountains 5 m ≈ 1 m).
  - **In regions the model never saw:** terrain +1.6% (additive) / +2.2%
    (trees) CRPS skill; tags +0.2% / −0.9%.
  - **Terrain beats tags in 15 of 17 held-out regions**; the other two are
    ties.
  - Control: ~60% of the gain is uneven grade *inside* the 50 m segment,
    which a DEM sees and an average slope or a tag can't; ~40% is
    difficulty beyond grade.
  - With the hiker's own pace: +10.3–11.0%, and whole-hike time error
    13.7% → 9.4%.
- **North Shore rebuilt from its full download** (10:53): 242 hiking traces
  (was 91 lab-only), 165 walking outings, v0 4.38 km/h. All 17 pooled:
  2,684 hiking traces, 1,848 walking outings, 4,374 h, v0 4.27 km/h. San
  Gabriels downloading next (≤ 2,307 pages).
- Paper outline: `paper/OUTLINE.md` (4-page budget, Table 1, figures).
- 95% bootstrap intervals (resampling whole regions): terrain minus tags in
  unseen regions +0.7 to +2.4 points, above zero in every draw.
- What "terrain" means in speed, all 17 regions (`t2_terrain_effects.py`):
  - the smoothest fifth of trail profiles is ~9% faster than slope alone
    predicts; the steppiest fifth ~8% slower;
  - every region shows the same direction;
  - side slope doesn't matter.
- Draft paper figures: `paper/figures/fig_skill.png` (skill by model with
  CIs) and `fig_regions.png` (terrain vs tags per held-out region).
- **San Gabriels rebuilt from its full download** (13:55): 141 hiking traces
  (was 81 lab-only), 116 walking outings, v0 4.08 km/h. One LA-side tile is
  capped by the API's time limit and reaches back only to July 2023 (like
  Shenandoah, decision #77). All 17 pooled: 2,744 hiking traces, 1,892
  walking outings, 4,481 h, v0 4.28 [4.21, 4.36] km/h. Columbia Gorge
  downloading next (≤ 3,076 pages).
- The 1 m elevation download is slower than estimated: the Cascades alone
  have 2,766 cells (~3.5 h). ETA for all regions ~21:00 CDT.
- Robustness (decision #86): terrain is not a proxy for "which region". It
  adds ~1.8 points on top of each region's own speed offset.
- **Vegetation from 30 m national maps adds nothing** (decision #87): tree
  canopy cover and land cover (NLCD 2021) give +0.0% in unseen regions,
  alone or with terrain. The remote-sensing signal is in the elevation
  data; fine-scale understory from lidar points is the last vegetation test.
- **Published baselines added** (decision #88):
  - Campbell et al. 2022's median curve (Utah and California AllTrails
    hikes, nothing fitted on our data) ties our refitted slope curve in
    unseen regions (−0.6%, interval includes 0), against Tobler's −13%.
  - It is region-dependent: −10% in the Adirondacks, +4% on the North Shore.
  - STRIDE (lidar model, coefficients from its R package) enters with the
    1 m roughness run tonight.
- **Columbia Gorge rebuilt from its full download** (20:23): 104 hiking
  traces (was 43 lab-only), 67 walking outings, v0 4.63 km/h. All 17
  pooled: 2,805 hiking traces, 1,935 walking outings, 4,597 h, v0 4.29
  km/h. Wasatch downloading (≤ 2,436 pages), then the Bay Area.
- The 1 m elevation download finished (~20:20, 12,499 cells); 1 m terrain
  and STRIDE roughness are being computed for all regions.
- **1 m lidar results** (decision #89):
  - 1 m terrain ≈ 5 m terrain in unseen regions (+1.5–2.4%); terrain beats
    tags in 16 of 17 regions.
  - STRIDE as published −17.7% (worse than Tobler: its roughness term
    over-penalizes trails); refitted +0.1%.
  - The trail's elevation profile carries the signal, not micro-roughness.
- **Satellite embeddings pilot** (decision #90; AlphaEarth 2022 from the
  free Source Cooperative mirror, CC-BY):
  - White Mountains: +2.6–3.3% alone, +4.6–4.9% with terrain
    (complementary).
  - Running for all 17 regions overnight (~10–15 GB) for the unseen-region
    test.
- Draft meeting brief for 16 Oct: `Meeting_Prep_Oct16.md`.
- **A terrain-adjusted hiking function** (T4, decision #91): Tobler's
  formula with peak speed and slope sensitivity depending on trail
  steppiness, one number from any DEM.
  - Smooth trails peak at 4.56 km/h, steppy ones at 3.82.
  - +0.65% in unseen regions; beats tags in 11 of 17 regions.
- **Whole-hike times** (decision #92, 1,199 hikes in unseen regions): median
  error Tobler 14.0%, slope curve 13.7%, + terrain 13.0%, + personal pace
  + terrain 9.5% (52% of hikes within ±10%).
- **Satellite embeddings, all 17 regions** (decision #93):
  - Within regions they're strong (+2.9% with trees; +4.5% with terrain).
  - In unseen regions they're unreliable: +0.7% / −0.1%, ranging from +5%
    to −5% by region.
  - Terrain from elevation data is what transfers.
  - Paper angle: "embeddings help locally, lidar terrain transfers".
- **T1 complete** (23:59):
  - Wasatch rebuilt from its full download: 131 hiking traces (was 60
    lab-only), 91 walking outings, v0 4.80 km/h.
  - The Bay Area stays lab-only: the API times out on its freeway-dense
    tiles (decision #94).
  - Final T1: 17 regions (16 full + 1 lab-only), 2,876 hiking traces,
    1,994 walking outings, 4,702 walking hours, 490 bike/ski traces; pooled
    v0 4.31 [4.23, 4.37] km/h, k 1.80.
  - An overnight refresh (`cluster/refresh_all.sh`) rebuilds the combined
    dataset, checks, covariates and every harness run on the final T1.

## Sat 10 Oct 2026

- **Moved the whole T1 pipeline to the lab cluster** (03:30): project copy
  `/engrfs/project/jacobsn/zhou.n/travel-speed/`, Python 3.12 env, Slurm
  jobs: one polite OSM download queue; each finished region submits its own
  elevation + build jobs. Limits found: ≤ 8 CPUs/job, ≤ 4 running jobs.
- Robustness after a 5-hour network outage on the laptop (decision #67):
  download passes retry stopped tiles; builds require complete downloads;
  USGS elevation fallbacks (direct image, then 4 stitched quarters).
- **OSM API depth limit** (decision #70): the trackpoints API times out
  past ~page 906 of one area; such tiles count as complete up to that limit
  (Cascades Issaquah tile reaches back to Oct 2009; Boulder tile to Aug 2009).
- Fixed: builder read only 600 cached pages per tile; corrupt GPX points
  (NMEA text as coordinates) crashed 5 builds.
- **10 regions built**: 1,923 hiking traces (1,857 independent outings),
  1,369 walking hikes, 3,608 walking hours, 294 bike/ski traces. Pooled
  walking curve: v0 4.25 [4.16, 4.33] km/h, k 1.80 [1.72, 1.87], fastest
  slope −4.5%.
- Elevation source under walked trails (decision #73): 1 m lidar for
  87–100% of segments, except Olympic (29%). Olympic's low k is partly a
  coarse-DEM artifact; the Smokies' isn't.

## Fri 9 Oct 2026

- Morning: weekly meeting with Danni and Tianyi (T1 v0 results).
  **Decisions:** finish T1 completely, then T2; do as many regions as
  possible across the US / North America; lab storage access requested via
  Mark Bober (EIT).
- 1 m elevation downloaded overnight for every walked White Mountains trail.
- Lab storage access works. `OSM_data` = the lab's crawl of the original
  files of ~1.5M public + identifiable OSM traces (2016–2022). Indexed on the
  cluster; 23 candidate regions scouted; traces extracted per region.
- T1 pipeline generalized to any region (`regions.py`, `--region`).
- White Mountains T1 v1: + lab traces, near-duplicate removal, outings →
  235 hiking traces (218 outings); curve unchanged.
- T1 checks done: 50 m segments kept (25 m gives the same curve); 1 m vs 5 m
  slope: no difference (the curve's rounded top is real); map-match rate 97%,
  failures are correct non-matches; travel mode anchored on foot-only
  trails (walk / run / bike-or-ski); 10 km blocks for geographic hold-out;
  sampling-interval stratification.

## Thu 8 Oct 2026

- T1 started for the White Mountains (agreed with Danni 2 Oct): full tile
  download + original GPX files; HMM map-matching test (median 100% matched,
  2.2 m); blind stop-labeling sheet.
- T1 v0 built overnight: 192 hiking traces, 34,652 trail segments; walking
  curve v0 4.25 km/h, k 2.08, fastest slope −5%; robust across 4 stop
  rules; out-and-back pairs: downhill only ~15% faster (Tobler: 42%).

## Fri 2 Oct 2026

- Gate 1 run on real OSM data for 3 candidate regions (v2 of the audit
  script after real data exposed 3 bugs). Usable on-trail share 44–54%.
- Meeting with Danni: **region = White Mountains**. Progress Report #1
  submitted.

---

## Next (as of 11 Oct)

See `docs/NEXT_STEPS.md` (written 11 Oct) for the plan from here to the
IGARSS paper.
