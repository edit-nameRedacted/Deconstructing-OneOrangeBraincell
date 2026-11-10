# Typical Orange Cats — D3 version

A row of "typical cats", one per group of r/OneOrangeBraincell heyday posts (top 40 a month, Apr–Aug 2022; 182 posts). The body shows what the group's cats look like; the tail carries the group's post data.

## Run it

Double-click **`Open viz.bat`** in this folder. A window opens running a small local server, and the page opens in your browser. Keep that window open while you use the page; close it to stop.

Or, from a terminal: `python viz_d3/serve.py` (from `Orange_Braincells`) or `python serve.py` (from here).

The page only works while the server is running; `localhost` is your own computer. Add `?check` to the address to run the parity checks; results print to the browser console.

`serve.py` always serves the `Orange_Braincells` folder (so the page can reach the data and the cat kit), tells the browser `.js` files are JavaScript (some Windows setups get this wrong with plain `python -m http.server`), and tries ports 8001–8009 if 8000 is busy.

The page needs a connection for D3 (jsDelivr) and the fonts (Google Fonts). Without the fonts it falls back to system fonts.

## Reading a cat

- **Body and coat:** the group's median share of white fur, plus white markings and a body type over-represented in the group (the typical-cat rule).
- **Eyes:** wide and wonky (the kit's `round` set) for the dumbest group in the view; big and sparkly for the cutest of the others; the rest are a fixed random pick.
- **Tail segments:** one per tail variable (upvotes and comments by default), each in its own shade from white to brown. A segment's length is where the group's median sits among all posts (its percentile). The longest tail in the view is drawn full length.
- **Tail stripes:** one per hand code (except the one the cats are grouped by), each in its own shade of orange or white, laid over the segments, base to tip. A stripe shows the group's standout value on that code — the one most over-represented against all posts, held by at least 3 posts — and is as thick as that value's share of the group. Click one for the code's full breakdown and **Chase this tail** to regroup by it. When a segment bristles, its stripes stretch out with the fur. The settings panel turns stripes on and off.
- **What a model thinks (robot button under a zoomed tail):** the same tail twice, side by side, with the hand-code stripes swapped for two models' readings. **Qwen 3.5 (9B)**, a language model that reads pictures, was shown each post's photos with its reply started ("This cat is so…" / "What a…"); its stripes are how much of its next-word odds went to cute, funny, calm, body and mind words. **SigLIP 2**, an image–caption matcher, compared each post's images against pairs of opposite captions (dumb/smart, cute/ugly, fat/skinny, derpy/dignified, blank/thinking, loaf/cat); its stripes are the group's percentile on each. "← Back to the human ratings" (or Esc) returns.
- **Example post:** the zoomed cat's panel shows a random photo or video from its group ("Show another" picks again).

Look settings live in `js/config.js`: `TAIL_RANGE` (which part of the white-to-brown ramp the segments use), `OUTLINE_WIDTH` (line weight for body and tail), `RING_MAX` (stripe thickness), `STRIPE_COLORS` (one shade per hand code).

**Bread (the loaf button in the heading):** a popup about one post, `wqtzrl`, titled "Bread": the only post the vision model said had no cat ("This is a capybara"). It shows how long the model struggled (three dot charts of time, reasoning length and second-guesses against every other post, from `oobc_archive/ai_opinion/reasoning_measures.csv`), the start of its reasoning, the rerun told "a human coder has confirmed there is a cat", what the commenters said (bread, mostly), and what the two internet-trained models make of it. Its words are in `index.html`; `js/bread.js` fills in the numbers and draws the charts from the data.

**The pointer is a neuron** (`js/neuronCursor.js`): the cell body is a hand-drawn neuron icon with its axon removed (`neuron_soma.svg`), centred on the pointer. A short axon grows from the gap and trails behind, ending in a branching arbor of terminals, pulled along by a d3-force simulation (linked nodes, a little repulsion to splay the terminals, a little droop), with a cap on how far it can stretch. The body turns so its gap faces the axon. Clicking sends a pulse down the axon; the cell body swells over anything clickable. It switches itself off on touch screens and when the system asks for reduced motion, and the settings panel has a toggle (remembered in this browser). Its shape and feel are the constants at the top of the file.

The page opens on an introduction to the subreddit and the project (the ⓘ button brings it back). Click a cat to zoom to its tail; the panel on the right describes the cat and lists its tail. Click a segment or stripe for details and **Chase this tail**, which regroups the posts by it.

## Files

| File | What it does |
| --- | --- |
| `Open viz.bat`, `serve.py` | Start the local server and open the page |
| `build_model_data.py` → `model_data.json` | Gathers Qwen's and SigLIP's readings of each post from `oobc_archive/ai_opinion`. Re-run if those change |
| `build_media_index.py` → `media_index.json` | Lists each post's photo or video in `oobc_media`, for the example pictures. Re-run if the posts or media change |
| `index.html` | The page's frame: heading, settings panel, row, zoom and details containers |
| `style.css` | Colours (light and dark), type and layout |
| `js/main.js` | Loads the inputs, connects the state to the views |
| `js/config.js` | Every setting, threshold and label, with what it controls |
| `js/text.js` | The explanatory sentences: what each category, value and tail measure means (edit freely) |
| `js/state.js` | The one state object; `set()` reports which keys changed |
| `js/data.js` | Groups the posts, ranks values, describes each cat in a view |
| `js/typicalCat.js` | The typical-cat rule |
| `js/color.js` | The white-to-brown OKLab ramp |
| `js/kit.js` | Loads `SVG/cat_kit.svg` and makes one cat from it, including its ears: the inside tinted pinker or darker and each ear's tuft scaled (per cat, from `earsFor` in `js/data.js`; ranges in `EARS`, `js/config.js`) |
| `js/tail.js` | Draws a tail: segments, stripes, bristles, labels (on a short tail, crowded labels fan out at an angle; `FAN` at the top of the file) |
| `js/blink.js` | Eyelids for every eye set: each cat blinks every 10–30 s at random, quick or slow at random, never two at once; a slow blink when the pointer rests on one (times in `BLINK`, `js/config.js`; off under reduced motion) |
| `js/gaze.js` | The "Seeking it" cat's pupils follow the pointer (the braincell): they drift from where they are drawn part of the way toward looking straight at it, so it keeps its half-lidded expression (`GAZE` in `js/config.js`, `who` says which cats; mouse only, off under reduced motion). Uses `SVG/eye_parts.json` to move the pupil without the lid line |
| `js/sequence.js` | Idle animations: now and then one cat in the row grooms or turns its head (one cat at a time, never during a blink, only cats on screen; `IDLE` in `js/config.js`). The traced frames play in the cat's coat colours, white bib and white muzzle, with its own eye set drawn on each frame from the sequence's eye track (position, size, tilt, gaze, lids). Hand fixes per sequence are in `SEQUENCES`, `js/config.js` |
| `sequence_preview.html` | Working page for checking the sequences: pick sequence, eye set, body, coat, white patches and ears; play or step through frames |
| `build_sequences.py` | Packs each sequence from `SVG/sheet_tools` into `sequences/<key>.json` (one file, ~1 MB gzipped); rerun after the frames or `eyes.json` change |
| `js/controls.js` | Category switcher and settings panel |
| `js/catView.js` | The row of cats (a D3 join) |
| `js/intro.js` | The opening screen (its text is in `index.html`) |
| `js/legend.js` | The key under the row of cats |
| `js/zoom.js` | The zoomed tail view |
| `js/models.js` | The two models' readings of a group, as tail stripes |
| `js/modelView.js` | The side-by-side model tails (robot button) |
| `js/details.js` | The panel beside a zoomed tail: the cat's overview, or a segment's or stripe's details, histogram, dot strip, posts and Chase this tail |
| `js/bread.js` | The Bread popup: numbers, picture, open and close |
| `js/neuronCursor.js`, `neuron_soma.svg` | The neuron pointer (d3-force), and its cell-body icon |
| `js/checks.js` | Parity checks, run with `?check` |

## How a change flows

Every control calls `store.set({...})`. `main.js` hears which keys changed and redraws only what depends on them:

| Changed | Redraws |
| --- | --- |
| `arrange`, `vars` or `stripes` | The cats are described again and the row re-joined; an open zoom is redrawn |
| `zoom` | The tail view opens (animated) or closes |
| `sel` | The chosen segment or stripe is marked and its details shown |
| `model` | The zoomed tail is swapped for the two model tails, or back |

## Inputs

| File | Holds |
| --- | --- |
| `oobc_archive/viz/oobc_viz_data.json` | Posts, hand-code groupings, tail variables (built by `build_viz_data.py`) |
| `SVG/cat_kit.svg` | The V2 kit (built by `SVG/V2/build_kit_v2.py`): bodies, white zones, eye sets, plus `data-coat`, `data-ears`, `data-cream`, `data-fluff`, `data-mouth`, `data-fur` (defaults: the hand-drawn V2 as drawn). If it is rebuilt, copy the tail points it prints into `ATTACH` in `js/tail.js` |
| `SVG/white_stages.json` | % white after each white zone, per body |
| `SVG/eye_parts.json` | Each eye set's opening and pupil, so pupils can look around in sequences and follow the pointer (built by `SVG/V2/eye_parts.py`; rerun it after rebuilding the kit) |
| `sequences/<key>.json` | The packed sequences (built by `build_sequences.py` from `SVG/sheet_tools/out/<sequence>/svg/`) |
| `SVG/tails/tail_geometry.json` | the two hand-drawn tails, as outlines and stations |

## Deploy

Live at https://oneorangebraincell.web.app (Firebase project `oneorangebraincell`). From the Orange_Braincells folder:

    python viz_d3/build_media_index.py   # only if posts or media changed
    python viz_d3/build_site.py          # copies what the page needs into site/
    npx firebase-tools deploy --only hosting

Photos and videos load from their original Reddit/imgur links, so they are not uploaded; only video posters and posts without a direct link are.
