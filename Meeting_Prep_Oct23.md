# Meeting prep: weekly sync with Danni & Tianyi, Fri 23 Oct 2026

*Prepared by Claude (21 Oct). Plain-English brief; all numbers are in
`DECISIONS_LOG.md` (#109–114) and `paper/main.pdf`.*

## 1. If you only read one thing

- **We have a complete 4-page draft** (`paper/main.pdf`, references
  included). Every section is a first pass written by Claude at your
  request, marked in red for you to rewrite. The numbers are final.
- **Gate 2 is answered early** (the plan had it ~13 Nov: "does remote
  sensing get close to the tags?"). It does better than close: terrain from
  elevation data beats the OSM tags in 16 of 17 regions the model never saw.
- **We are ~5 weeks ahead of the plan** (full draft was due 27 Nov), so the
  best use of the time is getting Danni's, Tianyi's and Prof. Jacobs'
  comments now, not in December.

## 2. Before the meeting (you do these)

1. **Send the draft** to Danni and Tianyi, ideally a day ahead. A draft
   email is in section 6; edit it freely.
2. **Check Canvas** for the CSE 5999 deadlines (progress updates, final
   report and its format). We still don't know them.
3. **Fill in the stop-check sheet** (`stop_check/stop_check.html`, ~15 min).
   It now only checks the stop rule; the agreement rate goes in the paper.

## 3. What changed since 16 Oct (one line each)

- **Lidar understory, White Mountains** (you approved the download): inside
  the same hike, the densest-understory fifth of trail is 7.5% slower. With
  terrain, predictions in new 10 km squares improve from +3.6% to +5.0%.
- **Lidar understory, 15 regions** (72 GB, kept on the ENGR cluster): it does
  **not** carry over to new regions (+0.2 points over terrain, not
  significant; helps in 9 of 15). So of everything we tried (tags, 30 m
  vegetation, satellite embeddings, lidar vegetation, weather, season),
  **only terrain transfers reliably**.
- **STRIDE's understory term** (a published lidar model) makes it much worse
  on trails (−18% → −35%): it was calibrated off-trail.
- **Distance along the trail** instead of straight lines between GPS points
  fixes the corner cutting of sparse traces and would raise all speeds by
  ~1–3%. **Decision #113:** keep the paper on the current dataset and state
  this as a limit; a corrected dataset can come with a data release later.
- **Check #114:** only 2 of 1,992 walking outings cross from one region into
  the next. Too few to matter.
- **Paper layout:** the skill chart and the per-region chart became one
  figure; the hike-time chart and the trail map became one sentence each.

## 4. Questions to walk out with answers to

1. **Authors:** who is on the paper, and in what order?
2. **Student Paper Competition:** can we enter? It needs Prof. Jacobs'
   attestation, so ask whether Danni or you should raise it with him.
3. **Data release:** may we release the de-identified segments (no user
   names; decision #100)? The Conclusion has a placeholder sentence for it.
4. **Theme:** SP.6 (datasets, benchmarks, evaluation) or SP.5 (foundation
   models and embeddings)? Our pick: SP.6, since the transfer test is the
   contribution.
5. **Title:** it says "Lidar Terrain", but 1 m lidar adds little over the
   5 m grid, which is itself mostly resampled lidar. Keep it, or say
   "Elevation"?
6. **Freezing the numbers (#113):** are they OK with no dataset rebuild
   before the paper?
7. **Review timeline:** when can they each read it, and when should it go to
   Prof. Jacobs?

## 5. What a reviewer will push on, and our answer

| They'll say | We say |
|---|---|
| "2–3% is a small gain." | Much of the spread in speed is the hiker and the day, which no map can see (26% of what's left after slope is between outings). Terrain still beats a slope curve refitted on the held-out region's own hikers (+1.2%), and its CRPS is 13% lower than Tobler's. |
| "Terrain is just telling the model which region it's in." | No: it adds ~1.9 points on top of a learned offset per region, and it holds with a whole zone, or half the continent, held out. |
| "Do you even need lidar?" | The 5 m grid works as well as 1 m lidar, and most 5 m grids are resampled lidar. This is the title question above. |
| "OSM uploaders aren't typical hikers." | Agreed, it's in the limits. The comparison between models is what we claim, and it holds for newer hikes and every GPS recording rate. |
| "Sparse GPS traces read slow." | Yes, a measurement effect we explain (Data section); the gains are the same at every recording rate. |

## 6. Draft email (you send it; edit as you like)

> **Subject:** Full draft of the IGARSS paper (4 pages)
>
> Hi Danni and Tianyi,
>
> Attached is a complete first draft of the IGARSS 2027 paper, 4 pages
> including references. The prose is a first pass written with Claude's
> help (marked in red); I'm rewriting it in my own words over the next two
> weeks. The numbers are final on the current dataset.
>
> The main result held up: terrain from elevation data improves predictions
> in regions the model never saw (+2.1 to +2.8%) and beats the OSM tags in
> 16 of 17 regions. Lidar vegetation and satellite embeddings help only
> inside a region.
>
> Could we use Friday's meeting for a few decisions: the author list, the
> Student Paper Competition (it needs Prof. Jacobs' attestation), whether
> to release the de-identified data, and the theme and title? Any comments
> on the framing are very welcome.
>
> Thanks,
> Brian

## 7. The plan from here

| When | Who | What |
|---|---|---|
| This week | Brian | Send the draft; stop-check sheet; start rewriting (Introduction and Discussion first) |
| 26 Oct–6 Nov | Brian | Rewrite Results, Data, Methods, then the abstract; fold in mentor comments |
| 26 Oct–6 Nov | Claude | Run any check the mentors ask for; prepare a public code-only repo if they want a release |
| 10 Nov | Claude | Portal opens: move the paper into the official IGARSS 2027 template; confirm the page rule |
| ~13 Nov | Brian | Rewritten draft to Prof. Jacobs |
| Dec | Both | Review rounds; CSE 5999 final report (format per Canvas) |
| by ~8 Jan | Brian | Submit (deadline 11 Jan) with the competition attestation |
