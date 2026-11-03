/*
  main.js — loads the inputs, then connects the state to the views.

  The flow:
    0. Set up the opening screen, which covers the page while the rest loads and draws.
  1. Load the four inputs at once (data, cat kit, white stages, tail geometry).
    2. Build the controls; every control calls store.set().
    3. On every change, update() decides what to redraw from which state keys changed:
         arrange / vars / stripes -> describe the view again and re-join the row
         zoom                  -> open or close the tail view
         sel                   -> mark the segment or ring, show its details
         model                 -> swap the zoomed tail for the two model tails, or back
    4. Esc and the back button close the zoom.
  With ?check in the address, the parity checks run too (see checks.js).
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { PATHS, DEFAULTS } from "./config.js";
import { prepareData, arrangement, describeView, isTailArrangement } from "./data.js";
import { loadKit } from "./kit.js";
import { prepareTailGeometry } from "./tail.js";
import { createStore } from "./state.js";
import { setupControls, syncControls } from "./controls.js";
import { renderRow } from "./catView.js";
import { openZoom, closeZoom } from "./zoom.js";
import { showOverview, showDetails, hideDetails } from "./details.js";
import { renderLegend } from "./legend.js";
import { setupIntro } from "./intro.js";
import { CATEGORY_TEXT, TAILS_OF_TEXT } from "./text.js";
import { runChecks } from "./checks.js";
import { prepareModels } from "./models.js";
import { showModelView, hideModelView } from "./modelView.js";
import { setupNeuronCursor } from "./neuronCursor.js";
import { setupBread } from "./bread.js";

// ---- 0. The opening screen (shown while everything below loads and draws behind it) ----
setupIntro();
setupNeuronCursor();

// ---- 1. Inputs ----
// d3.json and d3.xml fetch over HTTP, which is why the page must be served (python -m http.server)
// rather than opened as a file.
const [raw, kit, stages, rawGeometry] = await Promise.all([
  d3.json(PATHS.data),
  loadKit(PATHS.kit),
  d3.json(PATHS.whiteStages),
  d3.json(PATHS.tailGeometry),
]);
const data = prepareData(raw, stages.white_pct_cumulative);
// The example pictures are optional: if media_index.json is missing, carry on without them.
data.media = await d3.json(PATHS.mediaIndex).catch(() => ({}));
const geometry = prepareTailGeometry(rawGeometry);
// The two models' readings are optional too: without model_data.json the robot button stays hidden.
const models = prepareModels(await d3.json(PATHS.modelData).catch(() => null), data.posts);
document.getElementById("robot").hidden = !models;
// The "Bread" popup (loaf button in the heading) fills its numbers from the same data.
setupBread({ data, models });

// ---- 2. State and controls ----
const store = createStore({
  arrange: DEFAULTS.arrange,
  vars: new Set(DEFAULTS.vars),
  stripes: new Set(DEFAULTS.stripes),
  zoom: null,
  sel: null,
  model: false,             // true while the two model tails are shown in place of the zoomed tail
});
setupControls(data, store);

// What is currently drawn.
let view = null;          // from describeView: the arrangement and every cat's look, tail and eyes
let rowViewBox = null;    // the row's shared frame; the zoom starts from it
let zoomTail = null;      // the zoomed tail's controller, while the tail view is open
let lastZoom = null;      // which cat was zoomed, so focus can return to it

// ---- 3. Redrawing ----
function update(state, changed) {
  const viewChanged = changed.has("arrange") || changed.has("vars") || changed.has("stripes");

  if (viewChanged) {
    syncControls(data, state);
    view = describeView(data, arrangement(data, state.arrange), state);
    rowViewBox = renderRow(document.getElementById("row"), view, kit, geometry, openCat);
    document.getElementById("lede").textContent = ledeFor(state.arrange);
    renderLegend(document.getElementById("legend"), view, data, state);
  }

  if (state.zoom == null) {
    // The row is showing.
    // Back to the row: focus returns to the cat that was open, or to the first cat when the
    // row itself changed (after Chase this tail).
    if (changed.has("zoom")) closeZoom(changed.has("arrange") ? 0 : lastZoom);
    zoomTail = null;
    hideDetails();
  } else if (changed.has("zoom") || viewChanged) {
    // Open the tail view (animated only when it is newly opened, not when settings change).
    zoomTail = openZoom({
      view, index: state.zoom, selectedKey: state.sel, animate: changed.has("zoom"),
      rowViewBox, kit, geometry,
      onSelect: (item) => store.set({ sel: item.key }),
    });
    showSelected(state);
  } else if (changed.has("sel")) {
    zoomTail?.select(state.sel);
    showSelected(state);
  }

  // The model view sits on top of the zoomed tail: drawn when it is switched on, or redrawn when
  // the cat or the settings change while it is open.
  if (state.zoom != null && state.model) {
    if (changed.has("model") || changed.has("zoom") || viewChanged) {
      showModelView({ view, index: state.zoom, rowViewBox, kit, geometry, models, focusBack: changed.has("model") });
    }
  } else {
    hideModelView();
    if (changed.has("model") && state.zoom != null) document.getElementById("robot").focus({ preventScroll: true });
  }
  lastZoom = state.zoom;
}

// The panel beside the zoomed tail: the selected segment or ring, or the cat's overview.
function showSelected(state) {
  const cat = view.cats[state.zoom];
  const onPick = (key) => store.set({ sel: key });
  if (!state.sel) {
    showOverview({ data, view, cat, state, onPick });
    return;
  }
  showDetails({
    data, state, cat, onPick,
    selectedKey: state.sel,
    onChase: (arrange) => store.set({ arrange, zoom: null, sel: null, model: false }),
  });
}

// The sentence under the heading: what the current grouping means (text.js).
function ledeFor(arrange) {
  if (isTailArrangement(arrange)) return TAILS_OF_TEXT(data.tailvars[arrange.slice(5)].label);
  return CATEGORY_TEXT[arrange]?.lede ?? "";
}

// A click on a cat in the row (key = the clicked segment or ring, or null for the cat itself).
function openCat(index, key) {
  store.set({ zoom: index, sel: key });
}

store.subscribe(update);

// ---- 4. Leaving the tail view ----
d3.select("#back").on("click", () => store.set({ zoom: null, sel: null, model: false }));
// Esc steps back one level: from the model view to the human ratings, then from the tail to the row.
d3.select(document).on("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (store.state.model) store.set({ model: false });
  else if (store.state.zoom != null) store.set({ zoom: null, sel: null });
});

// ---- 5. The model view: the robot button opens it, "Back to the human ratings" closes it ----
d3.select("#robot").on("click", () => store.set({ model: true }));
d3.select("#model-back").on("click", () => store.set({ model: false }));

// First draw: tell update() that everything changed.
update(store.state, new Set(["arrange", "vars", "stripes"]));

if (new URLSearchParams(location.search).has("check")) runChecks(data);
