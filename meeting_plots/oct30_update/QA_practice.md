# Friday 30 Oct: practice questions on learned Tobler

*Prepared with Claude (29 Oct 2026). Every number is in
`LearnedTobler_setup.pdf`, `Gate2_writeup.pdf` or `DECISIONS_LOG.md`
(#120–#122). Answer out loud first, then check.*

## The model

**1. In one sentence, what is learned Tobler?**
Tobler's speed-vs-slope curve, where a small neural network sets the
curve's numbers for each 50 m segment from its terrain: the peak speed, how
fast speed drops uphill and downhill, where the peak sits, and how
uncertain the prediction is.

**2. What does the network see? Does it see slope?**
Only terrain: 12 measures of the segment's path from the 1 m and 5 m
elevation models, plus 7 missing-value flags. Slope goes in through
Tobler's formula, not the network, so every prediction is still a
Tobler-shaped curve.

**3. Why not a plain neural network that predicts speed directly?**
The output stays readable: we can say what k and the peak speed are on
smooth vs steppy trail. The curve shape is also a strong prior with only
~2,000 hikes, and softplus keeps k positive, so speed always falls away
from the peak. It still ties the boosted trees.

**4. How big is the network?**
19 inputs → 32 → 32 → 5, SiLU activations: 1,861 weights. Small on
purpose, because we have about 2,000 hikes.

## Training

**5. Why a Student-t likelihood instead of a normal one?**
GPS glitches and missed stops give heavy tails. With ν = 5 (fixed, not
tuned), a few wild speeds can't drag the fit.

**6. Why does it start from the slope curve?**
The output layer starts at zero with the reference constants as biases, so
the untrained model is exactly the refitted slope curve (to 3 × 10⁻⁷).
Training only learns departures from it, so any gain is a real gain over
slope alone, and training is stable.

**7. How do you avoid overfitting and leakage?**
In each fold the training hikes are split by hike, 70/15/15: fit (learn),
stop (early stopping) and cal (spread for scoring). Test hikes are never
touched. Clipping and scaling are fitted on training rows only, and there
are no coordinates or region IDs among the inputs.

## Evaluation and results

**8. What is CRPS skill, and why not RMSE?**
CRPS scores the whole predicted distribution, centre and spread. Skill is
the percentage improvement over the refitted slope curve. For the harness
models, RMSE tells the same story.

**9. What are the (a) and (b) scores?**
(a) uses the same spread rule as every model in Table I (residual quantiles
on the calibration hikes), so it compares the centres fairly. (b) uses the
model's own Student-t spread.

**10. Is it really better than the trees?**
- (a), same spread rule: a tie in all five setups (−0.12 to +0.22 points;
  every interval spans zero).
- (b), its own spread: ahead by +0.55 to +0.66 points on new hikes, new
  10 km squares and unseen regions, intervals above zero.
- Caveat: the trees had no learned spread here. When we gave them one before
  (decision #98), it didn't help.

**11. Is its uncertainty calibrated?**
Yes. Its 90% ranges hold 89.4–89.9% of test segments in every setup. The
North Shore is lower (about 82%), as it is for every model.

**12. What did it learn?**
k stays between about 1.9 and 2.7, never Tobler's 3.5. The peak speed falls
from 4.5 to 3.6 km/h from smooth to steppy trail. Going down smooth trail
is easy (k down 1.9), while steppy trail slows descents too.

## Problems and next steps

**13. Did anything break?**
A few elevation glitches at cliff edges and stairways (hidden climbing up
to 524 SDs out) made the network predict absurd values. Clipping the inputs
to the 0.1st–99.9th percentiles fixed it. The trees and the paper's binned
models were not affected.

**14. How stable is it across seeds?**
With three seeds, the score moves by at most 0.24 points within a setup.
The learned k values shift by about 0.1, so the plots average the seeds.

**15. What's next?**
Gate 2 on 6 Nov. Week 12: NAIP imagery, starting with Clay's precomputed
embeddings. Week 13: the full draft in my own words.
