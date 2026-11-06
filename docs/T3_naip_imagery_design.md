# T3, week 12: the NAIP aerial-imagery arm (plan)

*Drafted by Claude (26 Oct 2026) for Brian, following the semester plan §9
("a frozen pretrained encoder and a small head") and NEXT_STEPS §4's tier 3.
For the go/no-go at the Gate 2 meeting on 6 Nov. Nothing has been
downloaded; every number below was checked on 26 Oct.*

## The question

Does aerial imagery of the trail add to terrain **in regions the model never
saw**? Terrain is the only input that has transferred so far. The satellite
embeddings (AlphaEarth, decision #93) helped inside a region but mostly told
the model *which place* it was in, so imagery has to pass the same test.

**Success:** in the unseen-region setups (`loro`, `loro_hiker`), terrain +
imagery beats terrain alone, with the paired 95% interval above zero, for
learned Tobler or the trees. Otherwise imagery gets one sentence in the
paper, like the embeddings.

## What is available

- **NAIP on Microsoft Planetary Computer** covers all 16 US regions; North
  Shore (Canada) has none, so this arm runs on 16 regions and is compared
  with terrain on the same 16.
  - Latest year 2021–2023 everywhere: 0.6 m, except New Hampshire, Vermont
    and Colorado, whose 2023 flights are 0.3 m.
  - Four bands (red, green, blue, near infrared), leaf-on summer flights.
  - Cloud-optimized GeoTIFFs: one file per quarter quad (2 GB at 0.3 m),
    stored as 512-pixel tiles of about 1 MB with built-in lower-resolution
    copies, so we can read just the tiles along trails.
  - Free and no account: a short-lived access token comes from the
    Planetary Computer's token service.
- **Our trail spots** (computed on ENGR from `data/t1_all/segments_L50.parquet`):
  275,797 walking segments in the 16 US regions, at 173,444 unique 25 m spots,
  touching about 24,000 tiles of 307 m and about 805 quarter quads.
- **Clay v1.5 NAIP embeddings, already computed:** NAIP 2010–2021, one
  1024-number embedding per 256-pixel chip (154 m at 0.6 m), CC-BY 4.0, one
  parquet file per quarter quad on Source Cooperative (the same host we
  read AlphaEarth from). Files are 7–9 MB at 0.6 m, so our ~805 quads come
  to about 6.5 GB.
- **Encoders for chips centred on the trail:**

| Encoder | Trained on | Bands | Access and license |
|---|---|---|---|
| Satlas `Aerial_SwinB_SI` (Allen AI) | aerial imagery at 0.5–2 m, including NAIP | RGB | open; ODC-BY weights |
| DINOv3 ViT-L/16 SAT-493M (Meta) | 493 million Maxar chips at 0.6 m | RGB | gated on Hugging Face: Brian must log in and accept Meta's DINOv3 License himself |
| Clay v1.5 | many sensors, NAIP among them | RGB + NIR | the precomputed embeddings above |

Ruled out: 10–30 m models (Prithvi, SatMAE) are too coarse for a trail,
and location encoders (SatCLIP, GeoCLIP) break the held-out-region rule
(NEXT_STEPS §4).

## Two tracks

### A: Clay's precomputed embeddings (1–2 days, ~6.5 GB, no GPU)

1. On ENGR, list Clay's files for each region's quarter quads, keep the
   latest year up to 2021, and keep the chip that contains each segment's
   midpoint.
2. Shrink the 1024 numbers to 16 with PCA, fitted on each fold's training
   rows only.
3. Run the five Gate 2 setups for the trees (harness) and learned Tobler
   (`run_all.py`): imagery alone, and terrain + imagery. Report the paired
   gain over terrain.

The catch: a 154 m chip shows the landscape, not the trail, which is closer
to AlphaEarth than to what we want.

**Coverage, checked 5 Nov.** These checks only listed the bucket; nothing
was downloaded. Each region's map box was matched against Clay's quarter
quads, taking each tile's latest year up to 2021.
- Clay covers all 13 states we need, at 60 cm, in 2019–2021.
- Washington's 2021 set is incomplete:
  - the Cascades take 154 of their 300 box tiles from 2019;
  - the Gorge's Washington side is 2019.
- **Olympic exists only as 2017 at 1 m.** With 256-pixel chips that is
  256 m squares from coarser photos, not comparable with the other
  regions. So Track A runs on **15 regions**, and Olympic returns in
  Track B.

| Region | Clay files (state + year) | Box tiles found |
|---|---|---|
| White Mountains | NH 2021 (+ ME 2021, 1 tile NH 2018) | 197 / 204 |
| Adirondacks, Catskills | NY 2021 | 63 / 63, 70 / 70 |
| Green Mountains | VT 2021 | 56 / 56 |
| Shenandoah | VA 2021 | 129 / 130 |
| Smokies | TN 2021 + NC 2020 | 96 / 96 |
| Pisgah | NC 2020 | 80 / 80 |
| Front Range | CO 2021 | 110 / 110 |
| Wasatch | UT 2021 | 48 / 48 |
| Cascades | WA 2021 + WA 2019 | 300 / 300 |
| Gorge | OR 2020 + WA 2019 | 60 / 60 |
| Olympic | WA 2017 only, 1 m | 84 / 84 |
| Bay Area | CA 2020 | 116 / 144 (the rest is probably ocean and bay) |
| San Gabriels, Yosemite | CA 2020 | 60 / 60, 54 / 54 |
| Tahoe | CA 2020 + NV 2019 | 56 / 56 |

Box tiles are an upper bound: the whole boxes come to 1,327 files and
10.9 GB, while the trail tiles alone are about 805 files and 6.5 GB.

**File layout** (from Clay's README, `clay-v1-5-naip-2/README.md`, read
5 Nov):
- Each file is a parquet with two columns: `geometry` (the chip's outline)
  and `embeddings` (1,024 numbers, Clay v1.5's class token).
- Each NAIP tile is cut into 256 × 256-pixel chips.
- The folders mirror NAIP on AWS (`naip-analytic`, 2010–2021). License
  CC-BY 4.0.
- The geometry's coordinate system is checked on the first file Monday.
  Each segment's midpoint then takes the embedding of the chip that
  contains it.

Tile numbering was confirmed on Planetary Computer. In each 1° block,
quads 01–64 run from the north-west corner eastward, then south: m_4407146
is 44.25–44.375° N, 71.25–71.375° W.

**Track A result (6 Nov, decision #125).** Trees on 15 regions, terrain +
imagery minus terrain:
- new hikes +1.03 [+0.35, +1.71];
- new 10 km squares +0.65 [+0.13, +1.18];
- new hikers +0.55 [−0.38, +1.42];
- unseen regions +0.19 [−0.77, +1.19];
- unseen regions + hikers +0.37 [−0.79, +1.22].

Learned Tobler, unseen regions, its own spread: +0.44 [−0.67, +1.20].

So imagery helps inside known regions but not in new ones: the AlphaEarth
pattern. Track A does not pass. Details:
`travel-speed-gate1/exercises/week12_imagery/README.md`.

### B: chips centred on the trail + a frozen encoder (3–4 days, ~25–35 GB of reads, CPU)

1. **Chip:** 96 m × 96 m, north up, centred on each unique 25 m spot, at
   0.6 m (160 × 160 pixels); the 0.3 m states are read from their 0.6 m
   copy.
2. **Reads:** only the tiles the chips need, about 25,000–35,000 tiles of
   ~1 MB, streamed on ENGR. Chips are not kept, only their embeddings
   (173,444 × 1024 numbers in half precision, about 0.36 GB).
3. **Encoder:** frozen, the average of its patch outputs, then PCA to 16
   per fold, and the same runs as A.
4. **Compute:** CPU on ENGR (`engr-class-any`, 8 CPUs). Roughly 2 h for
   Satlas Swin-B and 7 h for DINOv3 ViT-L. The cluster needs PyTorch first,
   from offline wheels uploaded from the Mac (about 0.2 GB; the cluster
   cannot reach the Python package index).

**Brian's sanity check:** 20 random chips with the matched trail drawn on
top. Does each chip actually show the trail?

### Why A first

A is cheap and answers "does NAIP transfer at all?" in two days.
- If it transfers, B asks whether trail-centred chips add more.
- If it shows the AlphaEarth pattern (helps inside a region only), B is the
  real test of trail-level imagery: run it if time allows and the mentors
  want it.

## Schedule (week 12, 9–15 Nov)

| Day | Work | Who |
|---|---|---|
| Mon 9 Nov | Track A: read and join the embeddings on ENGR; sample chips for the sanity check | Claude; Brian checks the chips |
| Tue 10 Nov | Track A runs, five setups; the IGARSS submission site opens, so the paper moves to its template | Claude runs; Brian adds the columns to learned Tobler and re-runs it |
| Wed 11 Nov | Decide: stop (one sentence in the paper) or Track B | Brian, with Danni and Tianyi on Slack |
| Thu 12 – Fri 13 Nov | Track B if go; otherwise the template and the rewrite for week 13 | Claude and Brian |

Brian's plot for the week: imagery's gain over terrain, region by region,
in the unseen-region setup.

## Decisions for 6 Nov

1. Imagery in week 12: go or no-go.
2. Track A first? (recommended, on 15 regions: see the coverage check)
3. The encoder for Track B: Satlas (open), DINOv3 (gated; Brian accepts the
   license), or what the lab suggested at the 23 Oct meeting.
4. Downloads, all onto ENGR:
   - Track A: about 6.5 GB of Clay parquet from Source Cooperative.
   - Track B: about 25–35 GB of NAIP tile reads from Planetary Computer.
   - Track B: about 0.2 GB of PyTorch wheels for the cluster, plus the
     encoder weights (Swin-v2-Base or a ~300M-parameter ViT-L).

## Rules carried over

- No coordinates or location encoders as features.
- PCA and scaling are fitted on training rows only; inputs are clipped to
  the training rows' 0.1st–99.9th percentiles (decision #121).
- Same folds, scoring and intervals as Gate 2 (`run_all.py`,
  `gate2_summary.py`).
- The paper's numbers stay frozen (#113): imagery adds a row or a sentence.

## Sources (opened 26 Oct 2026)

- Planetary Computer NAIP: the STAC search API,
  `https://planetarycomputer.microsoft.com/api/stac/v1` (collection `naip`),
  queried for each region's bounding box; one New Hampshire file's header and
  size read directly.
- [Clay v1.5 NAIP embeddings](https://source.coop/clay/clay-v1-5-naip-2/);
  file sizes from the bucket listing.
- [Satlas pretrained models](https://github.com/allenai/satlaspretrain_models)
  and the [SatlasPretrain paper](https://arxiv.org/pdf/2211.15660).
- [DINOv3 ViT-L/16 SAT-493M model card](https://huggingface.co/facebook/dinov3-vitl16-pretrain-sat493m).
