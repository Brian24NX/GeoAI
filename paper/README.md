# IGARSS 2027 paper (skeleton)

- `OUTLINE.md`: the plan (page budget, claims, Table 1, figure list).
- `main.tex` + `sections/*.tex`: the paper. **Every section is a draft by
  Claude, at Brian's request, to rewrite in your own words** (Data and
  Methods 13 Oct; Introduction, Results and Discussion 21 Oct), each
  marked with a red `[TODO: Draft by Claude ...]` note; so is the abstract
  (21 Oct). Claude also set up the template, the table and the figures. Disclose AI assistance as IGARSS and CSE 5999
  require.
- `refs.bib`: references, all checked against Crossref or arXiv (12 Oct).
  `RELATED_WORK.md`: what each paper did and how we differ (for the
  Introduction).
- `figures/`: drawn by `../travel-speed-gate1/make_paper_figures.py` from
  the harness results. The trail map, terrain curves and mode curves (not
  in the paper for now) are read from `../travel-speed-gate1/results/`.

Compile: `tectonic main.tex` (writes `main.pdf`).

The template is IEEEtran (conference), a stand-in until the official IGARSS
2027 author kit is posted (the portal opens 10 Nov 2026). The section files
move over unchanged. With every section drafted it fills exactly 4 pages,
references included (older IGARSS kits count references inside the 4
pages): Table I, the map, the speed-slope curve and one figure across both
columns (skill by model, each region held out). The hike-time figure and
the trail map became one sentence each and can come back; see the budget
note in `OUTLINE.md`.
