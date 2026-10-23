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
Most of the leftover variation is the person and the day, which no map can
see: about a quarter of what's left after slope is between hikes. Terrain
still beats refitting the slope curve on the held-out region's own hikers,
and against Tobler the error drops by about 13%.

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
