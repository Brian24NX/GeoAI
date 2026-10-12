# IGARSS 2027 paper (skeleton)

- `OUTLINE.md`: the plan (page budget, claims, Table 1, figure list).
- `main.tex` + `sections/*.tex`: the paper skeleton. Red `[TODO: ...]` notes
  hold the points to make in each paragraph, with the final numbers (12 Oct).
  **The prose is yours to write.** Claude set up the template, the table and
  the figures. Disclose AI assistance as IGARSS and CSE 5999 require.
- `refs.bib`: references. Entries marked TODO need checking against the
  paper itself before citing (Wood et al. 2023, AlphaEarth).
- `figures/`: drawn by `../travel-speed-gate1/make_paper_figures.py` from
  the harness results. The trail map, terrain curves and mode curves are
  pulled in from `../travel-speed-gate1/results/`.

Compile: `tectonic main.tex` (writes `main.pdf`).

The template is IEEEtran (conference), a stand-in until the official IGARSS
2027 author kit is posted (the portal opens 10 Nov 2026). The section files
move over unchanged. With only the TODO notes it already runs to 4 pages,
so the final version keeps 3–4 of the 6 figures. Decide which with the
mentors.
