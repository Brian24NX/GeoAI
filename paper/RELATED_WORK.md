# Related work, checked (12 Oct 2026)

A cheat sheet for writing the Introduction: what each paper did, how it
was evaluated, and how we differ. Every entry is in `refs.bib` (key in
brackets), with details checked against Crossref or arXiv. Numbers in the
"what they did" column are from the papers' abstracts or main text.

## The closest prior work

| Paper | What they did | Evaluation | How we differ |
|---|---|---|---|
| **Wood et al. 2023**, PLOS ONE [`wood2023hiking`] | 7,636 Hikr.org and OSM GPS tracks (~88,000 km), England and Wales. A generalised linear model (log link) with walking slope, hill slope, OSM terrain type (paved, unpaved, off-road) and lidar obstruction (DSM − DTM over 10 cm). RMSE on 50 m sections 1.10 vs Tobler's 1.24 | 10-fold cross-validation; no held-out regions. For whole routes every model, theirs included, had 13.5–15.5% error | 17 North American regions, leave one region out; trail tags (sac_scale, surface, visibility) vs remote sensing head to head; predicted ranges scored with CRPS; whole hikes 13.6% → 9.6% with the hiker's own pace and terrain |
| **Huang et al. 2026**, Applied Geography [`huang2026modeling`] | 7,913 crowdsourced trajectories in Hong Kong, 16 factors (slope, altitude, road type, weather: temperature, humidity, precipitable water). Boosted trees (LightGBM) best; SHAP to read the effects | Random split, one city (test RMSE 0.220, R² 0.676) | Transfer to regions the model never saw; remote sensing vs map tags. **They have weather; we don't** (a limitation to state) |
| **Šerić et al. 2022**, JOSIS [`seric2022modeling`] | GPS trails from several trail maps, Kozjak range (Croatia). A latent walking speed ("walkability") from SVD, predicted from Sentinel-2 imagery | One range; the abstract describes no held-out area | Lidar-derived terrain and satellite embeddings over 17 regions, tested on held-out regions |
| **HikingTTE**, Asako et al. 2024, CIT [`asako2024hikingtte`] | Deep model of whole-hike arrival time (hikr.org) that uses the hiker's pace in the first part | Beats a taxi travel-time model adapted to hikes | Per 50 m segment, remote-sensing covariates, transfer tests. Our "personal pace" is the same idea, as a reference |

## Slope-speed functions

| Paper | Point to use |
|---|---|
| Tobler 1993 [`tobler1993`] | The baseline: v = 6 exp(−3.5 \|s + 0.05\|) km/h, still the default in GIS |
| Campbell et al. 2019, Applied Geography [`campbell2019crowdsourced`] | Strava data near Salt Lake City: Lorentz-shaped percentile curves; Tobler too fast and too peaked |
| Campbell et al. 2022, CEUS [`campbell2022variability`] | ~2,000 AllTrails hikes (Utah, California), 39 percentile curves. **Our published baseline** (median curve): ties our refit on average, −3.8% to +5.8% by region |
| Irmischer & Clarke 2018, CaGIS [`irmischer2018measuring`] | Field calibration of speed vs slope and land cover |
| Higgins 2021, Findings [`higgins2021hiking`] | Tobler calibrated to one person's tracks (Hong Kong): slower on flat ground, faster on steep stairs |
| Márquez-Pérez et al. 2017 [`marquezperez2017estimated`] | Measured trail times differ a lot from Naismith, Tobler and MIDE predictions |
| Pagneux et al. 2023, Applied Geography [`pagneux2023modelling`] | How trail speed models depend on slope-data (DEM) resolution. **Findings not read** (paywalled): read before citing. We found 1 m ≈ 5 m on trails |
| Goodwin et al. 2025, Acta Astronautica [`goodwin2025application`] | Hiking functions hold only at the sampling resolution they were fitted at. Supports our finding that sparse GPS traces read slow |

## Remote sensing and walking speed

| Paper | Point to use |
|---|---|
| STRIDE: Campbell, Cutler & Dennison 2024, Sci. Rep. [`campbell2024stride`] | Lidar slope, understory density [`campbell2018understory`] and ground roughness, from timed field walks on and off path. **Our lidar baseline**: published −16.8%; its roughness adds nothing on trails |
| Campbell et al. 2017, IJWF [`campbell2017lidar`] | The earlier lidar study (slope, vegetation density, roughness) for firefighter escape routes |
| Cutler et al. 2026, GIScience & RS [`cutler2026machine`] | Random forest with lidar slope, vegetation and roughness, off-trail transects. Off-trail; we are on-trail and multi-region |
| RasterNet [`hadzic2020rasternet`]; Workman & Jacobs 2020 [`workman2020dynamic`]; Workman & Hadzic 2024 [`workman2024probabilistic`] | The lab's work learning road speed from overhead imagery and lidar, the last one with predicted distributions. We bring the idea to trails and walking |
| AlphaEarth Foundations [`brown2025alphaearth`, `alphaearth2025`] | The satellite embeddings we test |

## The gap, in points (for paragraph 3)

- Every study above fits and tests in one country, city or range, with
  random or within-area splits. None asks whether a model works in a
  region it never saw.
- None compares remote sensing with the trail tags mappers already add
  (sac_scale, surface, visibility) head to head.
- None scores predicted ranges (calibration), only single predictions.
- Whole-route time barely improves in Wood et al. (13.5–15.5% for every
  model). We show the hiker's own pace is what moves it (13.6% → 10.0%),
  and terrain adds on top (9.6%).

## Checked but not cited

- "Beyond Tobler's Hiking Function": no verifiable record found. Don't cite.
