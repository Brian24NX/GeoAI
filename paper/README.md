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

The template is the official IGARSS 2026 LaTeX kit (8 Nov 2026;
`IGARSS2026LaTeXTemplate.zip` from 2026.ieeeigarss.org, a copy of its .tex
in `template_igarss2026/`): IEEEtran conference on A4, natbib with
IEEEtranN, the title in capitals, one block per author. The section files
did not change. The 2027 kit goes up with the submission portal on 10 Nov;
compare it with the 2026 copy then.

The 2026 paper kit allows 4 pages including figures and does not count
references. In this template the main text (Table I, the map, the
speed-slope curve and the two-column skill figure) ends in page 4's left
column; the references fill the rest of page 4 and part of page 5. So
about 0.4 page is free if the 2027 kit keeps the rule. The hike-time figure
and the trail map, cut to one sentence each when references counted, could
come back; see the budget note in `OUTLINE.md`.
