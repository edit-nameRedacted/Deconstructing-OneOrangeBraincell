# Sheet tools: from a drawing sheet to layered, registered SVG frames

Replaces the by-hand Illustrator steps (Image Trace, expand, sort shapes into layers, line things up) for
sheets of cat drawings like the head-turn and grooming sheets. Needs Python with `opencv-python`, `numpy`,
`scikit-image`, `vtracer` and `svgelements`.

| Script | Does |
| --- | --- |
| `trace_layers.py IMG... --out DIR` | One drawing → one SVG with a `<g>` per colour role (`coat`, `stripe`, `ear`, `cream`, `white`, `nose`, `line`), classes `r-<role>`. Specks and anti-aliasing halos are cleaned up; fills run under the lines, so there are no gaps. `--line-min/--line-max` (px) evens out line weight while keeping the taper. |
| `sheet_frames.py SHEET --out DIR` | Cuts a sheet into frames (labels, grid lines and faded sketches are skipped), puts them all on one canvas lined up by the middle of their base, reads each frame's eyes and nose into `cues.json`, paints the drawn eyes over, and traces every frame with `trace_layers.py`. |
| `place_eyes.py DIR KIT.svg --set round --front N` | Puts one of the kit's eye sets on every frame, each eye where the drawing had it, sized by the front frame's eye spacing, narrowed or squashed as the drawn eye was, and tilted with the head. Frames with eyes shut keep their drawn eyes. |
| `preview_frames.py DIR OUT.png SETS [WIDTH]` | Contact sheet: the cues, the traces, and the traces with kit eyes. |
| `make_alignment.py HEADS_DIR ../V2/SVG OUTDIR` | Files for lining heads up on the V2 body by hand: `body_headless.svg` (the body under a movable neck-cut mask), `head_N.svg` (each head with a `cues` layer marking its eyes and nose), and `align_head_turn.svg` (body, the old V2 head faded for reference, and all heads in one `Heads` group, roughly placed). |
| `build_head_poses.py ALIGN.svg OUTDIR --pose N=FILE:GROUP ... [--bib N=FILE] --cues CUES.json` | Reads the heads you placed by hand (each `--pose` names a file and the head's group in it; `--bib` takes a pose's bib and fluff from a different file), measures each head's move and scale and how you moved and stretched the bib and fluff, fills in the poses you haven't placed (halfway between placed neighbours, or the same as the last one), and writes `body_headless.svg` (no bib or fluff: they now go with the head), `pose_N_head.svg` (head + its bib and fluff), `pose_N.svg` (on the body) and `poses.json`. |
| `make_pose_sheet.py POSES_DIR OUT.svg` | All five poses side by side in one file (`Pose_N` groups, each with `Body_N`, `Bib_N`, `Fluff_N`, `Head_N`) for corrections in Illustrator: move, scale or redraw the bib, fluff and head; leave each body where it is (or move a whole pose column, which is fine). |
| `apply_pose_edits.py POSES_DIR OUTDIR --sheet all_poses.svg` (or `--edits edits.json`) | Reads the corrected sheet back (everything kept as drawn, each pose lined up by its body), or the pose editor page's saved placements, and rewrites the pose files and `poses.json`; the eye and nose positions move with each head. |
| `render_turn.py POSES_DIR` | `turn_strip.png` (all five poses) and `head_turn_preview.gif` (the turn played back), cue marks hidden. |
| `make_pose_editor.py POSES_DIR OUT.html` | The pose editor page (drag, scale, ghost a neighbouring pose, play the turn, save for Claude) built from the current poses and `editor_template.html`. |
| `flf_runner.py --sequence FILE.json` | Wan 2.2 in-betweens: takes keyframes and a sequence file, asks the Wan ComfyUI for the frames between each pair, writes `out/NAME/frames/frame_NNNNN.png` and `out/NAME/run.json`. Also `--start A.png --end B.png --name N` for one pair, and `--dry-run` to check the plan without touching the server. See "In-betweens with Wan 2.2" below. |
| `trace_frames.py FRAMES_DIR --out DIR [--record RUN_JSON]` | Same eye/nose reading, eye painting and tracing as `sheet_frames.py`, for a folder of frames that are already lined up (no cutting, no aligning); eyes missed for 1-2 frames are filled from the frames either side. `--record` adds the eye states and isolated flips to `run.json`. |
| `preview_seq.py DIR [--set round]` | Animated GIF (`preview_<set>.gif`) and contact sheet (`contact_<set>.png`) of a traced sequence; keyframes are marked K. `--set ""` previews the traces alone. |

Example (about 3 seconds per sheet):

```
python sheet_frames.py head_turn_sheet.jpg --out out/head_turn --open-bottom 0.22   # heads: no line under the neck
python place_eyes.py out/head_turn ../cat_kit.svg --set round --front 3
python preview_frames.py out/head_turn out/head_turn_preview.png round
python make_alignment.py out/head_turn ../V2/SVG ../V2/head_turn
```

The colour roles match the V2 kit's colours (`ROLES` at the top of `trace_layers.py`); a sheet drawn in other
colours needs those changed. Known limits: the kit eyes keep their own pupils (the drawn eyes' gaze is in
`cues.json` but isn't copied), and frames are traced one by one, so small wobbles between frames in the source
drawing stay in the traces.

Correcting poses (one command each, about 3 seconds):

```
python make_pose_sheet.py ../V2/head_turn/poses ../V2/head_turn/poses/all_poses.svg      # then edit it in Illustrator and save as SVG
python apply_pose_edits.py ../V2/head_turn/poses ../V2/head_turn/poses_fixed --sheet ../V2/head_turn/poses/all_poses.svg
python render_turn.py ../V2/head_turn/poses_fixed
```

## In-betweens with Wan 2.2

Wan 2.2 draws the frames between two keyframes (first/last-frame video). The sheet tools then trace and preview them.
Wan runs in its own container, `comfyui-wan`, in the `comfyui_wan` folder that sits next to this project folder (image
`comfyui-wan:local`, port 8189). The sheet tools run with `.venv\Scripts\python.exe` in this folder (Python 3.13;
Playwright's Chromium is inside it). Below, `PY` means that file, and commands run from this folder.

**Start and stop.** Only one of `comfyui-wan` and `comfyui-3d` can run at a time: they share the 12 GB GPU and the
~31 GB Docker VM.

```
docker stop comfyui-3d
cd ..\..\..\comfyui_wan
docker compose up -d
```

When done:

```
docker stop comfyui-wan
docker start comfyui-3d
```

`comfyui-3d` stays stopped until you run `docker start comfyui-3d`, even across a reboot. To rebuild Wan:
`docker compose build`, then `docker compose up -d --force-recreate`. Versions are pinned by `requirements.lock`
(`PIP_CONSTRAINT`), which also pins setuptools and wheel, so adding another node pack may need a lock update.
The log line "IMPORT FAILED ... ComfyUI-Manager" is expected (base image symlink; Manager isn't used).

**Keyframes.** `PY sheet_frames.py SHEET --out out\NAME_keys`. The grooming sequence uses `out\grooming_keys`.

**Sequence file** (`sequences\grooming.json` is the example):

| Field | Meaning |
| --- | --- |
| `name` | Output folder, `out\NAME`. |
| `keys` | Keyframe folder (relative to this folder) from `sheet_frames.py`, or a list of PNGs (numbered 1, 2, ...). |
| `order` | Keyframe numbers in playing order. A step is each neighbouring pair. |
| `fps` | Playback rate, 16 at most. |
| `seconds` | Playback length per step (the flag default is 0.5). |
| `gen_seconds` | How long Wan generates per step (default 1.0). |
| `seed` | Wan seed. |
| `loop` | `true` adds a closing step back to the first keyframe, unless `order` already ends on it. Either way the duplicate closing frame is dropped. |
| `front` | Keyframe used as the front view for eye placement: pick a frontal one with both eyes detected (grooming uses 1; keyframe 3 is a misdetection, which tilted every frame's eyes ~50 degrees). The runner prints its frame number. |
| `default_prompt` | Prompt for every step. |
| `steps` | Optional, per pair `"2-3": {"prompt": ..., "seconds": ..., "gen_seconds": ..., "seed": ...}`. A step's own `seed` gives another take of the same move (e.g. one without an invented blink). |
| `budget` | Optional. Pixels Wan works at (default 400000); frames are scaled back. |
| `retime` | Optional. `"motion"` (default) or `"clock"`, see Timing. |
| `match_body` | Optional, e.g. `{"3": [2, 4]}`: before Wan, narrow (or widen) keyframe 3's body below the head, row by row, to the average width of keyframes 2 and 4 (`body_match.py`), for a pose drawn broader than its neighbours. The keyframe folder and sheet are untouched; the adjusted keyframe is what appears in the frames. |

Single pair, no file: `PY flf_runner.py --start A.png --end B.png --name N [--seconds --gen-seconds --fps --seed --prompt --budget]`.
`--no-exact-endpoints` and `--url` (default `http://127.0.0.1:8189`) work in both modes.

**The four commands, keyframes to GIF** (grooming; `--front 1` is the `front_frame` the runner prints, a frontal keyframe with both eyes detected; `place_eyes.py` warns if the front frame's eyes are tilted more than 15 degrees):

```
PY flf_runner.py --sequence sequences\grooming.json
PY trace_frames.py out\grooming_wan\frames --out out\grooming_wan\svg --record out\grooming_wan\run.json --keep-shut
PY eyes_json.py out\grooming_wan
PY place_eyes.py out\grooming_wan\svg ..\cat_kit.svg --set round --front 1
PY preview_seq.py out\grooming_wan\svg --set round
```

`PY preview_seq.py out\grooming_wan\svg --set ""` previews the traces alone. Use `--dry-run` first to see the plan.

**Eyes for the viz (live kit eyes).** Every `svg\frame_NNNNN.svg` is eyeless, shut-eye frames included: eyes drawn shut
are placed between the frames either side (moved onto the drawn lid line where one is clearly found) and painted out
like the open ones. `--keep-shut` also writes the drawn-shut versions as `frame_NNNNN_drawnshut.svg` (not the default).
`eyes_json.py out\NAME` then writes:
- `svg\eyes.json`: per frame, per eye (`left` = the viewer's left, followed frame to frame), in kit units (the units
  of `cat_kit.svg`, V2 units × 1.35): `cx, cy, w, h` (the eye's size when open), `opening_h` (the white as read),
  `angle` (eye line, degrees), `visible`, `lid` (0 open, 1 shut; measured from the white's height against the same
  eye's open height nearby, 1 where drawn shut, and at least the blink ramp), `gaze_x, gaze_y` (pupil offset, share
  of half the width/height), `source` (`detected`, `filled`, `interpolated`), and `smooth` (cx, cy, w, h, angle:
  3-frame median then [1 2 1], keyframes pinned to their detected values; the one to draw). Plus `flags` (frames
  where the eye spacing changes more than 20% or the eye line more than 10 degrees against the frames either side,
  eyes that swap sides, one eye found on a frontal head) and `unsure_which_eye`.
- `to_kit` [scale, tx, ty] in `run.json` (x_kit = scale·x + tx): frame 1's widest width below the neck to the kit's
  typical body, its middle to BODY_X and its floor to FLOOR_Y (`..\V2\build_kit_v2.py`, × 1.35). The frame SVGs are
  wrapped in `<g id="to-kit">` with a kit-unit viewBox, so they overlay the kit body.
- `svg\check_eyes.png`: every frame with its eye boxes (green read, blue filled, cyan interpolated), gaze arrows and
  lid values; flagged frames outlined in red.
`eyes_px.json` (from `trace_frames.py`) holds the same eyes in frame pixels, as read.
Wan makes up blinks (on a 2 s step, every seed tried did). Frames where the eyes go shut or to a sliver for a frame
or two are filled from the frames either side and painted out like the rest, and by default their `lid` is 0: the
viz blinks on its own, and a blink and a head or body turn shouldn't share a step. `--keep-wan-blinks` keeps them.
Eyes drawn shut in the keyframes (a longer run) always get lid 1.

**Keyframes from more than one sheet** (`join_keys.py`). The kneading sheet (`sheets\kneading_sheet.webp`) has no
frontal base pose, so the head turn's front pose is joined to it: `PY join_keys.py out\knead_keys
out\head_turn_keys:3 out\knead_sheet_keys:1,2,3,4,5,6 --match out\head_turn_keys:3=out\knead_sheet_keys:3` puts them
on one canvas lined up at the feet, the base scaled (0.830) to the kneading cat's height; `out\knead_keys` frame 1 is
the base, 2-7 the sheet's poses 1-6. `sequences\knead.json` plays base → sit turned (4) → paw up (3) → paw out (2)
and back, looped, with the turn steps 1 s long (2 s generated): 48 frames. Labels printed just under the feet are now
dropped by `sheet_frames.py` (ink wholly below the drawing's lowest point); the grooming and head-turn sheets cut
byte-for-byte as before.

The head turn is the same four commands with `sequences\head_turn.json` and `out\head_turn_wan` (front frame 1 there
too: the loop starts on the frontal pose 3). Its keyframes come from `PY sheet_frames.py sheets\head_turn_sheet.webp
--out out\head_turn_keys` (a 2000 px generative upscale of the 1024 px original, about 380×700 px per cat; same
proportions within 1%). The order 3,2,1,2,3,4,5,4,3 with `loop` makes 4 Wan runs; the way back reuses them reversed;
48 frames, 4 s. The 1024 px original (`sheets\head_turn_sheet_1024.webp`) cuts and traces too, but its keyframes lose
the mouth and nose lines that the in-betweens keep, so the face flickers on the keyframes; keep sheets near 2000 px.
The front pose (3) is drawn 8-10% broader than poses 1, 2, 4 and 5, so the chest swelled each time the cat faced
front. Pose 3's width is also the V2 base poses' body width (`..\V2\head_turn\poses`), so the other four are widened
to it: `"match_body": {"1": [3], "2": [3], "4": [3], "5": [3]}`. Over the loop the body is now within 0-3% of the V2
body down to the haunch (5% narrower at the lower haunch, the sheet's own shape) and swings 2.5-3.7% (6.5% at the
neck, where the bib's shape still differs between poses).
Wan invents blinks: with these keyframes every step blinked at seed 42, and a "no blinking" prompt didn't stop it.
Each step has its own seed (`steps`, `"seed"`) picked by trying seeds until the raw frames' eye heights never drop
below 60% of their median: 3-2 2024, 2-1 7, 3-4 9001, 4-5 101. All 48 frames read open eyes.
`preview_seq.py --fps` (default 12) must match the sequence's `fps`.

After any rerun of `flf_runner.py`, rerun `trace_frames.py`, `place_eyes.py` and `preview_seq.py`: `svg\` isn't invalidated by a new run, and `run.json`'s `eyes` is rewritten by `trace_frames.py --record`.

**Timing.** Wan always generates at 16 fps. `seconds` is the playback length of a step; `gen_seconds` is how long Wan
generates. Wan generates `max(seconds, gen_seconds)` and the step's frames are picked from that, so the motion
plays faster than it was generated. Why: at 0.5 s (9 frames) Wan drifted off-style (grey textured background, soft
lines; endpoint diff about 35); at 1 s it stays flat (about 6). `fps` above 16 is refused: it would need RIFE.

Wan tends to do a step's whole move in a burst of 4-5 of its 16 frames and hold still around it, so frames picked by
the clock snap (the head-turn bib moved 16 px in one frame, then stalled for 22 of 47 frames). So by default
(`"retime": "motion"`, or `--retime motion`) each step's frames are picked by how far the picture has moved: equal
shares of the step's movement per frame, eased a little in and out. On the head turn that halved the biggest
one-frame jump (16.5 to 8.5 px) and cut stalls from 22 to 8 frames. `--retime clock` (or `"retime": "clock"`) picks
by time instead. The picks used are in `run.json` per step. Retiming reuses the cached Wan frames: no GPU.

**Endpoints.** On by default, the keyframes themselves are put at the joins, so they appear unchanged. `run.json`
records how far Wan's own endpoints were (`endpoint_diff`).

**Cache.** `out\NAME\raw\seg_A-B` holds Wan's frames, keyed by both keyframe images, the prompt (with the style
tail), seed, generation length, size and workflow. Change any of those and only that step is regenerated. A reverse
step (2 to 1 after 1 to 2) reuses the frames reversed.

**Blink rule.** A blink and a head turn should not share a step. The runner warns when a step's keyframes differ in
eye state. Put the blink in its own step.

**Negative prompt.** There isn't one. At CFG 1 (the Lightning LoRAs) it does nothing, so it isn't exposed.

**Measured** (grooming, 11 steps, 67 frames, 12 GB GPU): per-step times weren't recorded for this run, so these are approximate:
the first step after starting the container takes about 3.5 min (model load from the Windows bind mount), later steps
about 1 min each, a full uncached run about 12-14 min. Peak VRAM about 11.8 GiB of 12.0 GiB (nvidia-smi MiB; the card
is 12,282 MiB). Peak container RAM about 30.0 of 31.3 GiB (30,730 MiB of the Docker VM's 33,657,810,944 bytes), about
1.3 GiB spare, so it is close to the limit, and one head-turn run was killed for memory. `comfyui_wan\docker-compose.yml`
now starts ComfyUI with `--cache-ram 6` (keep models cached, but drop cached items when free RAM falls under 6 GB);
the next run peaked at 26.8 GiB. A fully cached re-run takes about 3 s. From now on `run.json` records
per-step generation stats (`raw\seg_A-B\seg.json`: wall seconds and peak VRAM/RAM); a cached step shows them under
`generated` (null if the segment predates this), while the run-level peaks are for that run only. (`out\grooming_wan\run.json`
on disk is from a cached re-run, so its times and peaks are low.)

**Known limits.**
- Eyes are read from the eye whites. Pieces of white split by a pupil are joined into one eye, and white touching the
  outline is ignored (whiskers crossing the outline close off pockets of paper that look like eyes). In a sequence,
  `trace_frames.py` fills a frame or two with no eyes, or with eyes under half their neighbours' size (half-lidded,
  only a sliver of white), from the frames either side: those frames get their drawn eyes painted out and kit eyes
  like the rest (`"eyes_filled": true` in `cues.json`, `filled` in `run.json`). Grooming: 4, 10, 59, and 65, where
  Wan invented a blink.
- Eyes drawn shut for longer than 2 frames (grooming 39-49, the keyframes' own blink) are left as drawn: no kit eyes,
  `eyes_closed` true. So the kit eyes don't pop into the drawn ones, every frame's cue has a `lid` (0 open, 1 shut)
  that eases over `--blink-ramp` frames (default 2) before and after each shut run, e.g. grooming 37: 0.33, 38: 0.67,
  39-49: 1, 50: 0.67, 51: 0.33. `place_eyes.py` puts it on the eyes group as `data-lid`; the viz closes the kit
  eyes' lids that far with `closeEyes(svg, +eyes.dataset.lid)` from `blink.js`. The previews don't show the lids.
