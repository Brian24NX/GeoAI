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
4. **Your one plot: the week-9 log-linear diagnostic**
   (`travel-speed-gate1/exercises/week09_loglinear/README.md`, ~1 hour):
   the plan's test of whether Tobler's form is a straight line in log space.

## 3. What changed since 16 Oct (one line each)

- **Lidar understory, White Mountains** (you approved the download): inside
  the same hike, the densest-understory fifth of trail is 7.5% slower. With
  terrain, predictions in new 10 km squares improve from +3.6% to +5.0%.
- **Lidar understory, 15 regions** (72 GB, kept on the ENGR cluster): pooled
  over the 15 regions it adds only about +0.2 points on top of terrain,
  inside or outside the regions it trained on (the bigger gain was in the
  White Mountains alone). So of everything we tried (tags, 30 m vegetation,
  satellite embeddings, lidar vegetation, weather, season), **terrain is the
  only input with a large gain that holds in new regions**.
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
- **Unseen regions with unseen hikers** (#116): 47 people hiked in several
  regions, so the headline test could keep a held-out region's hikers in
  training. Holding out whole hikers changes almost nothing; leaving out a
  region together with everyone who hiked there lowers every model a
  little, tags most (terrain +1.8 / +2.4, tags +0.5 / −0.4), and terrain
  still beats tags in every draw. The paper now claims both.
- **Independent check of the draft** (#115; a fresh Claude reviewer, then
  every point re-verified): "new hikers" is now "new hikes" (that split
  holds out outings, so a hiker's other outings can be in training); "tags
  do not transfer" is now "transfer less well" (the additive tag model keeps
  two thirds of its gain in new regions; the trees lose most); terrain beats
  tags in 16 of 17 regions with the additive models, 14 of 17 with trees;
  Eq. (1)'s coefficients are now printed; a few smaller numbers fixed. The
  travel-mode result was cut for space (kept as a comment).

## 4. Questions to walk out with answers to

1. **Authors:** who is on the paper, and in what order?
2. **Student Paper Competition:** can we enter? Only full 4-page papers are
   eligible, and its deadline is the paper deadline (11 Jan). In past years
   it needed the advisor's attestation, so ask whether Danni or you should
   raise it with Prof. Jacobs. Also ask about **travel support** for
   students (application deadline also 11 Jan).
3. **Data release:** may we release the de-identified segments (no user
   names; decision #100)? The Conclusion has a placeholder sentence for it.
4. **Theme:** the 2027 list has SP.6 (Datasets, Benchmarks, and Evaluation
   Methodologies for Earth Observation), SP.5 (Foundation Models and
   Embeddings for EO) and L.7 (Land Surveying, Geodesy and Topography); none
   is about human mobility. Our pick: SP.6, since the transfer test is the
   contribution.
5. **Title:** it says "Lidar Terrain", but 1 m lidar adds little over the
   5 m grid, which is itself mostly resampled lidar. Keep it, or say
   "Elevation"?
6. **Freezing the numbers (#113):** are they OK with no dataset rebuild
   before the paper?
7. **Review timeline:** when can they each read it, and when should it go to
   Prof. Jacobs?

**IGARSS 2027 dates** (call for papers, checked 21 Oct): portal opens
10 Nov; papers, Student Paper Competition and travel support all due
11 Jan; decisions 12 Mar; final paper and registration 30 Apr; conference
11–16 Jul, Reykjavík. Whether references count toward the 4 pages comes
with the paper kit on 10 Nov.

## 5. What a reviewer will push on, and our answer

| They'll say | We say |
|---|---|
| "2–3% is a small gain." | Much of the spread in speed is the hiker and the day, which no map can see (26% of what's left after slope is between outings). Terrain still beats a slope curve refitted on the held-out region's own hikers (+1.2%), and its CRPS is 13% lower than Tobler's. |
| "Terrain is just telling the model which region it's in." | No: it adds ~1.9 points on top of a learned offset per region, and it holds with a whole zone, or half the continent, held out. |
| "The same hikers are in training and test." | We also hold out everyone who hiked in the test region: terrain +1.8% / +2.4%, tags +0.5% / −0.4%, terrain still ahead in every draw. |
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
> 16 of 17 regions. Lidar vegetation adds little, and satellite embeddings
> help mostly inside a region.
>
> Could we use Friday's meeting for a few decisions: the author list, the
> Student Paper Competition (it needs Prof. Jacobs' attestation), whether
> to release the de-identified data, and the theme and title? Any comments
> on the framing are very welcome.
>
> Thanks,
> Brian

## 7. The plan from here (re-paced to the semester plan, decision #117)

Draft 0 is a safety net; the remaining weeks follow the plan's schedule,
with Brian doing more of the hands-on work. Ask Danni and Tianyi whether
they agree with the two new pieces (weeks 10–12).

| Plan week | Dates | What |
|---|---|---|
| 9 | now | Log-linear diagnostic (Brian); draft 0 to mentors; stop-check sheet |
| 10–11 | 26 Oct–8 Nov | T3: Tobler with learned constants + a variance head, built by Brian in PyTorch (`docs/T3_learned_tobler_design.md`); **Gate 2** on 6 Nov |
| 12 | 9–15 Nov | NAIP imagery arm if time; move to the IGARSS template (portal 10 Nov) |
| 13 | 16–22 Nov | **Full draft**: Brian's rewritten version with the new results |
| 14 | 23–29 Nov | Polish, figures, per-hiker effects if they fit |
| 15–16 | 30 Nov–13 Dec | Mentor + Prof. Jacobs review; CSE 5999 final report |
| break | by ~8 Jan | Submit (deadline 11 Jan) with the competition attestation |
