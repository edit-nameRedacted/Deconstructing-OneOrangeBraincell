/*
  legend.js — the key under the row of cats: what the tail's segments and rings stand for.

    Tail, base to tip: [swatch] Upvotes  [swatch] Comments   longer = ranks higher among all 182 posts
    Stripes, base to tip: [white] Braincell  [dark brown] Failure mode  …   each shows the group's standout value
    Wide, wonky eyes: the dumbest group here. Big sparkly eyes: the cutest.

  Rebuilt whenever the view changes (category, tail variables or stripes). Swatches use each segment's
  own fill, so they match the tails exactly.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";

export function renderLegend(container, view, data, state) {
  const legend = d3.select(container).html("");
  const segments = view.cats[0]?.segments ?? [];   // same variables and fills on every cat

  if (segments.length) {
    const row = legend.append("p").attr("class", "legend-row");
    row.append("span").attr("class", "legend-name").text("Tail, base to tip");
    const items = row.selectAll(".legend-item").data(segments).join("span").attr("class", "legend-item");
    items.append("span").attr("class", "swatch").style("background", (s) => s.fill);
    items.append("span").text((s) => s.label);
    row.append("span").attr("class", "legend-note")
      .text(`longer = the group's median ranks higher among all ${data.posts.length} posts`);
  }

  const stripes = view.cats[0]?.rings ?? [];      // same codes and colours on every cat
  if (stripes.length) {
    const row = legend.append("p").attr("class", "legend-row");
    row.append("span").attr("class", "legend-name").text("Stripes, base to tip");
    const items = row.selectAll(".legend-item.stripe").data(stripes).join("span").attr("class", "legend-item stripe");
    items.append("span").attr("class", "swatch stripe").style("background", (s) => s.color);
    items.append("span").text((s) => s.codeLabel);
    row.append("span").attr("class", "legend-note")
      .text("each shows what stands out about the group on that code; thicker = more of the group");
  }

  legend.append("p").attr("class", "legend-row")
    .append("span").attr("class", "legend-note")
    .text("Wide, wonky eyes: the dumbest group here. Big sparkly eyes: the cutest. Click a cat to look at its tail.");
}
