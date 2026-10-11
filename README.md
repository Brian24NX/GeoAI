# Learning travel speed from remote sensing and GPS traces

**Brian Zhou** · WashU CSE 5999 (independent study, Fall 2026) · Mentors:
Danni Beaulieu, Tianyi Gao · Advisor: Prof. Nathan Jacobs (MVRL)
Target: **IGARSS 2027** (4 pages, deadline 11 Jan 2027)

GIS tools still predict hiking speed with Tobler's 1993 formula, fit to
textbook figures rather than real hikes. This project measures how people
actually move on trails, from thousands of OpenStreetMap GPS traces across
many US / Canadian mountain regions, and asks the remote-sensing question:
**can LiDAR and imagery stand in for the trail details (difficulty, surface)
that maps usually don't have?**

| Deliverable | What | Status |
|---|---|---|
| T1 | Trajectory dataset: cleaned, stop-filtered, map-matched OSM traces cut into 50 m segments with speed, signed slope, direction, travel mode, tags | 11 of 17 regions built (see `PROGRESS.md`) |
| T2 | Remote-sensing covariates per segment (1 m LiDAR terrain, vegetation structure, canopy, imagery) | next |
| T3 | Four-arm comparison: Tobler / OSM tags / remote sensing / both, on held-out hikes and regions | planned |
| T4 | Slope-speed curves and up/down asymmetry (out-and-back pairs) | first looks done |

## Where things are

| Path | What |
|---|---|
| `PROGRESS.md` | **Daily progress log** (what was done, numbers, decisions, next) |
| `DECISIONS_LOG.md` | Every analysis decision with its reason and status |
| `travel-speed-gate1/` | The pipeline (Python): download, build, analyses. Its `README.md` explains every script and the run order |
| `travel-speed-gate1/cluster/` | Scripts that run on the lab cluster (Slurm jobs, the lab-crawl index) |
| `travel-speed-gate1/results/` | Small summaries and figures (no per-trace data) |
| `meeting_plots/`, `Meeting_Notes_*.md`, `Meeting_Prep_*.md` | Weekly meeting material |
| `progress_report_1/` | Progress Report #1 (CVPR template, LaTeX) |

**Everything in the project folder is here** (code, documents, built
datasets, logs, results), except two folders: `travel-speed-gate1/cache/`
(12 GB of raw downloads: OSM API pages, elevation grids and lab extracts;
GitHub refuses files over 100 MB) and `.venv/` (the Python environment).
Copies of the caches are on the lab cluster at
`/engrfs/project/jacobsn/zhou.n/travel-speed/cache/`, and the scripts can
re-create them.

**Keep this repository private.** The built datasets carry OSM usernames
and GPS tracks, and some documents are personal or course material.
Before ever making it public, remove `travel-speed-gate1/data/`, the logs
and the personal documents.

## Running it

Python 3.12; packages in `travel-speed-gate1/requirements.txt` (and the
cluster env `/engrfs/project/jacobsn/zhou.n/envs/t1`). See
`travel-speed-gate1/README.md` → "T1 for many regions".

AI assistance: Claude (Anthropic) helped write and run the code and draft
the documents; Brian reviews the work and is responsible for it.
