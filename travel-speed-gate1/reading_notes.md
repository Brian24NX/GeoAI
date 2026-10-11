# Week 1 reading notes — in plain English

These are the 4 papers the plan says to read in week 1, plus one new paper I
found that you should raise at the meeting. These notes help you get the main
idea fast. They don't replace reading — at least skim RasterNet, since it's
Prof. Jacobs' own paper and will likely come up.

## How they fit together

| Paper | Predicts | Uses | Gap our project fills |
|---|---|---|---|
| Tobler 1993 | walking speed | slope only | never tested on large real data |
| Campbell 2022 | walking speed + how much people vary | slope | no remote sensing, no map tags |
| HikingTTE 2024 | total hike time | GPS tracks + slope | no remote sensing |
| RasterNet 2020 | car speed on roads | LiDAR + aerial photos | cars, not hikers |
| Cutler 2026 ⭐ | off-trail walking speed | LiDAR slope, vegetation, roughness | off-trail only; no map-tag comparison |

Our project sits in the middle: **real GPS speeds + LiDAR + map tags, compared
head to head.**

---

## 1. Tobler (1993) — the formula we're testing

**One line:** a formula that predicts walking speed from slope. Everyone uses
it; nobody properly tested it.

**The formula:**
speed (km/h) = 6 × e^(−3.5 × |slope + 0.05|)

Slope here is "rise over run" (a 10% grade = 0.10), **not degrees**. Easy
mistake to make in code.

**Worked examples** (all checked):

| Terrain | Slope | Speed |
|---|---|---|
| Flat | 0 | 5.04 km/h |
| Gentle downhill (−2.86°) | −0.05 | **6.00 km/h (fastest)** |
| 10% uphill | +0.10 | 3.55 km/h |
| 20% downhill | −0.20 | 3.55 km/h |
| 30% uphill | +0.30 | 1.76 km/h |

Look at the 10% uphill and 20% downhill rows: **same speed.** That's the
asymmetry (Question 3). Tobler says you're fastest going slightly downhill,
and steep downhill slows you as much as a gentler uphill.

For other modes he just multiplies: × 3/5 for off-path, × 5/4 for horseback.
Question 4 tests whether that multiplying trick is right.

**Why it matters:** it's Arm 1 of the four-arm experiment — the baseline.

---

## 2. HikingTTE (Asako et al., 2024) — closest prior work

*Cybernetics and Information Technologies, 2024*

**One line:** deep learning that predicts how long a hike will take, adjusted
to each person's walking ability.

**What it does** (per the semester plan): an LSTM with attention, plus a
built-in slope–speed curve (a "modified Lorentz" function), personalized to
each hiker. It learns from GPS trajectories only.

**How we're different:** they use no remote sensing and no vegetation
information. We add LiDAR terrain and vegetation, and compare against map tags.

**Interesting link:** their built-in curve idea — keep a known formula inside a
learning model — is the same move our plan proposes with Tobler (section 9).

**Question you could ask:** "HikingTTE personalizes per hiker, but our plan
says most OSM hikers upload only one track. Do we compare against HikingTTE
directly, or just cite it?"

---

## 3. Campbell, Dennison & Thompson (2022) — the serious measurement work

*Computers, Environment and Urban Systems, vol. 97*

**One line:** people vary a lot in how fast they walk, so predict the whole
range, not just the average.

**What they did:** used close to 2,000 hikes from AllTrails in Utah and
California. Instead of predicting one speed per slope, they predicted a range
of percentiles (from slow walkers to fast walkers). Their typical-hiker model
beat existing slope formulas on new test data, and their predicted percentiles
landed within 10% of the real ones.

A nice trick from the paper: for each track, they took the median speed within
small slope windows (1° wide) to smooth out noise.

**Earlier work by the same group (2019):** used over 400,000 Strava activities
and found an uneven (asymmetric) Lorentz-shaped curve fit best — another hint
that uphill and downhill really are different.

**Why it matters for us:** this is why our plan predicts speed **and**
uncertainty (the "heteroscedastic head"). Knowing the spread matters.

**How we're different:** they model speed from slope. We add remote sensing
and map tags, and test travel mode.

---

## 4. RasterNet (Hadzic et al., 2020) — the lab's own method

*CVPR 2020 Workshops (EARTHVISION). Prof. Jacobs' lab, at the University of
Kentucky at the time. Acceptance rate 26%.*

**One line:** predict how fast cars drive on a road by looking at it from
above, with no hand-measured road data.

**The problem it solved:** traffic engineers normally estimate road speed from
measured features like grade, curve sharpness, and lane width. But for most
roads, nobody has measured those.

**What it does:** combines aerial photos and airborne LiDAR (3D laser scans)
on a shared grid so they line up, then a neural network predicts speed. They
built a new dataset covering Kentucky.

**Why it matters — this is the key connection:**

| | RasterNet | Our project |
|---|---|---|
| Who's moving | cars | hikers, bikes, horses |
| Missing info | measured road features | OSM trail tags |
| Fix | look from above | look from above |

Same idea, different traveler. The plan says RasterNet's way of lining up the
data is the model for our satellite/LiDAR layer (T2).

**Code:** the lab has a project page for it, but I couldn't confirm whether
the code is public. Ask tomorrow.

---

## ⭐ Bonus: Cutler, Campbell, Brewer & Dennison (2026) — raise this tomorrow

*GIScience & Remote Sensing, vol. 63. Not on the reading list — I found it
while checking the others. I've only read the summary, not the full paper.*

**One line:** machine learning predicts off-trail walking speed from LiDAR.

**What they did:** a random forest using airborne LiDAR measurements of slope,
vegetation density, and ground roughness. It explained about 78% of the
variation in walking speed on new test data. Slope mattered most, then
vegetation density, then roughness.

**Why this matters a lot:** it's close to our Question 2 — can LiDAR predict
speed? The plan says nobody has built "the thing in the middle." This paper
doesn't break that claim (it's off-trail, and doesn't compare against map
tags), but it's close enough that the paper must cite it and explain how
we're different.

**It also supports our plan:** it found vegetation density is the #2 factor.
Our plan bets that understory (vegetation) is what lets the remote-sensing arm
compete with map tags. This paper is evidence for that bet.

**Same research group as paper 3 above** (and #7 on the plan's full reading
list) — the plan already says Campbell is worth following.

**Question to ask:** "Have you seen this 2026 paper? It's off-trail, but it's
close to our Question 2. How should we position against it?"
