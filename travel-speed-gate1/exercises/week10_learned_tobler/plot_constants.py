#!/usr/bin/env python3
"""
Week 11 plot (Brian's; set up by Claude, 26 Oct 2026): what the learned
Tobler model learned. For every segment, scored while its region was held
out (split loro), the seed-averaged constants from run_all.py against
steppiness: pitch_sd_5m, how much the grade jumps between the 5 m pitches
inside a 50 m segment (smooth trail ~0.015, rock steps and stairs ~0.17).

Left:  k_up and k_down, how fast speed falls going up / down from the peak
Right: the peak speed v0 = exp(a), km/h
Tobler uses k = 3.5 and v0 = 6 km/h on every trail.

Data:   ../../cache/t3_learned/loro.parquet (run_all.py) and
        ../../cache/exercise/t3_table.parquet
Run:    ../../../.venv/bin/python plot_constants.py
Writes: fig_constants.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
t = pd.read_parquet(ROOT / "cache" / "exercise" / "t3_table.parquet",
                    columns=["pitch_sd_5m"])
d = pd.read_parquet(ROOT / "cache" / "t3_learned" / "loro.parquet")

# Brian: three ___ blanks (answers in chat are fine too).
d["steppy"] = ___                    # BLANK 1: each segment's pitch_sd_5m (d.row = its row in t)
d["v0"] = ___                        # BLANK 2: the peak speed in km/h, from a_mean
d["bin"] = pd.qcut(d.steppy, ___, labels=False)   # BLANK 3: how many equal-count bins? (ten)
g = d.groupby("bin").agg(
    steppy=("steppy", "median"), n=("row", "size"),
    k_up=("k_up_mean", "median"), k_down=("k_down_mean", "median"),
    v0=("v0", "median"),
    v0_lo=("v0", lambda v: v.quantile(0.25)),
    v0_hi=("v0", lambda v: v.quantile(0.75)))
print(g.round(3).to_string())

x_label = "steppiness: SD of the 5 m pitches in a 50 m segment"
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.2))
a1.plot(g.steppy, g.k_up, "o-", color="#2a78d6", label="k going up")
a1.plot(g.steppy, g.k_down, "o-", color="#eb6834", label="k going down")
a1.axhline(3.5, color="#1c2321", ls="--", lw=1, label="Tobler: 3.5 both ways")
a1.set_xlabel(x_label)
a1.set_ylabel("k: how fast speed falls with grade")
a1.set_ylim(0, 4)
a1.legend(frameon=False, loc="lower left")
a2.fill_between(g.steppy, g.v0_lo, g.v0_hi, color="#9ec5f0", alpha=0.6, lw=0,
                label="middle half of segments")
a2.plot(g.steppy, g.v0, "o-", color="#2a78d6", label="learned peak speed (median)")
a2.axhline(6, color="#1c2321", ls="--", lw=1, label="Tobler: 6 km/h")
a2.set_xlabel(x_label)
a2.set_ylabel("peak speed v0 (km/h)")
a2.set_ylim(0, 6.5)
a2.legend(frameon=False, loc="lower left")
for ax in (a1, a2):
    ax.spines[["top", "right"]].set_visible(False)
fig.suptitle("What the learned Tobler model learned, in regions it never saw "
             "(17 regions, 3 seeds averaged)", fontsize=11)
fig.tight_layout()
fig.savefig(HERE / "fig_constants.png", dpi=200)
print("wrote fig_constants.png")

# Brian: one sentence for the Gate 2 write-up, with numbers from the table
# printed above: "Tobler's k = 3.5 is closer to ... on smooth trail and ...
# on steppy trail; the peak speed falls from ... to ... km/h."
