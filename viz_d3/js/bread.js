/*
  bread.js — the "Bread" popup: one post (wqtzrl, titled "Bread"), and how each source read it.

  The loaf button in the heading opens it. The words are in index.html; this file
    - fills the numbers marked data-fill from the page's own data (post, look, models), so they
      always match what the cats and tails show;
    - shows the post's picture (from media_index.json, if it was loaded);
    - draws three small dot charts of how hard the vision model worked on every post (time,
      reasoning length, second-guesses; from reasoning_measures.csv), with Bread marked;
    - opens and closes the popup: ✕, Esc, or a click outside the card. While it is open the page
      behind it is made inert, so Tab stays inside the popup.

  Takes: the prepared data and the models (models may be null).
  Gives back: setupBread({ data, models }).
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { PATHS, mediaUrl } from "./config.js";

const BREAD_ID = "wqtzrl";

export function setupBread({ data, models }) {
  const popup = document.getElementById("bread");
  const button = document.getElementById("bread-btn");
  const closeButton = document.getElementById("bread-close");
  const page = document.querySelector(".wrap");
  const post = data.posts.find((p) => p.id === BREAD_ID);
  if (!post) { button.hidden = true; return; }      // Bread isn't in this data: no button

  fill(popup, post, data, models);
  // The reasoning measures are only needed here, so they load in the background; if the file is
  // missing, the charts and their sentence are simply left out.
  const measures = d3.csv(PATHS.reasoning, d3.autoType).catch(() => null);

  async function open() {
    popup.hidden = false;
    page.inert = true;
    popup.scrollTop = 0;
    closeButton.focus({ preventScroll: true });
    drawCharts(popup, await measures, data.media);       // drawn on every open, to fit the card's width
  }
  function close() {
    popup.hidden = true;
    page.inert = false;
    button.focus({ preventScroll: true });
  }

  button.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  // A click on the dimmed backdrop (outside the card) closes it.
  popup.addEventListener("click", (event) => { if (event.target === popup) close(); });
  // Esc closes it; stopPropagation keeps the page's own Esc (close the zoom) out of it.
  popup.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.stopPropagation(); close(); }
  });
}

// ---- The numbers and the picture ----
function fill(popup, post, data, models) {
  const slot = (name) => popup.querySelector(`[data-fill="${name}"]`);
  const month = d3.timeFormat("%B %Y")(d3.timeParse("%Y-%m")(post.month));
  const n = d3.format(",");

  slot("meta").textContent =
    `${month} · ${ordinalRank(post.rank)} that month · ${n(post.vals.score)} upvotes · ${n(post.vals.comments)} comments`;
  slot("kg").textContent = post.traits.kg;

  // The picture, if the media index was loaded.
  const media = data.media?.[BREAD_ID];
  const img = popup.querySelector("#bread-img");
  if (media?.type === "image") img.src = mediaUrl(media.src);
  else popup.querySelector("#bread-figure").hidden = true;

  // The two internet-trained models (the robot button's), if their readings were loaded.
  const modelsText = slot("models");
  const qwen = models?.qwen.posts[BREAD_ID];
  const siglip = models?.siglip.posts[BREAD_ID];
  if (!qwen || !siglip) {                               // no readings: drop the section and its heading
    modelsText.hidden = true;
    modelsText.previousElementSibling.hidden = true;
    return;
  }
  const openings = Object.entries(qwen.words);          // { "This cat is so": [three words], … }
  const rankOf = (score) => {                           // 1 = leans furthest toward the first caption
    const all = data.posts.map((p) => models.siglip.posts[p.id]?.[score]).filter((v) => v != null);
    return { rank: all.filter((v) => v > siglip[score]).length + 1, of: all.length };
  };
  const loaf = rankOf("loaf");
  const fat = rankOf("fat");
  // Body words: Bread's share, its rank among all posts, and the average (most posts get none).
  const bodies = data.posts.map((p) => models.qwen.posts[p.id]?.body).filter((v) => v != null);
  const bodyRank = bodies.filter((v) => v > qwen.body).length + 1;
  modelsText.textContent =
    `The same Qwen model, shown the picture and asked only for the next word, ` +
    openings.map(([start, words]) => `finished “${start}…” with ${words.slice(0, 3).map((w) => `“${w}”`).join(", ")}`).join(", and ") +
    `. ${pct(qwen.body)} of its next-word odds went to body words, ` +
    `${bodyRank === 1 ? "the most" : `the ${ordinalRank(bodyRank)} most`} of any post (the average is ${pct(d3.mean(bodies))}). ` +
    `SigLIP, weighing the picture against “a loaf of bread” and “a cat”, ranks Bread ` +
    `${loaf.rank === 1 ? "the most" : `the ${ordinalRank(loaf.rank)} most`} loaf-like of all ${loaf.of} posts, ` +
    `and the ${ordinalRank(fat.rank)} fattest.`;
}

// ---- How hard the vision model worked: three dot charts, Bread marked ----
// One row per measure. Each dot is a post; dots that land on the same spot stack upward, so the
// chart is a histogram made of posts. Bread is the large orange dot; the dashed line is the median.
const DOT = 4.6;                       // dot spacing (and column width), px

function drawCharts(popup, rows, media) {
  const box = d3.select(popup).select("#bread-charts").html("");
  const note = popup.querySelector('[data-fill="charts-note"]');
  const lead = popup.querySelector('[data-fill="n-posts"]');
  if (!rows) { box.style("display", "none"); note.hidden = true; lead.textContent = "182"; return; }

  // Reasoning length and second-guesses only exist for posts whose reasoning fit under the cap.
  const complete = rows.filter((r) => r.reasoning_overflowed === 0);
  const capped = rows.length - complete.length;
  lead.textContent = rows.length;
  const n = d3.format(",");

  drawStrip(box, {
    title: "Time to answer",
    rows, value: (r) => r.model_seconds, format: (v) => `${Math.round(v)} s`,
    rank: (bread, values) => {
      // Videos are read as four frames, and a reply that ran past the reasoning cap was asked
      // twice, so the fairest comparison for Bread (one photo) is other single photos with
      // complete reasoning.
      const singles = complete
        .filter((r) => media?.[r.post_id]?.type === "image" && media[r.post_id].count === 1)
        .map((r) => r.model_seconds);
      const slower = (list) => Math.round(100 * list.filter((v) => v < bread).length / list.length);
      return `slower than ${slower(values)}% of all ${values.length} posts` +
        (singles.length ? `, and than ${slower(singles)}% of the ${singles.length} single photos` : "");
    },
  });
  drawStrip(box, {
    title: "Length of its reasoning",
    rows: complete, value: (r) => r.reasoning_chars, format: (v) => `${n(Math.round(v))} characters`,
    tick: (v) => d3.format("~s")(v),
    rank: (bread, values) => placeText(bread, values, "longest"),
  });
  drawStrip(box, {
    title: "Second-guesses",
    rows: complete, value: (r) => r.second_guesses, format: (v) => `${Math.round(v)}`,
    rank: (bread, values) => placeText(bread, values, "most"),
  });

  note.textContent =
    `Each dot is one post. The tall stack near 90 s is videos, which the model reads as four ` +
    `frames; “single photos” are posts of one image whose reasoning was complete. Second-guesses count the words the model uses to doubt itself: ` +
    `“wait”, “actually”, “re-read”, “re-evaluate”, “look again”, “hmm”, “on second…”. ` +
    `Reasoning length and second-guesses leave out the ${capped} posts whose reasoning ran past ` +
    `the 6,000-token limit and were re-asked without it, so they are out of ${complete.length}.`;
}

// "the most of any post; next is 42", or "the 2nd longest of 154 posts".
function placeText(bread, values, word) {
  const higher = values.filter((v) => v > bread).length;
  if (higher === 0) {
    const next = d3.max(values.filter((v) => v < bread));
    return `the ${word} of any post; next is ${d3.format(",")(next)}`;
  }
  return `the ${ordinalRank(higher + 1)} ${word} of ${values.length} posts`;
}

function drawStrip(box, { title, rows, value, format, tick, rank }) {
  const breadRow = rows.find((r) => r.post_id === BREAD_ID);
  const values = rows.map(value);
  if (!breadRow) return;
  const bread = value(breadRow);
  const median = d3.median(values);

  const block = box.append("div").attr("class", "bread-strip");
  const head = block.append("p").attr("class", "bread-strip-head");
  head.append("span").attr("class", "bread-strip-title").text(title);
  head.append("span").text(` Bread ${format(bread)} · median ${format(median)} · ${rank(bread, values)}`);

  // Lay out the dots: column = rounded x position; each post stacks on the ones before it.
  const width = Math.max(260, block.node().clientWidth);
  const x = d3.scaleLinear().domain([0, d3.max(values)]).nice().range([DOT, width - DOT]);
  const stacks = new Map();
  const dots = rows
    .map((r) => ({ id: r.post_id, v: value(r) }))
    .sort((a, b) => (a.id === BREAD_ID) - (b.id === BREAD_ID))   // Bread last, so it sits on top
    .map((d) => {
      const col = Math.round(x(d.v) / DOT);
      const k = stacks.get(col) ?? 0;
      stacks.set(col, k + 1);
      return { ...d, cx: col * DOT, k };
    });
  const tallest = d3.max(stacks.values());
  const top = 18, axisH = 20;                                   // room for Bread's label and the axis
  const height = top + tallest * DOT + axisH;
  const base = top + tallest * DOT;

  const svg = block.append("svg").attr("width", width).attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`).attr("aria-hidden", "true");
  svg.append("line").attr("class", "bread-median")
    .attr("x1", x(median)).attr("x2", x(median)).attr("y1", top - 4).attr("y2", base);
  svg.append("g").selectAll("circle").data(dots).join("circle")
    .attr("class", (d) => (d.id === BREAD_ID ? "bread-dot is-bread" : "bread-dot"))
    .attr("cx", (d) => d.cx)
    .attr("cy", (d) => base - (d.k + 0.5) * DOT)
    .attr("r", (d) => (d.id === BREAD_ID ? 4 : DOT / 2 - 0.4));
  const b = dots.find((d) => d.id === BREAD_ID);
  svg.append("text").attr("class", "bread-dot-label")
    .attr("x", Math.min(b.cx, width - 20)).attr("y", base - (b.k + 0.5) * DOT - 8)
    .attr("text-anchor", b.cx > width - 40 ? "end" : "middle").text("Bread");
  svg.append("g").attr("class", "bread-axis").attr("transform", `translate(0,${base + 2})`)
    .call(d3.axisBottom(x).ticks(5).tickSize(3).tickFormat(tick ?? d3.format("~s")))
    .call((g) => g.select(".domain").remove());
}

function pct(share) { return `${Math.round(share * 100)}%`; }

// 1 → "1st"; for a rank, unlike config.ordinal's percentile wording.
function ordinalRank(k) {
  const s = ["th", "st", "nd", "rd"], v = k % 100;
  return k + (s[(v - 20) % 10] || s[v] || s[0]);
}
