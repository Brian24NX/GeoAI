# Weekly meeting — first project sync

**Brian Zhou** · CSE 5999 · Mentors: Danni Beaulieu, Tianyi Gao · Advisor: Prof. Jacobs

---

## What I did

- Read the semester plan, including section 8 on trace handling
- Submitted the CSE 5999 project plan to Canvas
- **Built a Gate 1 audit script** (made with Claude, tested on fake data). It
  downloads OSM traces for 4 sample boxes per candidate region, sorts them
  into usable vs. shuffled, computes speeds, applies the 0.5 km/h stop filter,
  and saves speed histograms. Every download is cached.
- Wrote plain-English notes on the 4 week-1 papers
- Found a 2026 paper close to our Question 2 (Cutler et al., see questions)

<!-- If you ran gate1_audit.py before the meeting, add the real numbers here:
     usable points %, number of usable traces, median moving speed.
     Then bring results/<region>/speed_histograms.png as your plot. -->

## What broke

Both of these came from testing the script on fake data with realistic GPS
wobble:

1. **The 0.5 km/h stop filter misses stops.** A fake hiker stood still for 20%
   of the hike; the filter caught about 1%. GPS wobble makes standing still
   look like 1–3 km/h. This supports the plan's "speed + minimum duration"
   rule in section 8.
2. **Frequent GPS recording inflates speed.** The same fake 3.5 km/h walker
   read about 9.6 km/h when GPS recorded every second, and 3.5 km/h at every
   30 seconds. My fake wobble exaggerates this (real GPS errors drift slowly
   and partly cancel), so the script checks the real size on real data. This
   supports measuring speed over fixed-length segments, as the plan says.

**Plot:** `stop_filter_problem.png` (fake data)

## Questions for Danni and Tianyi

1. Where does the project stand? Has Gate 1 been done, and which region?
2. What's mine to pick up this week?
3. What counts as "enough" usable traces to pass Gate 1?
4. **Have you seen Cutler et al. (2026)?** Random forest on LiDAR slope,
   vegetation density, and roughness predicts off-trail walking speed
   (R² ≈ 0.78). It's off-trail and doesn't compare against map tags, but it's
   close to our Question 2. How should we position against it?
5. Is RasterNet's code available in the lab? (The project page exists; I
   couldn't confirm public code.)
6. Does the lab have a standard Python environment I should match?
7. What's the process for Earth Engine, lab compute, and swipe access?

## My plan for the next 2 weeks

| Week | What I'll do | Output |
|---|---|---|
| This week | Run Gate 1 on all 3 candidate regions. Add the non-trace columns to the region table (3DEP 1 m coverage, relief, canopy). Read the 4 core papers in full. | Region comparison table, Gate 1 numbers |
| Next week | Gate 1 decision with you. If go: design a better stop detector (speed + minimum duration) and test it on real traces. | Go/no-go, first T1 cleaning step |
