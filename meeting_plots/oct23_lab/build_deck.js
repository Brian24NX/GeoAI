// Lab-meeting deck, 23 Oct 2026 (MVRL, Prof. Jacobs): ~5 min, Dan's outline
// (problem, prior work, goal, what's done, next steps, visuals).
// Run:  node build_deck.js   (after ../../.venv/bin/python make_assets.py)
// Writes Zhou_LabMeeting_23Oct.pptx next to this file.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(path.join(
  "/Users/brian/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/aa9118d1-e698-4429-a4ef-0631f61817fb/5a1927db-0a59-4145-b0c1-b60ec2055cb8/skills/pptx",
  "scripts", "apply_theme.js"));

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..", "..");
const FIG = (f) => path.join(ROOT, "paper", "figures", f);
const ASSET = (f) => path.join(HERE, "assets", f);
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
  text(slide, `${name} label`, runs, x, ly, w, compare ? 0.85 : 0.5);
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
text(s, "Credits", [{ text: "Background: 10 m contours of Tuckerman and Huntington ravines, Mt Washington, NH, from USGS 3DEP 1 m lidar.  Slides prepared with help from Claude (Anthropic).",
  options: { fontSize: 10, color: C.accent5 } }], 0.8, 6.75, 11.7, 0.35);
s.addNotes("Hi everyone, I'm Brian. With Danni and Tianyi I'm working on predicting how fast people hike, from public GPS traces and remote sensing. In five minutes: the problem, what's been done, what I built, two findings, and next steps.");

// ---------------------------------------------------------------- 2 problem
pres.addSection({ title: "Problem and goal" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and goal" });
s.addText("GIS still times hikes with a 1993 formula", { placeholder: "title" });
box(s, "Formula card", M, 1.45, 6.0, 1.9, C.background2);
text(s, "Formula label", [{ text: "TOBLER'S HIKING FUNCTION (1993)", options: { fontSize: 12, bold: true,
  color: C.accent3, charSpacing: 1.5 } }], M + 0.3, 1.62, 5.4, 0.3);
text(s, "Formula", [
  { text: "v = 6 e", options: { fontFace: HEAD, fontSize: 30, color: C.text1 } },
  { text: "−3.5 |s + 0.05|", options: { fontFace: HEAD, fontSize: 30, color: C.text1, superscript: true } },
  { text: "   km/h", options: { fontSize: 18, color: C.accent4 } },
], M + 0.3, 1.98, 5.4, 0.75, { valign: "middle" });
const rows2 = [
  ["Fit to figures in a Swiss cartography textbook", "not to observed hikes"],
  ["One curve for every trail", "no rocks, roots, steps or vegetation"],
  ["Still the default in GIS travel-time tools", "search and rescue, wildfire escape routes, trail apps"],
];
text(s, "Formula how to read", [
  { text: "s = slope (0.10 = 10% uphill).  ", options: { fontSize: 14, color: C.text1 } },
  { text: "Fastest at a gentle downhill: 6 km/h. Flat: 5.0 km/h. 20% climb: 2.5 km/h.",
    options: { fontSize: 14, color: C.accent4 } },
], M + 0.3, 2.75, 5.4, 0.5);
rows2.forEach(([label, detail], i) => {
  const y = 3.6 + i * 0.78;
  s.addShape(SH.ellipse, { x: M + 0.02, y: y + 0.09, w: 0.18, h: 0.18, fill: { color: C.text2 },
    line: { type: "none" }, objectName: `Problem marker ${i + 1}` });
  text(s, `Problem ${i + 1}`, [
    { text: label, options: { fontSize: 16, bold: true, color: C.text2, breakLine: true } },
    { text: detail, options: { fontSize: 14, color: C.text1 } },
  ], M + 0.4, y, 5.6, 0.72);
});
text(s, "Tag coverage note", [
  { text: "And the map rarely helps: ", options: { fontSize: 16, bold: true, color: C.text2 } },
  { text: "OSM's difficulty tag covers ", options: { fontSize: 16, color: C.text1 } },
  { text: "1.5% to 96%", options: { fontSize: 16, bold: true, color: C.accent2 } },
  { text: " of walked trail, depending on the region.", options: { fontSize: 16, color: C.text1 } },
], M, 5.95, 6.0, 0.8);
s.addChart(pres.ChartType.bar, [{ name: "Walked trail with sac_scale (%)",
  labels: data.coverage.map((d) => d.region), values: data.coverage.map((d) => d.pct) }], {
  x: 7.05, y: 1.35, w: W - M - 7.05, h: 5.5, barDir: "bar", barGapWidthPct: 45,
  chartColors: [C.accent2], showLegend: false,
  showTitle: true, title: "Walked trail with a difficulty tag (sac_scale), by region",
  titleFontSize: 14, titleColor: C.text2, titleFontFace: "+mn-lt",
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"',
  dataLabelFontSize: 10, dataLabelColor: C.text1, dataLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 11, catAxisLabelColor: C.text1, catAxisLabelFontFace: "+mn-lt",
  catAxisLineShow: false, valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 112,
  valGridLine: { style: "none" }, catGridLine: { style: "none" },
  objectName: "Tag coverage chart",
});
s.addNotes("Today, if software estimates how long a hike takes, it usually uses Tobler's formula from 1993. v is walking speed, s is the slope. It says you're fastest, 6 km/h, on a gentle downhill, and slower the steeper it gets: about 5 km/h on flat ground, 2.5 on a 20% climb. There are three problems. It was fit to numbers in a cartography textbook, not to real hikes. It's one curve for every trail, so a rocky scramble and a smooth path get the same speed. And it's still what GIS tools use for search and rescue, wildfire escape routes and trail apps. Could the trail map fix this? OpenStreetMap has a difficulty grade called sac_scale, from the Swiss Alpine Club: from easy 'hiking' up to 'alpine hiking'. But this chart shows how much of the trail actually has it: 96% in the Adirondacks, under 2% in the Green Mountains. For most trails, the map can't tell you how hard they are.");

// ---------------------------------------------------------------- 3 prior work + goal
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and goal" });
s.addText("Prior work stays inside one region", { placeholder: "title" });
const prior = [
  ["Slope-only curves", "Tobler 1993; Campbell et al. 2019, 2022 (Strava, AllTrails): Tobler is too fast"],
  ["Extra inputs, one study area", "Wood et al. 2023 (England & Wales, OSM + lidar); Huang et al. 2026 (Hong Kong): random or cross-validated splits"],
  ["Lidar model from field walks", "STRIDE, Campbell et al. 2024: slope, understory density, ground roughness"],
  ["This lab", "RasterNet, Hadzic et al. 2020: road speed from lidar and overhead imagery"],
];
prior.forEach(([label, detail], i) => {
  const y = 1.45 + i * 1.08;
  box(s, `Prior card ${i + 1}`, M, y, 6.7, 0.94, C.background2);
  text(s, `Prior ${i + 1}`, [
    { text: label, options: { fontSize: 16, bold: true, color: C.text2, breakLine: true } },
    { text: detail, options: { fontSize: 14, color: C.text1 } },
  ], M + 0.25, y + 0.1, 6.25, 0.8);
});
text(s, "Gap", [
  { text: "Missing: ", options: { fontSize: 16, bold: true, color: C.accent2 } },
  { text: "a test in regions the model never saw, and map tags vs remote sensing head to head.",
    options: { fontSize: 16, color: C.text1 } },
], M, 5.9, 6.7, 0.75);
const gx = 7.65, gw = W - M - gx;
box(s, "Goal card", gx, 1.45, gw, 5.25, C.text2);
text(s, "Goal label", [{ text: "OUR GOAL", options: { fontSize: 12, bold: true, color: C.accent5,
  charSpacing: 2 } }], gx + 0.3, 1.7, gw - 0.6, 0.3);
text(s, "Goal", [{ text: "Predict the speed of every 50 m of trail, with its uncertainty, from what can be seen from above, and test it in regions the model never saw.",
  options: { fontFace: HEAD, fontSize: 20, color: C.background1 } }], gx + 0.3, 2.05, gw - 0.6, 1.9);
text(s, "Arms label", [{ text: "Four models, same method, different inputs", options: { fontSize: 14,
  color: C.accent5 } }], gx + 0.3, 4.0, gw - 0.6, 0.35);
const arms = [["Tobler", "slope only", C.accent4], ["Tags", "OSM trail tags", C.accent2],
  ["Remote sensing", "lidar terrain, vegetation, embeddings", C.accent1], ["Both", "everything", C.accent3]];
const cw = (gw - 0.6 - 0.2) / 2;
arms.forEach(([name, what, color], i) => {
  const x = gx + 0.3 + (i % 2) * (cw + 0.2), y = 4.45 + Math.floor(i / 2) * 1.05;
  box(s, `Arm ${name}`, x, y, cw, 0.9, color);
  text(s, `Arm ${name} text`, [
    { text: name, options: { fontSize: 15, bold: true, color: C.background1, breakLine: true } },
    { text: what, options: { fontSize: 12, color: C.background1 } },
  ], x + 0.15, y + 0.1, cw - 0.3, 0.75);
});
s.addNotes("Crowdsourced GPS studies already show Tobler is too fast, and newer models add inputs like OSM terrain classes, weather or lidar. STRIDE models speed from lidar using timed field walks, and our lab's RasterNet learns road speed from lidar and imagery. But these studies fit and test in one area, with random splits. Nobody has tested whether such a model works in a region it has never seen, or compared map tags with remote sensing directly. That is the goal: four models that differ only in what they can see, tested on regions held out entirely.");

// ---------------------------------------------------------------- 4 what I built
pres.addSection({ title: "What I built" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "What I built" });
s.addText("17 regions, 290,640 measured trail segments", { placeholder: "title" });
s.addImage({ path: FIG("fig_map.png"), x: M, y: 1.4, w: 7.0, h: 7.0 / 1.937,
  objectName: "Map of the 17 regions" });
text(s, "Map caption", [{ text: "Circle area = walking hours. Blue: full OSM download plus the lab's crawl; orange: crawl only. Inset: White Mountains segments by speed.",
  options: { fontSize: 11, color: C.accent4 } }], M, 5.08, 7.0, 0.45);
const stats4 = [["290,640", "", "walking segments, 50 m each"], ["1,992", "", "hikes (outings)"],
  ["4,702", " h", "of walking"], ["14,532", " km", "of trail walked"]];
stats4.forEach(([v, u, l], i) => {
  const x = 7.95 + (i % 2) * 2.55, y = 1.5 + Math.floor(i / 2) * 1.75;
  stat(s, `Data stat ${i + 1}`, x, y, 2.3, v, C.text2, l, null, 36, u);
});
const steps = ["Public OSM GPS traces", "Clean and remove stops", "Match to the trail map",
  "Cut into 50 m segments", "Add slope, tags, lidar terrain, vegetation, embeddings"];
let px = M;
steps.forEach((t, i) => {
  const w = i === 4 ? 3.0 : 2.0;
  box(s, `Pipeline step ${i + 1}`, px, 5.75, w, 0.95, C.background2);
  text(s, `Pipeline step ${i + 1} text`, [{ text: t, options: { fontSize: 14, color: C.text2,
    bold: i === 4 } }], px + 0.15, 5.75, w - 0.3, 0.95, { valign: "middle", align: "center" });
  if (i < 4) s.addShape(SH.rightArrow, { x: px + w + 0.05, y: 6.1, w: 0.18, h: 0.25,
    fill: { color: C.accent3 }, line: { type: "none" }, objectName: `Pipeline arrow ${i + 1}` });
  px += w + 0.28;
});
s.addNotes("I built the dataset from public OpenStreetMap GPS traces in 17 mountain regions in the US and Canada, plus the lab's crawl of 1.5 million original uploads. The pipeline cleans each trace, removes stops, matches it to the trail network with a hidden Markov model, and cuts it into 50 m segments. Each segment gets its speed, slope, OSM tags, terrain from 1 m lidar and 5 m elevation, vegetation and satellite embeddings. That's 290,640 segments from 1,992 hikes.");

// ---------------------------------------------------------------- 5 finding 1
pres.addSection({ title: "Findings" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Tobler is too fast and too peaked", { placeholder: "title" });
s.addImage({ path: FIG("fig_curve.png"), x: M, y: 1.35, w: 6.45, h: 6.45 / 1.186,
  objectName: "Speed vs slope figure" });
stat(s, "Peak speed", 7.6, 1.5, W - M - 7.6, "4.2", C.accent1,
  "real peak walking speed, on level to gently descending trail", "Tobler: 6 km/h", 40, " km/h");
stat(s, "Downhill", 7.6, 3.3, W - M - 7.6, "8–23%", C.accent1,
  "faster downhill than uphill, same hiker on the same trail", "Tobler: 42% at every grade");
stat(s, "Tobler regions", 7.6, 5.1, W - M - 7.6, "17 of 17", C.text2,
  "regions where Tobler predicts worse than a refitted slope curve", "−12.5% overall (CRPS skill)");
s.addNotes("First finding. Real hikers peak around 4.2 km/h, not 6, and the top of the curve is rounded. From hikes where the same person walked the same trail both ways, going down is only 8 to 23% faster than going up; Tobler assumes 42% at every grade. Scored in regions the model never saw, Tobler is worse than a refitted slope curve in all 17 regions.");

// ---------------------------------------------------------------- 6 finding 2
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("In new regions, terrain beats map tags", { placeholder: "title" });
s.addImage({ path: FIG("fig_skill_regions.png"), x: M, y: 1.25, w: CW, h: CW / 3.113,
  objectName: "Skill by model and by region" });
const sw = (CW - 2 * 0.32) / 3;
stat(s, "Terrain skill", M, 5.3, sw, "+2.1 to +2.8%", C.accent1,
  "terrain, in regions the model never saw", null, 30);
stat(s, "Regions won", M + sw + 0.32, 5.3, sw, "16 of 17", C.text2,
  "held-out regions where terrain beats tags", null, 30);
stat(s, "Tag skill", M + 2 * (sw + 0.32), 5.3, sw, "+0.4 to +0.9%", C.accent2,
  "OSM tags, in regions the model never saw", null, 30);
text(s, "Skill note", [{ text: "Skill: how much better a model's predicted speed distribution scores (CRPS) than a slope-only curve refitted to our data. It holds for newer hikes, every GPS rate, whole zones held out and hikers the model never saw; vegetation and satellite embeddings don't transfer.",
  options: { fontSize: 12, color: C.accent4 } }], M, 6.42, CW, 0.5);
s.addNotes("The main result. Each bar is a model's skill over a slope-only curve: light bars are new hikes in regions the model knows, dark bars are regions it never saw. Terrain from elevation keeps its gain in new regions, about 2 to 3%, and on the right it beats the map tags in 16 of 17 held-out regions. Tags lose most of their gain. This holds for newer hikes, any GPS rate, whole zones held out, and even with all of a region's hikers removed from training. Vegetation and satellite embeddings help inside a region but don't transfer.");

// ---------------------------------------------------------------- 7 next steps
pres.addSection({ title: "Next steps" });
s = pres.addSlide({ masterName: "CLOSING_DARK", sectionTitle: "Next steps" });
contours(s, 62);
s.addText("Next: Tobler with learned constants", { placeholder: "title" });
const done = [["✓  T1 dataset", 1.75], ["✓  T2 covariates", 2.05], ["✓  T3 four-model comparison", 3.15],
  ["✓  T4 slope curves", 2.25], ["✓  Paper draft 0", 1.95]];
let cx = M;
done.forEach(([t, w], i) => {
  box(s, `Done chip ${i + 1}`, cx, 1.45, w, 0.5, C.accent3);
  text(s, `Done chip ${i + 1} text`, [{ text: t, options: { fontSize: 14, bold: true,
    color: C.background1 } }], cx, 1.45, w, 0.5, { valign: "middle", align: "center" });
  cx += w + 0.24;
});
const next = [
  ["Weeks 10–11", "Tobler's form with its constants learned from terrain, plus a variance head (PyTorch). Gate 2, 6 Nov: does it beat boosted trees?"],
  ["Week 12", "NAIP aerial imagery: a frozen pretrained encoder with a small head."],
  ["Week 13 to 11 Jan", "Full paper draft, then IGARSS 2027 and its Student Paper Competition."],
];
next.forEach(([when, what], i) => {
  const y = [2.45, 3.5, 4.3][i];
  text(s, `Next ${i + 1} when`, [{ text: when, options: { fontSize: 16, bold: true, color: C.accent5 } }],
    M, y + 0.04, 2.5, 0.4);
  text(s, `Next ${i + 1} what`, [{ text: what, options: { fontSize: 18, color: C.background1 } }],
    M + 2.65, y, CW - 2.65, 0.85);
});
box(s, "Question card", M, 5.35, CW, 1.1, C.accent3, { fill: { transparency: 55 } });
text(s, "Question", [
  { text: "Question for the lab: ", options: { fontSize: 18, bold: true, color: C.background1 } },
  { text: "which pretrained aerial-imagery encoder would you use for 1 m NAIP chips along trails?",
    options: { fontSize: 18, color: C.background1 } },
], M + 0.3, 5.35, CW - 0.6, 1.1, { valign: "middle" });
s.addNotes("Where we are: the dataset, the covariates, the four-model comparison and the curves are done, and there's a first paper draft. Next, in weeks 10 and 11, the plan's main model: Tobler's form with its constants learned from the terrain, plus a variance head, in PyTorch. That's Gate 2 on November 6: does it beat boosted trees? Week 12: an imagery arm with NAIP and a frozen pretrained encoder. Then the full draft and IGARSS in January. One question for you: which pretrained aerial-imagery encoder would you use for that?");

// ---------------------------------------------------------------- write
(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
