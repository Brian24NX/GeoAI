# Lab meeting, 23 Oct: likely questions and short answers

*Prepared by Claude for Brian. Every number is in `DECISIONS_LOG.md` or the
paper draft. Answer in one or two sentences, then stop.*

**"How much data is this, really?"**
1,992 hikes in 17 regions, cut into 290,640 segments of 50 m (14,532 km).
The hikes are the real sample size, not the segments, so every interval
resamples whole hikes, or whole regions for the unseen-region test.

**"How do you get a clean speed from GPS?"**
Each trace is cleaned, stops are removed (a point that is still within
10 m a minute later counts as stopped), and the trace is matched to the
trail map with a hidden Markov model (85–99% of points matched, by region).
Speed is measured per 50 m segment.

**"Why CRPS instead of RMSE?"**
We predict a distribution of speeds, and CRPS scores both the center and
the spread. Plain RMSE tells the same story: in unseen regions terrain cuts
error by 2–3% against the slope curve, tags by under 1%, and Tobler is 13%
worse.

**"2–3% sounds small."**
Speed is noisy: after slope, about a quarter of what's left differs between
hikes (who is hiking, the day) and the rest from one 50 m stretch to the
next. Nothing we tried does much better, and terrain is most of the best
model's gain. It even beats a slope curve refitted on the held-out
region's own other hikers (+1.2%), and against Tobler the error drops by
about 13%.

**"What exactly is 'terrain'?"**
The trail's elevation profile along each 50 m segment, read from lidar
elevation maps (1 m and 5 m): the steepest short pitch, rock steps, side
slope, and above all the hidden ups and downs that one average slope
hides. That hidden climbing alone carries over half of the gain.

**"Why don't tags carry over to a new region?"**
In regions the model knows, tags help (+1.3% / +1.5%, additive / trees);
in a new region the additive model keeps +0.9% and the trees +0.4%. It's
not that tags mean different things in different places: within the same
hike, harder difficulty grades are slower in every region with enough
tagged trail. Tags are patchy (1.5–96% of trail) and the trees seem to
learn region-specific tag combinations. Terrain exists on every trail.

**"Is terrain's lead over tags real or noise?"**
Real: resampling whole regions, terrain minus tags is +0.7 to +2.2 points
(95% interval), above zero in every draw.

**"Isn't terrain just telling the model which region it's in?"**
No. It adds about 1.9 points on top of a learned per-region offset, and it
holds when a whole zone, or half the continent, is held out.

**"Are the same hikers in training and test?"**
For the strictest test, we also remove everyone who hiked in the held-out
region from training. Terrain keeps +1.8 / +2.4%, tags drop to +0.5 /
−0.4%, and terrain stays ahead in every bootstrap draw.

**"Why didn't vegetation or satellite embeddings help?"**
They help inside a region but not across regions: they mostly encode which
place you're in. Lidar understory, even split into Campbell's three height
layers, adds about 0.2 points everywhere. 30 m land cover is too coarse.

**"Why not train a CNN on aerial imagery?"**
That's the week-12 plan: NAIP 1 m imagery with a frozen pretrained encoder
and a small head. With about 2,000 hikes, training an encoder from scratch
would overfit. (Good moment to ask which encoder they'd use.)

**"How does STRIDE do?"**
As published it scores −16.8%: its roughness and understory terms were
calibrated off-trail and over-penalize trails. Refitted to our hikes, it
ties the slope curve.

**"Who uploads to OpenStreetMap? Isn't that biased?"**
Yes: mappers and enthusiasts, not a random sample of hikers. It's stated as
a limit. The claim is about which inputs work better, and that comparison
holds for newer hikes and every GPS recording rate.

**"What can someone actually do with it?"**
Get a pace for any mapped trail where an elevation model exists. In the
White Mountains that's 3,369 km of trail, 77% of which nobody in our data
walked.

**"Will the data be released?"**
A de-identified copy exists (no user names); releasing it is waiting on
Danni's and Tianyi's decision.

## Cut from the slides (say only if someone asks)

The 23 Oct deck was simplified to one message per slide. These details
were on the earlier version:

- **Downhill vs uphill:** for the same hiker on the same trail, going down
  is 8% faster on gentle grades and about 23% on steep ones (2,763
  out-and-back pairs from 1,145 hikes). Tobler assumes 42% everywhere.
- **How much worse is Tobler?** 12.5% worse overall than a slope curve
  fitted to the other regions (CRPS). On climbs steeper than 25% it is
  actually about 18% too slow.
- **Tag coverage:** the difficulty tag (sac_scale) covers 1.5% (Green
  Mountains) to 96% (Adirondacks) of walked trail.
- **Additive vs trees:** in unseen regions terrain gains +2.1% (additive) /
  +2.8% (trees), tags +0.9% / +0.4%. Terrain beats tags in 16 of 17 regions
  with the additive model and 14 of 17 with trees.
- **Data size:** 14,532 km and 4,702 hours of walking.
- **The November check:** Gate 2 on 6 Nov asks whether Tobler with learned
  constants beats boosted trees on the same folds.
- **Which conference:** IGARSS 2027 (deadline 11 Jan) and its Student Paper
  Competition.
