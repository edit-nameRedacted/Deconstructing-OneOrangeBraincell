/*
  details.js — the panel beside a zoomed tail.

  With nothing selected it shows the overview of the cat:
    - what its group is (the category value, in words from text.js);
    - an example post from the group, picked at random (with "Show another");
    - what its typical cat looks like, in words;
    - its tail, item by item; each line is a button that selects that segment or stripe.
  With a segment (a tail variable) selected:
    - what the variable is; the group's median and its percentile among all posts, and whether
      that is in the left tail (below the 10th percentile), the body, or the right tail (above the 90th);
    - a dot strip: every post as a dot along the variable's range, this group's posts highlighted,
      the outer 10% on each side shaded, and a line at the group's median;
    - "Chase this tail": regroup all posts into left tail / body / right tail of this variable.
  With a stripe (a hand code) selected:
    - the group's standout value for that code, what it means, its share here against all posts;
    - the code's full breakdown: every value's share of this group, with all posts marked;
    - "Chase this tail": switch the row to that code.
  All three end with the group's post titles, folded away.

  Takes: the prepared data, the view, the zoomed cat, the state, and callbacks: onPick(key) to
  select a segment or ring (null = back to the overview), onChase(arrange) to regroup.
  Gives back: showOverview(...), showDetails(...), hideDetails().
  Replaces: showInfo() and strip() in the prototype (the strip was a hand-written SVG string;
  it is now D3 scales, an axis and a join of circles).
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { INVERT, UNIT, PATHS, formatValue, ordinal } from "./config.js";
import { stableHash, isTailArrangement } from "./data.js";
import { CATEGORY_TEXT, TAILVAR_TEXT } from "./text.js";

// Distribution chart size, in pixels: histogram on top, dot strip below, axis at the bottom.
// The width is set when drawing, from the panel's actual width (between STRIP_MIN and STRIP_MAX),
// so the axis text stays at its true size on a phone.
const STRIP = { left: 16, right: 16, top: 6, histHeight: 84, gap: 6, dotsHeight: 54, bottom: 34 };
const HIST_BINS = 20;       // bins for a variable with many values
const FEW_VALUES = 16;      // up to this many distinct values, one bar per value
const STRIP_MIN = 260;
const STRIP_MAX = 760;

// Words for the typical cat's build.
const BUILD_WORDS = { typical: "an average build", kitten: "a kitten's build", slender: "a slender build", chunky: "a chunky build" };

export function hideDetails() {
  d3.select("#info").html("");
}

// An empty panel to fill.
function freshPanel() {
  return d3.select("#info").html("");
}

// ---------------------------------------------------------------------------
// Overview: nothing selected
// ---------------------------------------------------------------------------

export function showOverview({ data, view, cat, state, onPick }) {
  const box = freshPanel();
  const group = cat.group;

  // What the group is.
  box.append("h3").text(`${view.arr.title}: ${group.label}`);
  const meaning = groupMeaning(data, view, group);
  if (meaning) box.append("p").attr("class", "desc").text(meaning);

  // An example post from the group: a photo or video, picked at random.
  examplePost(box, data, cat);

  // What its typical cat looks like.
  const look = cat.look;
  let lookText = `${group.posts.length} posts. Their typical cat has ${BUILD_WORDS[look.body]}`;
  if (look.medianWhite != null) lookText += ` and about ${Math.round(look.medianWhite)}% white fur`;
  if (look.extraZones.length) lookText += `, with extra white on its ${look.extraZones.join(" and ")}`;
  lookText += ".";
  if (look.small) lookText += " This is a small group, so the look is a loose guess.";
  box.append("p").text(lookText);

  // Its tail, item by item: each line selects that part of the tail.
  if (cat.segments.length || cat.rings.length) {
    box.append("h4").text("Its tail");
    const list = box.append("ul").attr("class", "tail-list");
    const lines = [
      ...cat.segments.map((s) => ({
        key: s.key,
        swatch: s.fill,
        text: `${s.label}: median ${formatValue(s.key, s.median)}${UNIT[s.key]}, ${ordinal(Math.round(s.pct * 100))} percentile`,
      })),
      ...cat.rings.map((r) => ({
        key: r.key,
        swatch: r.color,
        stripe: true,
        text: `${r.codeLabel}: ${r.valueLabel} ${Math.round(r.share * 100)}% (vs ${Math.round(r.overall * 100)}% of all posts)`,
      })),
    ];
    const buttons = list.selectAll("li").data(lines).join("li")
      .append("button").attr("type", "button").attr("class", "linklike")
      .on("click", (event, line) => onPick(line.key));
    buttons.append("span").attr("class", (d) => (d.stripe ? "swatch stripe" : "swatch")).style("background", (d) => d.swatch ?? null);
    buttons.append("span").text((d) => d.text);
    box.append("p").attr("class", "hint").text("Pick a line, or click a segment or stripe on the tail, for the details behind it.");
  }

  postList(box, group.posts);
}

// ---------------------------------------------------------------------------
// Example post
// ---------------------------------------------------------------------------

// The example shown for each cat, remembered (by cat id) so it stays put while you click around
// its tail; "Show another" picks a new one.
const chosenExample = new Map();

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];

// A random post from the group that has a photo or video, other than `avoid`.
function randomPostWithMedia(data, posts, avoid) {
  const candidates = posts.filter((p) => data.media[p.id] && p !== avoid);
  if (candidates.length === 0) return avoid ?? null;
  return candidates[Math.floor(Math.random() * candidates.length)];
}

function examplePost(box, data, cat) {
  if (!chosenExample.has(cat.id)) chosenExample.set(cat.id, randomPostWithMedia(data, cat.group.posts, null));
  const post = chosenExample.get(cat.id);
  if (!post) return;                                   // no media index, or no media in this group
  const media = data.media[post.id];
  const src = (path) => PATHS.mediaRoot + path;

  const figure = box.append("figure").attr("class", "example");
  if (media.type === "video") {
    figure.append("video")
      .attr("src", src(media.src))
      .attr("poster", media.poster ? src(media.poster) : null)
      .attr("controls", "").attr("muted", "").attr("loop", "").attr("playsinline", "")
      .attr("preload", "metadata")
      .attr("aria-label", `Example post: ${post.title}`)
      .property("muted", true);                        // the attribute alone doesn't mute in every browser
  } else {
    figure.append("img").attr("src", src(media.src)).attr("alt", `Example post: ${post.title}`);
  }

  const [year, month] = post.month.split("-");
  const caption = figure.append("figcaption");
  caption.append("span").attr("class", "example-title").text(`“${post.title}”`);
  let where = `${MONTHS[Number(month) - 1]} ${year}, #${post.rank} of the month`;
  if (media.type === "image" && media.count > 1) where += ` · first of ${media.count} photos`;
  caption.append("span").attr("class", "example-meta").text(where);
  if (cat.group.posts.filter((p) => data.media[p.id]).length > 1) {
    caption.append("button").attr("type", "button").attr("class", "linklike example-next")
      .text("Show another")
      .on("click", () => {
        chosenExample.set(cat.id, randomPostWithMedia(data, cat.group.posts, post));
        const fresh = d3.create("div");                // redraw just the figure, in place
        examplePost(fresh, data, cat);
        figure.node().replaceWith(fresh.select("figure").node());
      });
  }
}

// One sentence on what a group means: from text.js for a hand code, or the tail's range.
function groupMeaning(data, view, group) {
  if (isTailArrangement(view.arr.key)) {
    const label = data.tailvars[view.arr.key.slice(5)].label.toLowerCase();
    const where = { left: "the lowest 10%", body: "the middle 80%", right: "the highest 10%" }[group.value];
    return `Posts in ${where} of all posts on ${label}.`;
  }
  return CATEGORY_TEXT[view.arr.key]?.values[group.value] ?? CATEGORY_TEXT[view.arr.key]?.lede ?? "";
}

// ---------------------------------------------------------------------------
// Details: a segment or stripe selected
// ---------------------------------------------------------------------------

export function showDetails({ data, cat, selectedKey, state, onChase, onPick }) {
  const item = [...cat.segments, ...cat.rings].find((x) => x.key === selectedKey);
  if (!item) { hideDetails(); return; }

  const box = freshPanel();
  box.append("button").attr("type", "button").attr("class", "linklike back-link")
    .text("← About this cat")
    .on("click", () => onPick(null));

  if (selectedKey.startsWith("code:")) {
    // ---- A stripe: the group's standout value for one hand code, and the code's full breakdown ----
    const h = box.append("h3").attr("class", "with-swatch");
    h.append("span").attr("class", "swatch stripe").style("background", item.color);
    h.append("span").text(item.codeLabel);
    const p = box.append("p");
    p.append("span").text("Stands out in this group: ");
    p.append("strong").text(item.valueLabel);
    p.append("span").text(`, ${Math.round(item.share * 100)}% of its posts against ${Math.round(item.overall * 100)}% of all posts.`);
    const meaning = CATEGORY_TEXT[item.code]?.values[item.value];
    if (meaning) box.append("p").attr("class", "desc").text(meaning);
    breakdownChart(box, item);
    box.append("p").attr("class", "hint")
      .text("Bars: share of this group's posts. Ticks: share of all posts. The stripe on the tail shows the standout value, as thick as its bar.");
    chaseButton(box, () => onChase(item.code), `Regroup all the cats by ${item.codeLabel.toLowerCase()}.`);
  } else {
    // ---- A segment: the group's median among all posts ----
    const varKey = item.key;
    const dist = data.tailvars[varKey].dist;
    const where = item.pct < 0.1 ? "left tail" : item.pct > 0.9 ? "right tail" : "body";
    box.append("h3").text(data.tailvars[varKey].label);
    if (TAILVAR_TEXT[varKey]) box.append("p").attr("class", "desc").text(TAILVAR_TEXT[varKey]);
    const p = box.append("p");
    p.append("span").text("This group's median is ");
    p.append("strong").text(`${formatValue(varKey, item.median)}${UNIT[varKey]}`);
    p.append("span").text(`, the ${ordinal(Math.round(item.pct * 100))} percentile of all ${dist.n} posts (${where}).`);
    if (INVERT[varKey]) {
      p.append("span").text(" Lower rank is higher on the month's list, so the segment is longer the nearer the top.");
    }
    dotStrip(box, data, varKey, cat.group.posts, item.median);
    const fitted = data.tailvars[varKey].dist.kind === "lognormal";
    box.append("p").attr("class", "hint")
      .text(`Bars count all ${dist.n} posts, with this group's share in orange${fitted ? "; the curve is the log-normal fitted to all posts" : ""}. ` +
            "Below, each dot is a post. The shaded ends are the lowest and highest 10%: the tails.");
    // No chase when the row already shows this variable's tails.
    if (state.arrange !== "tail:" + varKey) {
      chaseButton(box, () => onChase("tail:" + varKey), "Regroup all posts into this measure's left tail, body and right tail.");
    }
  }

  postList(box, cat.group.posts);
}

// One hand code's breakdown for the group: a row per value with a bar for its share of this group
// (in the stripe's colour) and a tick at its share of all posts. Plain HTML rows built with a D3
// join; bar widths come from a d3.scaleLinear on 0–100%.
function breakdownChart(box, stripe) {
  const width = d3.scaleLinear().domain([0, 1]).range([0, 100]);   // share -> % of the track
  const rows = box.append("div").attr("class", "breakdown")
    .selectAll(".bd-row").data(stripe.breakdown).join("div")
    .attr("class", (b) => (b.value === stripe.value ? "bd-row is-standout" : "bd-row"));
  rows.append("span").attr("class", "bd-label").text((b) => b.label);
  const track = rows.append("span").attr("class", "bd-track");
  track.append("span").attr("class", "bd-bar")
    .style("width", (b) => width(b.share) + "%")
    .style("background", stripe.color);
  track.append("span").attr("class", "bd-all").style("left", (b) => width(b.overall) + "%")
    .attr("title", (b) => `${Math.round(b.overall * 100)}% of all posts`);
  rows.append("span").attr("class", "bd-num")
    .text((b) => `${Math.round(b.share * 100)}% · ${Math.round(b.overall * 100)}%`);
}

// "Chase this tail", with a line saying what it will do.
function chaseButton(box, onClick, note) {
  const row = box.append("div").attr("class", "btnrow");
  row.append("button").attr("type", "button").attr("class", "primary").attr("id", "chase")
    .text("Chase this tail")
    .on("click", onClick);
  row.append("span").attr("class", "hint").text(note);
}

// The distribution of one variable across all posts, in two panels that share one x axis:
//   top     a histogram of all posts; the part of each bar that is this group's posts is orange.
//           For the skewed counts, the log-normal fitted to all posts is drawn over it as a curve.
//   bottom  every post as a dot (this group's in orange), with a line at the group's median.
// Behind both, the outer 10% on each side (the tails) is shaded.
function dotStrip(box, data, varKey, groupPosts, groupMedian) {
  const dist = data.tailvars[varKey].dist;
  const { left, right, top, histHeight, gap, dotsHeight, bottom } = STRIP;
  const width = Math.max(STRIP_MIN, Math.min(STRIP_MAX, box.node().clientWidth));
  const height = top + histHeight + gap + dotsHeight + bottom;
  const label = data.tailvars[varKey].label.toLowerCase();
  const isLog = dist.kind === "lognormal";

  // Panel edges (pixels from the top of the svg).
  const histTop = top, histBottom = top + histHeight;
  const dotsTop = histBottom + gap, dotsBottom = dotsTop + dotsHeight;

  const inGroup = new Set(groupPosts.map((p) => p.id));
  const posts = data.posts.filter((p) => p.vals[varKey] != null);
  const valueOf = (p) => p.vals[varKey];
  const distinct = [...new Set(posts.map(valueOf))].sort(d3.ascending);
  const fewValues = distinct.length <= FEW_VALUES;
  const step = smallestStep(distinct);

  // ---- x: shared by both panels ----
  // Skewed counts (upvotes, comments…) are log-normal: a log scale spreads them out evenly.
  // Everything else uses a linear scale. A variable with few values gets half a step of room at
  // each end, so its first and last bars fit. If all values are equal, widen the domain so the
  // scale still works.
  let domain = dist.min === dist.max ? [dist.min, dist.min + 1] : [dist.min, dist.max];
  if (fewValues && !isLog) domain = [dist.min - step / 2, dist.max + step / 2];
  const x = (isLog ? d3.scaleLog() : d3.scaleLinear()).domain(domain).range([left, width - right]);

  const svg = box.append("svg")
    .attr("class", "strip")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("role", "img")
    .attr("aria-label", `Distribution of all posts' ${label}: a histogram${isLog ? " with a fitted log-normal curve" : ""}, then every post as a dot. This group is highlighted; the outer 10% on each side is shaded.`);

  // ---- The tails: the outer 10% on each side, shaded through both panels ----
  svg.append("rect").attr("class", "band")
    .attr("x", left).attr("y", histTop)
    .attr("width", Math.max(0, x(dist.p10) - left)).attr("height", dotsBottom - histTop);
  svg.append("rect").attr("class", "band")
    .attr("x", x(dist.p90)).attr("y", histTop)
    .attr("width", Math.max(0, width - right - x(dist.p90))).attr("height", dotsBottom - histTop);

  // ---- Histogram ----
  const bins = fewValues ? binPerValue(posts, valueOf, distinct, step) : evenBins(posts, valueOf, x, isLog);
  // Each bin holds its posts; count how many are this group's.
  for (const bin of bins) bin.inGroup = bin.filter((p) => inGroup.has(p.id)).length;

  // The fitted curve (log-normal variables only), as expected counts per bin so it shares the
  // bars' y scale: n x bin width x the normal density, all in log units.
  let curve = [];
  if (isLog && dist.mu != null && dist.sd != null) {
    const binWidth = bins[0].logWidth;
    const zMin = Math.log(domain[0]), zMax = Math.log(domain[1]);
    curve = d3.range(0, 1.0001, 1 / 200).map((t) => {
      const z = zMin + (zMax - zMin) * t;                 // a point on the log axis
      return [Math.exp(z), posts.length * binWidth * normalDensity(z, dist.mu, dist.sd)];
    });
  }

  // y: counts, from the bottom of the histogram panel up. Tall enough for the highest bar or curve.
  const yMax = d3.max([d3.max(bins, (b) => b.length), d3.max(curve, (c) => c[1]) ?? 0]);
  const y = d3.scaleLinear().domain([0, yMax]).range([histBottom, histTop + 4]);

  // One bar per bin: all posts in grey, and this group's part in orange at the bottom of the bar.
  const barGap = 1;
  const barX = (b) => x(b.x0) + barGap / 2;
  const barW = (b) => Math.max(3, x(b.x1) - x(b.x0) - barGap);   // at least 3px, so thin bars still show
  const bars = svg.append("g").attr("class", "hist");
  bars.selectAll("rect.bar").data(bins).join("rect").attr("class", "bar")
    .attr("x", barX).attr("width", barW)
    .attr("y", (b) => y(b.length)).attr("height", (b) => histBottom - y(b.length));
  bars.selectAll("rect.bar-in").data(bins.filter((b) => b.inGroup > 0)).join("rect").attr("class", "bar-in")
    .attr("x", barX).attr("width", barW)
    .attr("y", (b) => y(b.inGroup)).attr("height", (b) => histBottom - y(b.inGroup));

  // The curve: d3.line turns the [value, count] points into a path through the same scales.
  if (curve.length) {
    const line = d3.line().x((c) => x(c[0])).y((c) => y(c[1])).curve(d3.curveBasis);
    svg.append("path").attr("class", "fit").attr("d", line(curve));
  }

  // ---- Dots ----
  // Each post gets a fixed vertical jitter from a hash of its id, so dots with equal values don't
  // sit on top of each other, and the strip looks the same every time.
  svg.append("g").selectAll("circle")
    .data(posts, (p) => p.id)
    .join("circle")
    .attr("class", (p) => (inGroup.has(p.id) ? "dot in" : "dot"))
    .attr("cx", (p) => x(valueOf(p)))
    .attr("cy", (p) => dotsTop + 6 + ((stableHash(p.id) % 1000) / 1000) * (dotsHeight - 12))
    .attr("r", (p) => (inGroup.has(p.id) ? 3.6 : 2.8))
    .sort((a, b) => inGroup.has(a.id) - inGroup.has(b.id));   // group's dots drawn on top

  // The group's median, through both panels.
  if (groupMedian != null) {
    svg.append("line").attr("class", "med")
      .attr("x1", x(groupMedian)).attr("x2", x(groupMedian)).attr("y1", histTop).attr("y2", dotsBottom + 2);
  }

  // ---- Axis ----
  // Ticks at the minimum, 10th percentile, median, 90th percentile and maximum. Where two of these
  // are the same value (e.g. crossposts: min = 10th = median = 0), they share one tick and their
  // names are joined.
  const marks = [[dist.min, ""], [dist.p10, "10th"], [dist.p50, "median"], [dist.p90, "90th"], [dist.max, ""]];
  const ticks = d3.rollups(marks, (ms) => ms.map((m) => m[1]).filter(Boolean).join(" · "), (m) => m[0]);
  const names = new Map(ticks);
  const axis = d3.axisBottom(x)
    .tickValues(ticks.map((t) => t[0]))
    .tickFormat((v) => formatValue(varKey, v))
    .tickSize(4);
  const axisG = svg.append("g").attr("class", "axis").attr("transform", `translate(0,${dotsBottom})`).call(axis);
  axisG.select(".domain").remove();                         // the shaded bands already mark the range
  axisG.selectAll(".tick").append("text")                   // second line: which percentile
    .attr("class", "tick-name").attr("y", 26).text((v) => names.get(v));
}

// The bell curve: how dense a normal distribution with this mean and spread is at z.
function normalDensity(z, mean, sd) {
  return Math.exp(-((z - mean) ** 2) / (2 * sd * sd)) / (sd * Math.sqrt(2 * Math.PI));
}

// The smallest gap between neighbouring values (1 if there is only one value).
function smallestStep(sortedValues) {
  if (sortedValues.length < 2) return 1;
  return d3.min(d3.pairs(sortedValues), ([a, b]) => b - a);
}

// Histogram bins, as d3.bin makes them: arrays of posts, each with x0 and x1 (the bin's edges).

// A variable with only a few distinct values (ratings, crossposts…): one bar per value, centred on
// it, so the bars line up with the dots. The bin edges sit halfway between neighbouring values.
function binPerValue(posts, valueOf, distinct, step) {
  const edges = distinct.slice(1).map((v, i) => (distinct[i] + v) / 2);
  const bins = d3.bin().value(valueOf)
    .domain([distinct[0] - step / 2, distinct.at(-1) + step / 2])
    .thresholds(edges)(posts);
  // Draw each bar a little narrower than one step, centred on its value.
  bins.forEach((b, i) => { b.x0 = distinct[i] - step * 0.45; b.x1 = distinct[i] + step * 0.45; });
  return bins;
}

// Anything else: HIST_BINS bins of equal width along the axis. For a log axis that means equal
// width in log units, so the bars look even on screen (and the fitted curve uses that width).
function evenBins(posts, valueOf, x, isLog) {
  const [lo, hi] = x.domain();
  const toAxis = isLog ? Math.log : (v) => v;               // where a value sits along the axis
  const fromAxis = isLog ? Math.exp : (v) => v;
  const a0 = toAxis(lo), a1 = toAxis(hi);
  const edges = d3.range(1, HIST_BINS).map((i) => fromAxis(a0 + ((a1 - a0) * i) / HIST_BINS));
  const bins = d3.bin().value(valueOf).domain([lo, hi]).thresholds(edges)(posts);
  for (const b of bins) b.logWidth = (a1 - a0) / HIST_BINS;
  return bins;
}

// The group's post titles, folded away under a summary line.
function postList(box, posts) {
  const details = box.append("details");
  details.append("summary").text(`The ${posts.length} posts`);
  const items = details.append("ol").selectAll("li").data(posts).join("li");
  items.append("span").text((p) => p.title);
  items.append("small").text((p) => ` · ${p.month}, #${p.rank}`);
}
