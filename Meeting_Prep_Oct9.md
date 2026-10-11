# Meeting prep — weekly sync with Danni & Tianyi, 9 Oct 2026

*Written overnight, 9 Oct. About 10 minutes to read. **Part 1 is the
must-read**; the rest is backup. The one-page version to put on screen is
`Meeting_Notes_v4.md`, and the plots are in `meeting_plots/oct9/`.*

---

## 1. If you only read one thing

**What happened this week.** T1, the trace dataset, now exists for the White
Mountains (version 0). We downloaded every public GPS trace in the national
forest, cleaned it, matched it to the OSM trail map, and cut it into 50 m
pieces, each with a speed and a slope. Every later step builds on this table:
T2 adds remote-sensing columns, T3 compares the four arms, T4 draws the
curves. **You're ahead of the catch-up schedule:** T2 can start next week
instead of week 10.

**The dataset in one line:** 192 uploads (235 hiking days) → 34,652 trail
segments of 50 m, about 1,733 km and 592 hours of moving on 789 different
OSM trails.

**Three findings to present.** All intervals are 95%, from resampling whole
traces.

1. **Tobler is right about steep trails and wrong about easy ones.**
   - Hikers' best speed is **4.25 km/h, not Tobler's 6.0** (about 30% slower).
   - They slow down **less** on steep slopes (k 2.1 vs Tobler's 3.5).
   - The fastest slope, −5%, matches Tobler exactly.
   - In hours: Tobler's predicted moving time is **16% too short** for the
     median trace.
2. **None of this depends on the stop rule.** Four rules for "standing
   still" remove between 21% and 30% of the time, but the curve barely moves.
3. **Downhill is only ~15% faster than uphill, not 42%.** This is the Q3
   first look: same hiker, same trail, both directions.

**Plus a teaser for the core question (Q2).** At the same slope, people move
**14% faster** on trails tagged as easy (`sac_scale=hiking`) than on
`mountain_hiking` trails. So tags matter, and half the trail segments don't
have them. That's the gap remote sensing should fill.

**Be upfront about four things:**
- The stop rule still isn't checked by hand.
- One trace has a 1987 date (a GPS clock bug).
- "192 traces" are uploads, and a few uploads hold several days.
- The lab folder on ENGRFS still says *Permission denied*.

**Walk out with:**

1. OK (or changes) on the T1 design before T2 builds on it.
2. Stop rule: is the sensitivity check enough, or do we label stops by hand?
3. Who adds you to the `ENGR-Lab-jacobsn` group, and what's in `OSM_data`.
4. One region or two (a second region as a geographic hold-out)?
5. The T2 order, and whether the lab has a preferred imagery model or an
   Earth Engine project.

---

## 2. A 10-minute script

Put each figure on screen as you get to it.

1. **Status (1 min).** "Last week we picked the White Mountains. This week I
   built T1 v0, the full trace dataset. It's ahead of the catch-up schedule,
   so T2 can start next week."

2. **`fig_t1_dataset.png` (2 min).** "Every line is a trail someone hiked
   with a GPS, colored by their speed. 192 uploads, which is 235 hiking days,
   cut into 34,652 segments of 50 m. That's about 1,700 km and 590 moving
   hours on 789 OSM trails. The matching works: the median trace is 100%
   matched, and the median point sits 2.9 m from its trail."
   - Point at examples. The fastest trail is the **Lincoln Woods Trail**
     (center, around 44.08 N), an old logging-railroad grade: 5.3 km/h,
     about 2% slope.
   - The most-walked named trail is **Tuckerman Ravine** on Mt Washington
     (13 traces), at 2.5 km/h.

3. **`fig_t1_slope_speed.png`, the main result (3 min).**
   - Left panel: "Each blue dot is the median speed at that slope. Green is
     our fit of Tobler's formula, dashed is Tobler as published. Same shape
     and same fastest slope (−5%), but our peak is 4.25 instead of 6.0."
   - Right panel: "This is the plan's §9 diagnostic. On these axes Tobler's
     formula is a straight line. Our data aren't quite straight: they're flat
     at the top, then they follow Tobler's line on steep grades. So Tobler is
     right about the steep parts and wrong about the easy parts."
   - Then give the hours: "If you use Tobler to predict these hikes' moving
     time, it's 16% too short for the median trace, and 4 in 5 traces were
     slower than Tobler. Refitting the curve only cuts the typical error from
     19% to 17%. So slope explains the average, not why one hike is faster
     than another. That's T2's job."

4. **`fig_t1_stop_rules.png` (1.5 min).** "The stop rule is the biggest choice
   I haven't validated. So I rebuilt everything under four rules. They remove
   21–30% of the time, but the curve barely moves, and it's far from Tobler
   under every rule."

5. **`fig_t1_out_and_back.png` (1.5 min).** "This is the Q3 first look. When
   the same person walks the same trail up and back, how much faster is going
   down? Each bubble is one person on one trail. Tobler says 42% faster at any
   grade over 5% (the dashed line). The data say about 15%. Three in four
   pairs are faster going down, but by much less than Tobler says."

6. **Q2 teaser, then caveats (1 min).** Give the `sac_scale` numbers, then the
   four "be upfront" points from Part 1.

7. **Questions:** the rest of the meeting.

---

## 3. The figures in plain English

### `fig_t1_dataset.png`: the map

- Each colored line is made of 50 m trail segments walked by someone with a
  GPS. Color = speed: yellow is 5 km/h or more, purple is slow.
- The grey lines are the 12 download tiles.
- **Why the gaps?** We only have trails that someone uploaded a GPS track
  for. The popular areas are dense: the Presidentials (top right, Mt
  Washington) and Franconia / Pemigewasset (center).

### `fig_t1_slope_speed.png`: slope vs speed

- Slope is rise over run along the direction of walking. +10% means climbing
  10 m per 100 m; −10% means descending.
- **Left panel:**
  - blue dots = median speed in each 2% slope bin;
  - light-blue band = the middle 50% of segments (how much people vary);
  - green = our fit of Tobler's formula shape, with its 95% band;
  - dashed = Tobler as published.
- **Right panel:** Tobler's formula is `ln(speed) = ln(6) − 3.5 × |slope +
  0.05|`.
  - So if the formula's shape is right, plotting ln(speed) against
    |slope + 0.05| gives a straight line.
  - Filled dots are the uphill side; open squares are the downhill side.
    They overlap, so the curve really is symmetric around −5%, as Tobler
    says.
  - But the line is bent: flat at the top.
- **The three fitted numbers:**
  - **v0** = top speed, on the best slope;
  - **k** = how fast speed drops as the slope gets steeper;
  - **s0** = where the peak is (here −5%).

### `fig_t1_stop_rules.png`: the stop-rule check

- A stop is when you stand still: lunch, a view, a shoelace. Speed should be
  measured while moving, so stops are cut out first.
- Defining a stop is a judgment call. Plan §8 warns it moves the results
  more than any model choice.
- **The four rules:**
  - the plan's crude rule: anything slower than 0.5 km/h;
  - three versions of "you stayed within X m for at least Y seconds":
    30 s / 5 m, 60 s / 10 m (our draft default), and 90 s / 15 m.
- **Reading it:** the left panel shows how much time each rule removes. The
  middle and right panels show v0 and k with 95% intervals; Tobler's values
  are the dashed lines.

### `fig_t1_out_and_back.png`: the Q3 first look

- **Out-and-back** means the same person walks a trail up and then back down
  (or the reverse). It's a natural experiment: same legs, same trail, same
  day. Only the direction changes.
- **The y-axis** is log2(speed down ÷ speed up):
  - 0 = same speed;
  - +0.5 = down 41% faster;
  - +1 = down twice as fast.
- The dashed line is Tobler (flat at 0.5 above a 5% grade).
- **Bubble size** = how much trail the pair covers.
- **Numbers:**
  - median ratio 1.15 [1.12, 1.20], from 293 pairs in 107 traces;
  - 10–20% grades: 1.22 [1.16, 1.28];
  - Tobler: 1.42; our fitted curve: 1.23 (it agrees).

---

## 4. Likely questions and good answers

**"Why is the peak speed so low? Are your speeds right?"**
- Three checks agree:
  - The Gate 1 first look also gave 4.3 km/h for the White Mountains, using
    a different method (nearest trail, no HMM).
  - The number doesn't move under any of the 4 stop rules.
  - On steep grades the data match Tobler, so speed and slope aren't broken
    across the board.
- White Mountains trails are famously rocky and rooty, so "gentle" doesn't
  mean "easy".
- Tobler fit his formula to Imhof's published walking figures from the
  1950s, not to GPS hikes.
- A possible artifact: slope noise from the 5 m DEM blurs the peak. T2's 1 m
  DEM will test that.

**"How good is the map-matching?"**
- The median trace is 100% matched, and the median point is 2.9 m from its
  trail.
- On the 17-hike test it agreed 97% with the simple nearest-trail rule.
- Volunteer this caveat: many OSM trails were drawn from these same GPS
  uploads, so the 2.9 m flatters us.

**"Why resample whole traces for the intervals?"** Segments from the same hike
aren't independent: same person, same day, same weather. Resampling single
segments would make the intervals far too narrow (plan §10).

**"How many people is this?"**
- 40 named uploaders, plus 98 anonymous traces. Anonymous traces could
  include repeat people; we can't tell.
- No one dominates: the top uploader is 8% of the segments.

**"Is this enough data for a paper?"**
- For the curve, yes: the intervals are already about ±5%.
- For T3 (tags vs remote sensing), what matters is how many different trails
  we have (789 OSM ways) and how many of them are tagged.
- A second region as a hold-out would make the paper stronger. That's your
  question 3.

**"Why 50 m segments?"** Long enough for GPS and elevation noise to average
out, and short enough that the slope is roughly constant. A 25 m version is
saved too: plan §8 says to choose by how much the slope varies inside a
segment.

**"What about bikes (Q4)?"**
- 65% of trail segments are foot-only.
- The walker filter dropped only 8 of 192 traces.
- Q4 stays a limitations paragraph, as discussed last week.

**"What does 'refit, cross-validated' mean?"**
- We fit the curve on 4/5 of the traces and predicted the other 1/5. We did
  that five times, so no trace ever helps fit its own prediction.
- The typical error per trace goes from 19% (Tobler) to 17% (refit).
- The point: much of the difference between hikes is the hiker and the
  trail, not the slope. Asako et al. (2024) model each hiker's walking
  ability for exactly this reason.

**"What did the winter hikes look like?"** *(only if asked)*
- A third of the moving time is in Dec–Mar.
- Winter hikers aren't slower; if anything they're a bit faster on gentle
  grades: v0 4.46 [4.08, 4.66] in winter vs 4.19 [3.91, 4.49] in Apr–Nov.
  Maybe packed snow covers the rocks.
- But it's only 31 traces, and three uploads are more than half the winter
  data. It's not a claim.
- Season does belong in the model, and `day_of_year` is already a column.

**"Did you read the papers?"** Answer honestly with whatever you've finished.
The ones most relevant this week:
- Newson & Krumm 2009 (HMM map-matching);
- STRIDE (Campbell et al. 2024);
- Campbell et al. 2022 (crowdsourced GPS travel rates).

---

## 5. Words you might hear

- **Map-matching (HMM):** snapping a wobbly GPS track onto the trail network.
  It picks the most likely *sequence* of trails, not just the nearest trail
  for each point. HMM = hidden Markov model.
- **Trace / upload:** one GPS file on OSM.
  - **Identifiable:** has a username and the original file.
  - **Trackable (anonymous):** has timestamps but no name.
- **Segment:** a 50 m piece of trail walked by one trace, with its speed and
  slope.
- **Moving time:** time with the stops removed.
- **Bootstrap (by trace):** redo the fit 200 times, each time on a random
  re-draw of whole traces. The middle 95% of the results is the interval.
- **DEM:** digital elevation model, a grid of ground heights. 5 m now, 1 m in
  T2.
- **`sac_scale`:** OSM's hiking-difficulty tag (hiking → mountain_hiking →
  demanding_mountain_hiking → …).
- **EPT:** Entwine Point Tiles, the format USGS uses for LiDAR point clouds on
  AWS, so you can read just the area you need.

---

## 6. Where everything is

- **One-pager:** `Meeting_Notes_v4.md`.
- **Plots:** `meeting_plots/oct9/`. `meeting_numbers.json` there has every
  number in these notes.
- **Dataset:** `travel-speed-gate1/data/t1_white_mountains/`, with its
  `data_card.md`.
- **Code:** `travel-speed-gate1/`: `t1_build_dataset.py`, `t1_variants.py`,
  `t1_meeting_figures.py`. The README has the run order.
- **Decisions:** `DECISIONS_LOG.md`; T1 is entries 28–47.
