/*
  controls.js — the category switcher in the heading and the tail settings panel.

    - The heading is a <select>: hand-code categories, then "Tails of …" for each tail variable.
      It is sized to its text so it reads as a heading rather than a form field.
    - The sliders button opens the settings panel: tail variables as checkbox chips (grouped by
      source), and which hand codes are drawn as tail stripes (one chip per code, in its colour).

  Controls only call store.set(); they never redraw anything themselves.
  Takes: the prepared data and the store. Gives back: setupControls(data, store), syncControls(data, state).
  Replaces: the control-building code, sizeTitle() and fixMix() in the prototype.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { SOURCES, STRIPE_COLORS } from "./config.js";
import { isTailArrangement } from "./data.js";

export function setupControls(data, store) {
  // ---- Category switcher (the heading) ----
  const switcher = d3.select("#arrange");
  switcher.append("optgroup").attr("label", "Hand codes")
    .selectAll("option").data(Object.entries(data.groupings)).join("option")
    .attr("value", ([key]) => key)
    .text(([, g]) => g.label);
  switcher.append("optgroup").attr("label", "Tails of…")
    .selectAll("option").data(Object.entries(data.tailvars)).join("option")
    .attr("value", ([key]) => "tail:" + key)
    .text(([, t]) => `Tails of ${t.label.toLowerCase()}`);

  switcher.on("change", (event) => {
    const arrange = event.target.value;
    store.set({ arrange, zoom: null, sel: null, model: false });
  });

  // Fonts load after the page; re-size the heading once they have.
  document.fonts?.ready.then(sizeTitle);

  // ---- Settings panel ----
  d3.select("#gear").on("click", (event) => {
    const panel = document.getElementById("settings");
    const opening = panel.hidden;
    panel.hidden = !opening;
    event.currentTarget.setAttribute("aria-expanded", String(opening));
  });

  // One group of chips per source (Reddit, Hand ratings, How the cats look).
  const groups = d3.select("#vars").selectAll(".vargroup")
    .data(SOURCES)
    .join("div").attr("class", "vargroup");
  groups.append("span").text(([, sourceLabel]) => sourceLabel);
  const chips = groups.append("div").attr("class", "chips")
    .selectAll("label")
    .data(([source]) => Object.entries(data.tailvars).filter(([, t]) => t.source === source))
    .join("label").attr("class", "chip");
  chips.append("input")
    .attr("type", "checkbox")
    .attr("value", ([key]) => key)
    .on("change", (event) => {
      const vars = new Set(store.state.vars);    // a new Set, so the store sees a change
      const key = event.target.value;
      if (event.target.checked) vars.add(key);
      else vars.delete(key);
      // Unticking the selected variable also clears the selection (its segment is gone).
      const sel = store.state.sel === key && !event.target.checked ? null : store.state.sel;
      store.set({ vars, sel });
    });
  chips.append("span").text(([, t]) => t.label);

  // ---- Stripes: one chip per hand code, with a dot in the stripe's colour ----
  const stripeChips = d3.select("#stripes").selectAll("label")
    .data(Object.entries(data.groupings))
    .join("label").attr("class", "chip");
  stripeChips.append("input")
    .attr("type", "checkbox")
    .attr("value", ([code]) => code)
    .on("change", (event) => {
      const stripes = new Set(store.state.stripes);
      const code = event.target.value;
      if (event.target.checked) stripes.add(code);
      else stripes.delete(code);
      // Turning off the selected stripe also clears the selection.
      const sel = store.state.sel === "code:" + code && !event.target.checked ? null : store.state.sel;
      store.set({ stripes, sel });
    });
  stripeChips.append("span").attr("class", "chip-dot").style("background", ([code]) => STRIPE_COLORS[code]);
  stripeChips.append("span").text(([, g]) => g.label);
}

// Make the controls show the current state (called after every change).
export function syncControls(data, state) {
  d3.select("#arrange").property("value", state.arrange);
  sizeTitle();

  d3.selectAll("#vars input").property("checked", function () { return state.vars.has(this.value); });

  // Stripe chips: ticked if switched on. The row's own grouping can't be a stripe (it would be
  // 100% on every cat), so its chip is greyed out while that grouping is shown.
  const shown = isTailArrangement(state.arrange) ? null : state.arrange;
  d3.selectAll("#stripes input")
    .property("checked", function () { return state.stripes.has(this.value); })
    .property("disabled", function () { return this.value === shown; });
  d3.selectAll("#stripes label")
    .classed("is-off", function () { return this.querySelector("input").value === shown; })
    .attr("title", function () { return this.querySelector("input").value === shown ? "This is what the cats are grouped by" : null; });
}

// Size the heading <select> to the width of its chosen text (plus room for the arrow), by
// measuring the same text in a hidden span with the same font.
function sizeTitle() {
  const select = document.getElementById("arrange");
  const measure = document.getElementById("measure");
  measure.textContent = select.options[select.selectedIndex]?.text || "";
  const box = measure.getBoundingClientRect();
  select.style.width = Math.ceil(box.width + box.height * 0.75) + "px";
}
