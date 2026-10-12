#!/usr/bin/env python3
"""
Small extracts of the T1 dataset that the paper figures need on the laptop
(the dataset itself stays on the cluster: it has user names).

  results/fig1_wm_segments.parquet  the White Mountains' walking segments
                                    (ends and speed only), for Fig. 1's
                                    inset (make_paper_figures.fig_map)

Input:  data/t1_all/segments_L50.parquet
Run (cluster, after t1_combine.py): python make_paper_data.py
"""

from pathlib import Path

import pandas as pd

SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("results")


def main():
    cols = ["lat0", "lon0", "lat1", "lon1", "speed_kmh"]
    s = pd.read_parquet(SEG, columns=["region", "analysis_walk", *cols])
    wm = s.loc[s.analysis_walk & (s.region == "wm"), cols].round(5)  # ~1 m
    wm.reset_index(drop=True).to_parquet(OUT / "fig1_wm_segments.parquet",
                                         index=False)
    print(f"wrote {OUT / 'fig1_wm_segments.parquet'}: {len(wm):,} segments")


if __name__ == "__main__":
    main()
