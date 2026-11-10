/*
  config.js — every fixed setting and label the page uses, in one place.

  Nothing here is computed from the data. If a number carries a design decision
  (a threshold, a size, a duration), it lives here with a comment saying what it
  controls, so the other files can refer to it by name.

  Replaces: the constants at the top of the prototype's script (viz/viz_template.html)
  and the tail module's constants (viz/cat_tail_viz_template.js).
*/

// ---- Where the inputs live, relative to viz_d3/index.html ----
// The page is served from the Orange_Braincells folder (python -m http.server),
// so "../" reaches the data and the cat kit.
export const PATHS = {
  data: "../oobc_archive/viz/oobc_viz_data.json",
  kit: "../SVG/cat_kit.svg",
  whiteStages: "../SVG/white_stages.json",
  tailGeometry: "../SVG/tails/tail_geometry.json",
  // Each eye set's opening and pupil (built by SVG/V2/eye_parts.py), so sequence eyes can look around.
  eyeParts: "../SVG/eye_parts.json",
  // The animated sequences, one file each (built by build_sequences.py from SVG/sheet_tools).
  sequences: "sequences/",
  // Each post's photo or video, for the example pictures (built by build_media_index.py).
  // Optional: without it the page just shows no examples.
  mediaIndex: "media_index.json",
  // Media paths in the index start at the Orange_Braincells folder; from the page that is "../".
  mediaRoot: "../",
  // The two models' readings of each post (built by build_model_data.py). Optional: without it
  // the robot button is hidden.
  modelData: "model_data.json",
  // How the trait model behaved on each post: time, reasoning length, second-guesses (written by
  // oobc_archive/ai_opinion/reasoning_measures.py). Read only by the Bread popup; optional.
  reasoning: "../oobc_archive/ai_opinion/reasoning_measures.csv",
};

// A media path from the index as a URL: most are the posts' original Reddit/imgur links, used as is;
// the rest are local files under the Orange_Braincells folder.
export const mediaUrl = (path) => (/^https?:\/\//.test(path) ? path : PATHS.mediaRoot + path);

// ---- What the page shows when it first opens ----
export const DEFAULTS = {
  arrange: "braincell",          // the category shown as the row of cats
  vars: ["score", "comments"],   // tail variables, base to tip
  stripes: ["braincell", "failure", "inferred", "anthro", "dumb", "cute"],  // hand codes drawn as tail stripes
};

// ---- The typical cat (AC's rule, 2026-10-27) ----
// White zones, in the order they are switched on as a cat gets whiter.
// white_stages.json gives the cumulative % white after each of these, per body.
export const ZONES = ["chin", "locket", "muzzle", "bib", "blaze", "belly", "paws", "stockings", "face", "body"];
export const BODIES_OTHER = ["kitten", "slender", "chunky"]; // "typical" is the fallback body
export const TYPICAL = {
  MIN_CATS: 3,          // a trait needs at least this many cats in the group to count
  ZONE_LIFT: 1.3,       // an extra white zone must be at least 1.3x as common as across all posts...
  ZONE_SHARE: 0.3,      // ...and present on at least 30% of the group
  BODY_LIFT: 1.5,       // a non-typical body must be at least 1.5x as common as across all posts...
  BODY_SHARE: 0.25,     // ...and at least 25% of the group
  STRIPES_SHARE: 0.5,   // stripes are drawn if at least half the group has them
  SMALL_GROUP: 10,      // groups under 10 cats are "small": their typical cat is a loose guess
};

// ---- Eyes (AC's rule) ----
// The group with the highest mean Dumbness in a view gets wide, wonky eyes; the cutest of the
// other groups gets big shiny eyes. (If one group is both the dumbest and the cutest, the dumb
// eyes win and the shiny eyes go to the next-cutest, so both markers always show.)
// Every other cat gets one of the remaining five sets, picked by a stable hash.
export const EYES_DUMB = "round";
export const EYES_CUTE = "big-shiny";
export const EYES_OTHER = ["original", "almond", "slit", "half-lidded", "squint"];
// Eye sets that always go to one group, whatever its scores: { view (row) key: { group value: eye set } }.
// These win over the dumb and cute eyes (those then go to the next-dumbest / next-cutest group), and no
// other cat in that view is given the same set.
export const EYES_FIXED = {
  braincell: { "Seeking it": "half-lidded" },     // the unimpressed, still-looking eyes
};

// ---- Eyes follow the pointer (gaze.js) ----
// Only the cats named in GAZE.who follow it: { view (row) key: [group values] }. The pointer is the
// braincell, and only the cat still seeking it watches where it goes.
// Its pupils drift from where they are drawn toward the pointer, part of the way, so it keeps its
// own expression. Mouse only (no pointer to follow on touch); off under prefers-reduced-motion.
export const GAZE = {
  who: { braincell: ["Seeking it"] },
  amount: 0.45,     // how far toward "looking straight at the pointer" a pupil goes (0 never moves, 1 all the way)
  reach: 280,       // pixels: a pointer this far from an eye or further gets the full look; nearer, less
  ease: 140,        // milliseconds for a pupil to cover most of the way to where it should look
  vertical: 0.7,    // up-down travel as a share of side-to-side (lids sit close above and below)
};

// ---- Ears ----
// Each cat's ear insides and tufts vary a little, picked by hashing the cat, so the same cat always has the same
// ears (in the row, zoomed in and pouncing). The inside of the ear is the coat scheme's ear colour mixed
// toward pinker or darker; each ear's tuft is scaled from its root and kept inside the ear.
export const EARS = {
  pinker: "#EFA3A6", darker: "#7A4B33",
  tone: [-0.45, 0.6],     // -0.45 = 45% of the way to darker … 0.6 = 60% of the way to pinker
  tuft: [0.7, 1.35],      // tuft size against the drawing
  tuftDiffer: 0.08,       // how much a cat's two tufts may differ from each other
};

// ---- Drawing the cat ----
export const TILT = 0;            // degrees clockwise. The V2 cats face the viewer and already sit upright (was 5 for the 3/4-view kit)
export const TAIL_TYPE = "long";  // which of AC's two tail drawings to use
export const TAIL_SIZE = 1.6;     // tail scale against the body; larger than life so the data reads
export const TAIL_MIN = 0.3;      // the shortest tail drawn, as a fraction of the full drawing
export const ROW_PAD = 6;         // kit units of space around the row's shared frame

// ---- Tail stripes: the other hand codes (AC, 2026-11-02) ----
// One stripe per hand code (except the one the row is grouped by), overlaid on the segments and
// evenly spaced along the tail. Each shows the group's standout value for that code; its thickness
// is that value's share of the group: a 100% share is RING_MAX of the full tail's length.
// Each code has its own shade of orange or white (AC, 2026-11-02), spaced out in lightness from
// white to near-black brown so neighbouring stripes, and the light and rust segments under them,
// These stay brighter than the cat palette on purpose (AC, 2026-11-03): tails may leave the body
// palette where that keeps them readable. The segments and rings do use the palette.
// stay apart. A thin outline on every stripe keeps the palest and darkest ones readable too.
export const STRIPE_COLORS = {
  braincell: "#FFFFFF",   // white
  failure: "#2A1206",     // near-black brown
  inferred: "#FFB000",    // amber
  anthro: "#6B2E0E",      // chocolate
  dumb: "#F26B0F",        // bright orange
  cute: "#C2390B",        // red-orange
};
// The model tails use the same six shades, in this order, for their stripes.
export const MODEL_STRIPE_SHADES = ["#FFFFFF", "#FFB000", "#F26B0F", "#C2390B", "#6B2E0E", "#2A1206"];

export const RING_MAX = 0.12;
export const RING_EMPTY_DASH = "3 2"; // dash pattern for a value with no posts in the group

// ---- Zoom to the tail ----
export const ZOOM_MS = 650;       // length of the zoom transition
export const ZOOM_LABEL_PX = 14;  // tail labels are drawn at this many screen pixels once zoomed

// ---- The tail's colours: white -> orange -> brown, one shade per segment ----
// Interpolated in OKLab (see color.js), as in the prototype.
// The stops are swatches from the cat palette (2026-11-03), light to dark.
export const TAIL_STOPS = ["#F1E7DB", "#FCD9AF", "#F1B96F", "#DB8C3F", "#C37825", "#9A662D", "#6B3B13"];
// Which part of that ramp the segments use (0 = the white end, 1 = the brown end). Keeping off both
// ends puts more orange in the tails: two segments get a light orange and a rust instead of
// near-white and dark brown. The rings are dark brown (--tail-ring in style.css) to stand out.
export const TAIL_RANGE = [0.22, 0.8];

// ---- Line weight ----
// The kit's body outline is drawn as filled shapes about 3.4 units thick. The page slims it to
// OUTLINE_WIDTH with an SVG "erode" filter (kit.js), and draws the tail's outline at the same width.
const KIT_OUTLINE = 3.4;   // the V2 kit's median line width (SVG/V2/build_kit_v2.py)
export const OUTLINE_WIDTH = 2.6;
export const OUTLINE_ERODE = (KIT_OUTLINE - OUTLINE_WIDTH) / 2;   // taken off each side of the line

// ---- Tail variables: how each is read and written ----
// The settings panel groups the tail variables by where they come from.
export const SOURCES = [
  ["post", "Reddit"],
  ["ac", "Hand ratings"],
  ["look", "How the cats look"],
];
// Rank in month is "better" when lower (1 = top of the month), so its segment is inverted:
// the nearer the top, the longer the segment.
export const INVERT = { rank: true };
// Unit written after a value, per variable.
export const UNIT = {
  score: "", comments: "", score_rel: " per 1k subscribers", talk: "", crossposts: "", awards: "",
  rank: "", ac_dumb: " of 5", ac_cute: " of 5", look_white: "% white", look_kg: " kg",
};
// Decimal places, per variable (anything not listed is a whole number).
export const DIGITS = { talk: 2, score_rel: 1, look_kg: 1, ac_dumb: 1, ac_cute: 1 };

// ---- Labels ----
// The 1–5 rating categories read better with their name in front ("Dumbness 3", not "3").
export function labelFor(categoryKey, value) {
  if (categoryKey === "dumb") return `Dumbness ${value}`;
  if (categoryKey === "cute") return `Cuteness ${value}`;
  return value;
}

// Format a value of a tail variable for display, e.g. 3785.5 -> "3,786", 1.705 -> "1.71".
export function formatValue(varKey, value) {
  if (value == null) return "–";
  if (DIGITS[varKey]) return value.toFixed(DIGITS[varKey]);
  return Math.round(value).toLocaleString("en-US");
}

// 1 -> "1st", 2 -> "2nd", 11 -> "11th", 23 -> "23rd".
export function ordinal(n) {
  if (n % 100 >= 11 && n % 100 <= 13) return n + "th";
  return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
}

// ---- Blinking (blink.js) ----
// Times in ms. The lid sizes are shares of the eye's height.
export const BLINK = {
  every: [10000, 30000],          // each cat blinks once in this many ms, picked at random each time
  slowShare: 0.5,                 // share of blinks that are slow; the rest are quick
  gap: 300,                       // ms between one cat's blink ending and another's starting (never two at once)
  quick: { close: 70, hold: 40, open: 120 },
  slow: { close: 450, hold: 650, open: 700 },   // the slow "I trust you" blink
  slowOnHover: true,              // a slow blink when the pointer rests on a cat (skipped if another cat is mid-blink)
  pad: 0.18,                      // how far the lids' oval reaches past the eye white
  curve: 0.28,                    // how much the shut eye's line curves
  shut: 0.25,                     // where the shut line sits: 0 = middle of the eye, 1 = its bottom
  line: 0.13, lineMin: 1.2,       // lid line width
};

// ---- Animated sequences (sequence.js) ----
// Frames drawn by Wan 2.2 between hand-drawn keyframes, traced without eyes (SVG/sheet_tools), packed by
// build_sequences.py; the cat's own eye set is drawn on top from the sequence's eye track. `fix` corrects
// the track by hand:
//   hide:  frames where an eye is covered (by a paw), per side ("left" = the viewer's left)
//   lid:   frames whose lid value to replace (0 open .. 1 shut)
//   drawnShut: [first, last] frames that show the drawing's own shut eyes instead of kit eyes. For long
//          shut runs, where the eye track can only guess (it's interpolated, so eyes would slide around)
// `weight`: how often this sequence is picked when a cat plays one idly.
export const SEQUENCES = {
  grooming: {
    weight: 1,
    fix: {
      drawnShut: [38, 50],            // eyes shut while licking the paw (the paw also covers one eye here)
      lid: { 59: 0, 66: 0 },          // blinks Wan made up between keyframes (not in the drawings)
    },
  },
  headTurn: {
    weight: 1,
    fix: {},
  },
};

// Cats in the row play a sequence now and then, by themselves: one cat at a time, never while a cat is
// blinking, only cats on screen, and not at all under prefers-reduced-motion. Times in ms.
export const IDLE = {
  first: [6000, 12000],           // the first sequence starts this long after the row is drawn
  every: [20000, 40000],          // then one every this long, picked at random each time (counted from the last one's end)
  repeats: 1,                     // times a cat plays its sequence through before going back to sitting
};
