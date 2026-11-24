#!/usr/bin/env python3
"""
Table I of the IGARSS paper (paper/sections/results.tex, tab:skill), read
from the harness results instead of typed by hand (Claude, 24 Nov 2026).
CRPS skill (%) vs the refitted slope curve, all walking segments, for new
hikes (outing5), new 10 km squares (block5) and unseen regions (loro).

  row                      folder (results/...)            arms
  Tobler 1993              t3_harness_terrain15m           tobler
  Campbell 2022            t3_harness_terrain15m           campbell
  STRIDE 2024              t3_harness_terrain15m           stride (stride_refit)
  OSM tags                 t3_harness_terrain15m           lin_tags / gbm_tags
  30 m vegetation          t3_harness_landcover            lin_rs / gbm_rs
  Embeddings               t3_harness_aef                  lin_rs / gbm_rs
  Lidar vegetation         t3_harness_veg15_lidarveg       lin_rs / gbm_rs
  Terrain                  t3_harness_terrain15m           lin_rs / gbm_rs
  Terrain + emb. + tags    t3_harness_aef_terrain          lin_both / gbm_both
  Eq. (1), one input       t3_harness_terrain15m           terrain_curve
  Learned Tobler           t3_learned_tobler/gate2_summary learned_a (learned_b)

Run:  ../.venv/bin/python make_paper_table.py [results_dir]
      prints the rows as LaTeX and writes results_dir/paper_table1.csv
"""
import sys
from pathlib import Path

import pandas as pd

SPLITS = ["outing5", "block5", "loro"]
ROWS = [("Tobler 1993", "t3_harness_terrain15m", "tobler", None, "single"),
        ("Campbell 2022", "t3_harness_terrain15m", "campbell", None, "single"),
        ("STRIDE 2024", "t3_harness_terrain15m", "stride", "stride_refit",
         "paren"),
        ("OSM tags", "t3_harness_terrain15m", "lin_tags", "gbm_tags", "pair"),
        ("30 m vegetation", "t3_harness_landcover", "lin_rs", "gbm_rs",
         "pair"),
        ("Embeddings", "t3_harness_aef", "lin_rs", "gbm_rs", "pair"),
        ("Lidar vegetation", "t3_harness_veg15_lidarveg", "lin_rs", "gbm_rs",
         "pair"),
        ("Terrain", "t3_harness_terrain15m", "lin_rs", "gbm_rs", "pair"),
        ("Terrain + emb. + tags", "t3_harness_aef_terrain", "lin_both",
         "gbm_both", "pair"),
        ("Eq. (1), one input", "t3_harness_terrain15m", "terrain_curve", None,
         "single")]


def skill(res, folder, arm, split):
    m = pd.read_csv(res / folder / "metrics.csv")
    r = m[(m.split == split) & (m.arm == arm) & (m.subset == "all")]
    return float(r.crps_skill_vs_slope_pct.iloc[0]) if len(r) else None


def f(x):
    return "n/a" if x is None else f"${x:+.1f}$".replace("+-", "-")


def main():
    res = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path(__file__).resolve().parent / "results")
    out, tex = [], []
    for name, folder, a, b, kind in ROWS:
        cells = []
        for s in SPLITS:
            x = skill(res, folder, a, s)
            y = skill(res, folder, b, s) if b else None
            out.append(dict(row=name, split=s, first=x, second=y))
            cells.append(f(x) if kind == "single" else
                         f"{f(x)} ({f(y)})" if kind == "paren" else
                         f"{f(x)} / {f(y)}")
        tex.append(f"{name} & " + " & ".join(cells) + r" \\")
    g = res / "t3_learned_tobler" / "gate2_summary.csv"
    if g.exists():
        s = pd.read_csv(g).set_index("split")
        cells = []
        for sp in SPLITS:
            x, y = float(s.loc[sp, "learned_a"]), float(s.loc[sp, "learned_b"])
            out.append(dict(row="Learned Tobler", split=sp, first=x,
                            second=y))
            cells.append(f"{f(x)} ({f(y)})")
        tex.append("Learned Tobler & " + " & ".join(cells) + r" \\")
    pd.DataFrame(out).to_csv(res / "paper_table1.csv", index=False)
    print("\n".join(tex))


if __name__ == "__main__":
    main()
