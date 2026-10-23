// Lab-meeting deck, 23 Oct 2026 (MVRL, Prof. Jacobs): a 5 min talk and 4 min of
// questions, on Dan's outline (problem, prior work, goal, what's done, next steps,
// visuals). One message per slide; the details live in the speaker notes and in
// QA_prep.md.
// Run:  node build_deck.js   (after ../../.venv/bin/python make_assets.py)
// Writes Zhou_LabMeeting_23Oct.pptx next to this file.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(path.join(
  "/Users/brian/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/aa9118d1-e698-4429-a4ef-0631f61817fb/5a1927db-0a59-4145-b0c1-b60ec2055cb8/skills/pptx",
  "scripts", "apply_theme.js"));

const HERE = __dirname;
const ASSET = (f) => path.join(HERE, "assets", f);
const aspect = (f) => { const b = fs.readFileSync(f); return b.readUInt32BE(16) / b.readUInt32BE(20); };
const OUT = path.join(HERE, "Zhou_LabMeeting_23Oct.pptx");
const data = JSON.parse(fs.readFileSync(ASSET("data.json"), "utf8"));

// Pine and granite from the White Mountains; blue = terrain and orange = tags,
// the same two colors the paper's figures use.
const THEME = {
  name: "Trail Lidar",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1C2321", lt1: "FFFFFF", dk2: "1E3A2F", lt2: "EEF2EF",
    accent1: "2A78D6", accent2: "EB6834", accent3: "5E8C75",
    accent4: "6E7D76", accent5: "C9D8CF", accent6: "E2A53B",
    hlink: "2A78D6", folHlink: "5E8C75",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                       // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Does Remote Sensing Beat the Trail Map?";
pres.author = "Brian Zhou";
pres.company = "Washington University in St. Louis";
const C = pres.SchemeColor;
const SH = pres.ShapeType;
const HEAD = "+mj-lt";                             // theme heading font
const W = 13.333, M = 0.6, CW = W - 2 * M;         // slide width, margin, content width
const FOOT = "Brian Zhou  ·  MVRL lab meeting  ·  23 Oct 2026";

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.95, w: 9.8, h: 1.75,
      fontFace: HEAD, fontSize: 44, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 },
      text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.85, w: 9.8, h: 0.65,
      fontSize: 22, color: C.accent5, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: CW, h: 0.85,
      fontFace: HEAD, fontSize: 34, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 },
      text: "" } },
    { text: { text: FOOT, options: { x: M, y: 7.02, w: 8, h: 0.3, fontSize: 10,
      color: C.accent4, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.5, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: C.accent4,
    align: "right" },
});
pres.defineSlideMaster({
  title: "CLOSING_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: CW, h: 0.85,
      fontFace: HEAD, fontSize: 34, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 },
      text: "" } },
    { text: { text: FOOT, options: { x: M, y: 7.02, w: 8, h: 0.3, fontSize: 10,
      color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.5, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5,
    align: "right" },
});

// ---------------------------------------------------------------- helpers
const box = (slide, name, x, y, w, h, color, opts = {}) =>
  slide.addShape(SH.roundRect, { x, y, w, h, rectRadius: 0.1, fill: { color, ...(opts.fill || {}) },
    line: { type: "none" }, objectName: name });
const text = (slide, name, runs, x, y, w, h, opts = {}) =>
  slide.addText(runs, { x, y, w, h, isTextBox: true, margin: 0, valign: "top",
    objectName: name, ...opts });
const contours = (slide, transparency) =>
  slide.addImage({ path: ASSET("contours.png"), x: 0, y: 0, w: W, h: 7.5, transparency,
    objectName: "Contours, Mt Washington" });
// a big number with a label under it (and an optional comparison line)
function stat(slide, name, x, y, w, value, color, label, compare, size = 40, unit = "") {
  const runs0 = [{ text: value, options: { fontFace: HEAD, fontSize: size, bold: true, color } }];
  if (unit) runs0.push({ text: unit, options: { fontFace: HEAD, fontSize: Math.round(size * 0.55),
    bold: true, color } });
  text(slide, `${name} value`, runs0, x, y, w, size / 72 + 0.2);
  const ly = y + size / 72 + 0.2;
  const runs = [{ text: label, options: { fontSize: 15, color: C.text1,
    breakLine: Boolean(compare) } }];
  if (compare) runs.push({ text: compare, options: { fontSize: 14, color: C.accent4, italic: true } });
  text(slide, `${name} label`, runs, x, ly, w, compare ? 0.85 : 0.75);
}

// ---------------------------------------------------------------- 1 title
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
contours(s, 55);
text(s, "Kicker", [{ text: "MVRL LAB MEETING  ·  23 OCT 2026", options: { fontSize: 14, bold: true,
  color: C.accent5, charSpacing: 2 } }], 0.8, 1.45, 9.8, 0.35);
s.addText("Does Remote Sensing Beat the Trail Map?", { placeholder: "title" });
s.addText("Predicting hiking speed in regions a model has never seen", { placeholder: "body" });
text(s, "Author", [
  { text: "Brian Zhou", options: { fontSize: 18, bold: true, color: C.background1, breakLine: true } },
  { text: "CSE 5999 independent study  ·  Mentors Danni Beaulieu and Tianyi Gao  ·  Advisor Prof. Nathan Jacobs",
    options: { fontSize: 14, color: C.accent5 } },
], 0.8, 4.85, 11.5, 0.8);
text(s, "Credits", [{ text: "Background: lidar contours of Mt Washington, NH (USGS 3DEP).  Slides made with help from Claude (Anthropic).",
  options: { fontSize: 10, color: C.accent5 } }], 0.8, 6.75, 11.7, 0.35);
s.addNotes("Hi, I'm Brian. With Danni and Tianyi I'm studying how fast people hike, and whether lidar and other remote sensing can predict it better than the trail map. In five minutes: the problem, the data, two results, and what's next.");

// ---------------------------------------------------------------- 2 problem
pres.addSection({ title: "Problem and goal" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and goal" });
s.addText("GIS still times hikes with a 1993 formula", { placeholder: "title" });
box(s, "Formula card", M, 1.5, 6.2, 2.15, C.background2);
text(s, "Formula label", [{ text: "TOBLER'S HIKING FUNCTION (1993)", options: { fontSize: 12, bold: true,
  color: C.accent3, charSpacing: 1.5 } }], M + 0.3, 1.7, 5.6, 0.3);
text(s, "Formula", [
  { text: "v = 6 e", options: { fontFace: HEAD, fontSize: 32, color: C.text1 } },
  { text: "−3.5 |s + 0.05|", options: { fontFace: HEAD, fontSize: 32, color: C.text1, superscript: true } },
  { text: "   km/h", options: { fontSize: 18, color: C.accent4 } },
], M + 0.3, 2.05, 5.6, 0.85, { valign: "middle" });
text(s, "Formula how to read", [{ text: "s = slope.  Fastest, 6 km/h, on a gentle downhill.",
  options: { fontSize: 16, color: C.accent4 } }], M + 0.3, 3.0, 5.6, 0.4);
[["Fit to a textbook table", "not to real hikes"],
  ["Slope is its only input", "rocks, roots and brush are ignored"]].forEach(([label, detail], i) => {
  const y = 4.1 + i * 1.2;
  s.addShape(SH.ellipse, { x: M + 0.02, y: y + 0.12, w: 0.2, h: 0.2, fill: { color: C.text2 },
    line: { type: "none" }, objectName: `Problem marker ${i + 1}` });
  text(s, `Problem ${i + 1}`, [
    { text: label, options: { fontSize: 20, bold: true, color: C.text2, breakLine: true } },
    { text: detail, options: { fontSize: 16, color: C.accent4 } },
  ], M + 0.45, y, 5.75, 0.9);
});
const tagged = data.coverage;                       // sorted, least tagged first
const most = tagged[tagged.length - 1], least = tagged[0];
const full = (r) => r.replace("Mtns", "Mountains");
const rx = 7.3, rw = W - M - rx;
box(s, "Tag card", rx, 1.5, rw, 4.8, C.background2);
text(s, "Tag card label", [{ text: "CAN THE TRAIL MAP HELP?", options: { fontSize: 12, bold: true,
  color: C.accent3, charSpacing: 1.5 } }], rx + 0.35, 1.7, rw - 0.7, 0.3);
text(s, "Tag card lead", [{ text: "Share of walked trail with OpenStreetMap's difficulty tag:",
  options: { fontSize: 16, color: C.text1 } }], rx + 0.35, 2.05, rw - 0.7, 0.6);
stat(s, "Most tagged", rx + 0.35, 2.7, rw - 0.7, `${Math.round(most.pct)}%`, C.accent2,
  full(most.region), null, 54);
stat(s, "Least tagged", rx + 0.35, 4.05, rw - 0.7, `${least.pct}%`, C.accent2,
  full(least.region), null, 54);
text(s, "Tag card takeaway", [{ text: "Often the map can't say how hard a trail is.",
  options: { fontSize: 16, bold: true, color: C.text2 } }], rx + 0.35, 5.5, rw - 0.7, 0.6);
s.addNotes(`Software that estimates hiking time, like GIS travel-time tools, mostly still uses Tobler's formula from 1993. Speed depends only on slope: fastest, about 6 km/h, on a gentle downhill. Two problems: it was fit to a textbook table, not to real hikes, and slope is its only input. Could the trail map fill the gap? OpenStreetMap has a difficulty tag, but it covers ${Math.round(most.pct)}% of walked trail in the ${full(most.region)} and only ${least.pct}% in the ${full(least.region)}. (If asked: the tag is sac_scale, the Swiss Alpine Club's grade; flat ground is 5 km/h in Tobler, a 20% climb 2.5 km/h.)`);

// ---------------------------------------------------------------- 3 prior work + goal
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and goal" });
s.addText("Goal: predict speed in regions the model never saw", { placeholder: "title" });
text(s, "Prior label", [{ text: "WHAT'S BEEN DONE", options: { fontSize: 12, bold: true,
  color: C.accent3, charSpacing: 1.5 } }], M, 1.6, 5.2, 0.3);
[["Refit the slope curve", "with fitness-app data (Campbell et al. 2019, 2022)"],
  ["Add map or lidar inputs", "Wood et al. 2023; STRIDE 2024; RasterNet (this lab, 2020)"]]
  .forEach(([label, detail], i) => {
    const y = 2.05 + i * 1.35;
    box(s, `Prior card ${i + 1}`, M, y, 5.2, 1.1, C.background2);
    text(s, `Prior ${i + 1}`, [
      { text: label, options: { fontSize: 18, bold: true, color: C.text2, breakLine: true } },
      { text: detail, options: { fontSize: 13, color: C.accent4 } },
    ], M + 0.25, y + 0.18, 4.75, 0.75);
  });
text(s, "Gap", [
  { text: "Gap: ", options: { fontSize: 18, bold: true, color: C.accent2 } },
  { text: "always tested in the same area they were trained on.", options: { fontSize: 18, color: C.text1 } },
], M, 4.9, 5.2, 0.8);
const gx = 6.3, gw = W - M - gx, gi = gx + 0.35;
box(s, "Goal card", gx, 1.55, gw, 4.95, C.text2);
text(s, "Goal label", [{ text: "OUR TEST", options: { fontSize: 12, bold: true, color: C.accent5,
  charSpacing: 2 } }], gi, 1.8, gw - 0.7, 0.3);
text(s, "Goal", [{ text: "Train on 16 regions, predict the 17th. Repeat for each region.",
  options: { fontFace: HEAD, fontSize: 22, color: C.background1 } }], gi, 2.15, gw - 0.7, 0.85);
const dot = 0.22, gap = 0.07, dy = 3.2;
for (let i = 0; i < 16; i++) {
  s.addShape(SH.ellipse, { x: gi + i * (dot + gap), y: dy, w: dot, h: dot, fill: { color: C.accent5 },
    line: { type: "none" }, objectName: `Training region ${i + 1}` });
}
const ax = gi + 16 * (dot + gap) + 0.1, tx = ax + 0.47;
s.addShape(SH.rightArrow, { x: ax, y: dy + 0.01, w: 0.32, h: 0.2, fill: { color: C.accent5 },
  line: { type: "none" }, objectName: "Train to test arrow" });
s.addShape(SH.ellipse, { x: tx, y: dy - 0.04, w: 0.3, h: 0.3, fill: { color: C.accent2 },
  line: { type: "none" }, objectName: "Test region" });
text(s, "Train label", [{ text: "train on 16 regions", options: { fontSize: 13, color: C.accent5 } }],
  gi, dy + 0.35, 16 * (dot + gap) - gap, 0.3, { align: "center" });
text(s, "Test label", [{ text: "test", options: { fontSize: 13, bold: true, color: C.accent2 } }],
  tx - 0.35, dy + 0.35, 1.0, 0.3, { align: "center" });
text(s, "Arms label", [{ text: "Four models, same learning, different inputs:", options: { fontSize: 15,
  color: C.accent5 } }], gi, 4.0, gw - 0.7, 0.35);
const arms = [["Slope only", "like Tobler", C.accent4], ["Map tags", "OSM trail tags", C.accent2],
  ["Remote sensing", "lidar terrain, vegetation", C.accent1], ["Both", "tags + remote sensing", C.accent3]];
const cw = (gw - 0.7 - 0.2) / 2;
arms.forEach(([name, what, color], i) => {
  const x = gi + (i % 2) * (cw + 0.2), y = 4.45 + Math.floor(i / 2) * 0.95;
  box(s, `Arm ${name}`, x, y, cw, 0.8, color);
  text(s, `Arm ${name} text`, [
    { text: name, options: { fontSize: 15, bold: true, color: C.background1, breakLine: true } },
    { text: what, options: { fontSize: 12, color: C.background1 } },
  ], x + 0.15, y + 0.08, cw - 0.3, 0.68);
});
s.addNotes("Earlier work either refits the slope curve with data from fitness apps, or adds map and lidar inputs, but it always tests in the same area it trained on. The real use is a place with no data, so that's our test: train on 16 regions, predict the 17th, and repeat for every region. We compare four models that learn the same way but see different inputs: slope only, the map's tags, remote sensing, or both. (If asked: STRIDE is a lidar walking-speed model from timed field walks; RasterNet is our lab's road-speed model from lidar and overhead imagery.)");

// ---------------------------------------------------------------- 4 data
pres.addSection({ title: "Data" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data" });
s.addText("Data: 1,992 real hikes in 17 regions", { placeholder: "title" });
const mw = 7.6, mh = mw / aspect(ASSET("slide_map.png"));
s.addImage({ path: ASSET("slide_map.png"), x: M, y: 1.4, w: mw, h: mh, objectName: "Map of the 17 regions" });
text(s, "Map caption", [{ text: "Circle size = hours of walking", options: { fontSize: 12, color: C.accent4 } }],
  M, 1.45 + mh, mw, 0.3);
stat(s, "Hikes", 8.75, 1.65, W - M - 8.75, "1,992", C.text2, "hikes, from public GPS traces", null, 44);
stat(s, "Segments", 8.75, 3.3, W - M - 8.75, "290,640", C.text2,
  "trail segments of 50 m, each with a measured speed", null, 44);
const steps = ["Public GPS traces from OpenStreetMap", "Clean, remove stops, snap to the trail map",
  "50 m segments with slope, map tags and lidar"];
const pw = (CW - 2 * 0.55) / 3;
steps.forEach((t, i) => {
  const x = M + i * (pw + 0.55);
  box(s, `Pipeline step ${i + 1}`, x, 5.75, pw, 0.95, C.background2);
  text(s, `Pipeline step ${i + 1} text`, [{ text: t, options: { fontSize: 16, color: C.text2 } }],
    x + 0.2, 5.75, pw - 0.4, 0.95, { valign: "middle", align: "center" });
  if (i < 2) s.addShape(SH.rightArrow, { x: x + pw + 0.14, y: 6.07, w: 0.27, h: 0.3,
    fill: { color: C.accent3 }, line: { type: "none" }, objectName: `Pipeline arrow ${i + 1}` });
});
s.addNotes("The data are public GPS tracks that hikers upload to OpenStreetMap, from 17 mountain regions in the US and Canada; bigger circles mean more hours of hiking. I clean each track, remove stops, snap it to the trail map, and cut it into 50-meter pieces, each with a measured speed. That's about 2,000 hikes and 290,000 pieces. (If asked: 14,500 km and 4,700 hours of walking; snapping uses a hidden Markov model, and 85 to 99% of points match, by region.)");

// ---------------------------------------------------------------- 5 finding 1
pres.addSection({ title: "Findings" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Tobler's formula is too fast for real hikers", { placeholder: "title" });
const cvw = 7.0;
s.addImage({ path: ASSET("slide_curve.png"), x: M, y: 1.35, w: cvw, h: cvw / aspect(ASSET("slide_curve.png")),
  objectName: "Speed vs slope chart" });
stat(s, "Peak speed", 8.2, 1.9, W - M - 8.2, "4.2", C.accent1, "real hikers' top speed",
  "Tobler says 6 km/h", 54, " km/h");
stat(s, "Tobler regions", 8.2, 4.05, W - M - 8.2, "17 of 17", C.text2,
  "regions where Tobler predicts worse than a curve fitted to real hikes", null, 54);
s.addNotes("First result. The dots are real hikers' typical speed at each slope, downhill on the left, uphill on the right; the dashed line is Tobler. Real hikers top out around 4.2 km/h, not 6, so on everyday trail Tobler is about 20% too fast. And it predicts worse than a simple curve fitted to real hikes in all 17 regions. (If asked: going down is 8 to 23% faster than going up for the same hiker on the same trail, while Tobler assumes 42%; overall Tobler scores 12.5% worse.)");

// ---------------------------------------------------------------- 6 finding 2
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("In new regions, terrain beats map tags", { placeholder: "title" });
const rgw = 6.85;
s.addImage({ path: ASSET("slide_regions.png"), x: M, y: 1.3, w: rgw, h: rgw / aspect(ASSET("slide_regions.png")),
  objectName: "Terrain vs tags in each held-out region" });
stat(s, "Regions won", 7.95, 1.7, W - M - 7.95, "16 of 17", C.accent1,
  "new regions where terrain predicts better than map tags", null, 54);
stat(s, "Terrain gain", 7.95, 3.8, W - M - 7.95, "2–3%", C.accent1, "terrain's improvement over slope alone",
  "map tags: under 1%", 54);
text(s, "How to read", [{ text: "Each row: train on the other 16 regions, test on this one.",
  options: { fontSize: 14, italic: true, color: C.accent4 } }], 7.95, 5.85, W - M - 7.95, 0.6);
s.addNotes("This is the main result. Each row is one region the model never saw: it learned from the other 16 and was tested on this one. The black line at zero is slope alone, the curve from the last slide; dots to the right are better predictions. Blue adds terrain from lidar elevation maps, mostly the hidden ups and downs inside each 50-meter stretch that the average slope misses. Orange adds what the map says about the trail, like its difficulty grade and surface. Blue beats orange in 16 of 17 regions and is right of zero in every one. Orange is left of zero in five: there, tags learned elsewhere actually misled the model. Overall, terrain is 2 to 3% better than slope alone; tags, under 1%. (If asked why so small: speed is noisy; after slope, a quarter of what's left differs between hikes and the rest from stretch to stretch, and nothing we tried does much better; against Tobler, terrain is about 13% better. The score is CRPS, which grades the whole predicted range of speeds, and RMSE agrees. Terrain's lead over tags is +0.7 to +2.2 points, 95% interval. It holds with every hiker from the test region removed from training. Yosemite, the one exception, isn't investigated yet.)");

// ---------------------------------------------------------------- 7 next steps
pres.addSection({ title: "Next steps" });
s = pres.addSlide({ masterName: "CLOSING_DARK", sectionTitle: "Next steps" });
contours(s, 62);
s.addText("Next steps", { placeholder: "title" });
text(s, "Done so far", [
  { text: "Done so far: ", options: { fontSize: 16, bold: true, color: C.accent5 } },
  { text: "the dataset, the four-model comparison and a first paper draft.",
    options: { fontSize: 16, color: C.accent5 } },
], M, 1.35, CW, 0.4);
[["Weeks 10–11", "Learn Tobler's constants from terrain, with uncertainty"],
  ["Week 12", "Add aerial imagery (NAIP) with a pretrained encoder"],
  ["January", "Paper to IGARSS 2027"]].forEach(([when, what], i) => {
  const y = 2.25 + i * 0.85;
  text(s, `Next ${i + 1} when`, [{ text: when, options: { fontSize: 18, bold: true, color: C.accent5 } }],
    M, y + 0.04, 2.5, 0.45);
  text(s, `Next ${i + 1} what`, [{ text: what, options: { fontSize: 22, color: C.background1 } }],
    M + 2.65, y, CW - 2.65, 0.55);
});
box(s, "Question card", M, 5.05, CW, 1.25, C.accent3, { fill: { transparency: 55 } });
text(s, "Question", [
  { text: "Question for you: ", options: { fontSize: 20, bold: true, color: C.background1 } },
  { text: "which pretrained encoder would you use for 1 m aerial imagery along trails?",
    options: { fontSize: 20, color: C.background1 } },
], M + 0.35, 5.05, CW - 0.7, 1.25, { valign: "middle" });
s.addNotes("So far: the dataset, the four-model comparison, and a first paper draft. Next, in weeks 10 and 11: keep Tobler's shape but learn its constants from the terrain, with an uncertainty estimate. Week 12: add aerial imagery. Then the paper for IGARSS in January. One question for you: which pretrained encoder would you use for 1 m aerial imagery along trails? (If asked: the check on 6 November is whether that model beats boosted trees.)");

// ---------------------------------------------------------------- write
(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
