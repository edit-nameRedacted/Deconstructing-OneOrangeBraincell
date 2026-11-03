/*
  modelView.js — "What a model trained on the internet thinks of this group".

  Opened by the robot button under a zoomed tail. It replaces the zoomed view with two tails side
  by side, one per model (Qwen, SigLIP; see models.js). Each tail keeps the group's upvote and
  comment segments; its stripes show that model's reading instead of the hand codes. Above each
  tail: the model's name, what kind of model it is and what it was asked to do; below it: every
  stripe's value and how the model lines up with the hand ratings.
  "← Back to the human ratings" at the top returns to the normal zoomed tail.

  Takes: the view, the zoomed cat's index, the row's viewBox, kit, geometry and the models.
  Gives back: showModelView(...), hideModelView().
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { cloneCat, tilt, bodyOf } from "./kit.js";
import { drawTail } from "./tail.js";
import { tailOptions } from "./catView.js";
import { frameForTail } from "./zoom.js";
import { modelStripes, qwenTopWords } from "./models.js";
import { MODEL_TEXT } from "./text.js";

const $ = (id) => document.getElementById(id);

export function hideModelView() {
  $("model-view").hidden = true;
  $("zoom-head").hidden = false;
  $("zoom-body").hidden = false;
}

export function showModelView({ view, index, rowViewBox, kit, geometry, models, focusBack }) {
  const cat = view.cats[index];
  $("zoom-head").hidden = true;
  $("zoom-body").hidden = true;
  $("model-view").hidden = false;
  $("model-title").textContent = `What two models trained on the internet think of “${cat.group.label}”`;
  $("model-n").textContent = `${cat.group.posts.length} posts`;

  const columns = d3.select("#model-columns").html("");
  for (const which of ["qwen", "siglip"]) {
    const text = MODEL_TEXT[which];
    const stripes = modelStripes(models, cat.group, which);
    const col = columns.append("article").attr("class", "model-col");

    // What the model is, and what it did.
    const head = col.append("header").attr("class", "model-head");
    head.append("h3").text(text.name);
    head.append("p").attr("class", "model-kind").text(text.kind);
    col.append("p").attr("class", "model-how").text(text.how);

    // The tail: the same cat, with this model's stripes.
    const stage = col.append("div").attr("class", "model-stage").node();
    const values = drawModelTail(stage, { ...cat, rings: stripes }, view, rowViewBox, kit, geometry,
      (key) => highlightRow(col, key));

    // Every stripe's value, as a list; hovering or clicking a row marks its stripe on the tail.
    const list = col.append("ul").attr("class", "model-list");
    const rows = list.selectAll("li").data(stripes).join("li").attr("data-key", (s) => s.key);
    rows.append("span").attr("class", "swatch stripe").style("background", (s) => s.color);
    rows.append("span").attr("class", "model-label").text((s) => s.label);
    rows.append("span").attr("class", "model-value").text((s) => s.valueText);
    rows.on("click", (event, s) => { values.select(s.key); highlightRow(col, s.key); });

    if (which === "qwen") {
      const top = qwenTopWords(models, cat.group);
      const answers = cat.group.posts.filter((p) => models.qwen.posts[p.id]).length * models.qwen.openings.length;
      col.append("p").attr("class", "model-words")
        .text(`Its first-choice word, over both openings (${answers} answers): ${top.map(([w, n]) => `${w} ${n}`).join(", ")}.`);
    }
    col.append("p").attr("class", "hint").text(text.compare);
  }

  if (focusBack) $("model-back").focus({ preventScroll: true });
}

// One zoomed model tail: a copy of the cat, framed on its tail, body faded (no animation).
function drawModelTail(stage, cat, view, rowViewBox, kit, geometry, onPick) {
  const svg = cloneCat(kit, cat.look, cat.eyes);
  svg.removeAttribute("aria-hidden");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", `Tail of ${cat.group.label}, with a model's stripes`);
  svg.setAttribute("viewBox", rowViewBox.join(" "));
  stage.append(svg);
  tilt(svg);
  let tail = null;
  tail = drawTail(svg, tailOptions(cat, view, geometry, {
    labels: true,
    interactive: true,
    onSelect: (item) => { tail.select(item.key); onPick(item.key); },
  }));
  const frame = frameForTail(svg, stage);
  bodyOf(svg).classList.add("faded");
  svg.setAttribute("viewBox", frame.map((v) => v.toFixed(2)).join(" "));
  return tail;
}

function highlightRow(col, key) {
  col.selectAll(".model-list li").classed("is-on", function () { return this.dataset.key === key; });
}
