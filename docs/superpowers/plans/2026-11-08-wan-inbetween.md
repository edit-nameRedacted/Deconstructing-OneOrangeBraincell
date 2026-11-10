# Wan 2.2 in-betweens for the cat sheets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate quick, choppy in-betweens between AC's hand-edited cat keyframes with Wan 2.2 14B FLF2V in a
separate local ComfyUI container, and trace every frame into the same layered SVGs (with `cues.json`) that the
sheet tools make today.

**Architecture:** A new container `comfyui-wan` (folder `pysandbox/comfyui_wan/`, port 8189) serves one API-format
workflow. `flf_runner.py` in `SVG/sheet_tools/` pads the keyframes to Wan's size, runs one Wan job per step over
HTTP, picks frames for the target fps, undoes the padding, joins the steps, and writes `run.json`.
`trace_frames.py` passes the joined frames through the per-frame body of `sheet_frames.py`, and `preview_seq.py`
makes a GIF and a contact sheet.

**Tech Stack:** Docker (lecode comfyui-docker base, ComfyUI 0.8.2), ComfyUI-GGUF, Python 3.13 venv (stdlib,
Pillow, numpy, opencv, vtracer, svgelements, Playwright, pytest).

**Spec:** `docs/superpowers/specs/2026-11-08-wan-inbetween-design.md`. Read it before any task; where this plan
and the spec disagree, the spec wins.

**Paths used below:** `ST` = `C:\Users\Watcher\Documents\pysandbox\Orange_Braincells\SVG\sheet_tools`,
`CW` = `C:\Users\Watcher\Documents\pysandbox\comfyui_wan`, `PY` = `ST\.venv\Scripts\python.exe`.

## Global Constraints

- **Never touch the bust pipeline.** `C:\Users\Watcher\Documents\pysandbox\temp\comfyui3d\`, image `comfyui-3d:local` and container `comfyui-3d` are not edited, rebuilt, re-tagged or given any files. Allowed: `docker stop comfyui-3d` and `docker start comfyui-3d`, and only after AC says yes in chat. Leave the old exited container `comfyui` alone.
- **Pinned base image:** `ghcr.io/lecode-official/comfyui-docker:0.6.3-comfyui-0.8.2-comfyui-manager-4.0.5-pytorch-2.9.1-cuda-12.6-cudnn-9`. Image `comfyui-wan:local`, container `comfyui-wan`, host port 8189 → container 8188.
- **Models**, exactly these six files, flat in `CW\models\…`:
  - `Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf` and `Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf` → `unet/`
  - `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors` and `…_low_noise.safetensors` → `loras/`
  - `wan_2.1_vae.safetensors` → `vae/`
  - `umt5_xxl_fp8_e4m3fn_scaled.safetensors` → `text_encoders/`
- **Ask AC first** for any download not in that list, going above 480p-equivalent (about 400k px), Q5_K_M, driver or CUDA changes, installing outside `CW` or `Orange_Braincells`, and raising the WSL memory limit.
- **Sampler:** 4 steps split 2/2, CFG 1, shift 5, euler/simple, LoRA strength 1.0, the same seed on both `KSamplerAdvanced` nodes.
- **Frame maths:** L = 4·round(16·S/4)+1, capped at 81. D = (L−1)/16. N = round(D·F)+1. Output frame j = generated frame round(16·j/F). F > 16 is refused. Rounding is half-up everywhere.
- **Defaults:** fps 12, 0.5 s per step, exact endpoints on, working size about 400 000 px padded with white to multiples of 16.
- **No git commits or pushes** (AC's standing rule; `Orange_Braincells` has AC's uncommitted work). Every "Commit" step below is replaced by "leave uncommitted, list the files in the task report".
- **Fixes live in code or workflow files**, never in hand-edited outputs.
- **Run one Docker job at a time.** Rebuild only when a task says so; never run `docker compose up --build` casually.

## Review Focus

1. **Half-way rounding.** At S = 0.625 s, 16·S/4 = 2.5. Python's `round` gives 2, half-up gives 3 → L = 13. Expect L = 13. Test in Task 2.
2. **Mismatched keyframes.** Two keyframe PNGs of different sizes, or an order naming a keyframe that doesn't exist, should stop with a message naming the file or number, not a traceback deep in Pillow. Test in Task 2 (`load_keys`).
3. **Transparent input PNGs.** An RGBA keyframe must be flattened on white before Wan sees it (Wan is RGB only; a naive `convert("RGB")` turns transparent areas black). Test in Task 2.
4. **Stale segment reuse.** Rerunning a sequence after changing one step's prompt, seconds or the seed must regenerate only that step and never reuse frames made with other settings. Test in Task 8 (`segment_key`).
5. **ComfyUI rejects or loses a job** (node error, container stopped, run longer than the timeout). The runner should print the node error text, or say the container isn't reachable at :8189, and exit non-zero instead of hanging. Test in Task 6 (`check_prompt_response`).

---

### Task 1: Python env for the sheet tools, and a baseline

The sheet tools' dependencies aren't installed in any Python on this machine. `C:\Python313` has cv2, numpy, skimage, Pillow and pytest, but no vtracer, svgelements or playwright.

**Files:**
- Create: `ST\.venv\` (venv, Python 3.13; fall back to `C:\Python311` only if a vtracer wheel is missing for 3.13)
- Create: `ST\.venv\Lib\site-packages\sheet_tools_env.pth`
- Create: `ST\.gitignore` containing `.venv/`
- Create: `C:\Users\Watcher\AppData\Local\Temp\claude\eebd8dde873cca70\6d55b2cd-1a04-4436-a7ec-9c0b95c03c1d\scratchpad\baseline_grooming\` (baseline outputs)

**Interfaces:**
- Produces: `PY`, which runs every later sheet-tools command and test. It also produces the baseline folder that Task 9 compares against byte for byte.

- [ ] **Step 1:** Create the venv: `C:\Python313\python.exe -m venv ST\.venv`.
- [ ] **Step 2:** Install the dependencies:
  `PY -m pip install opencv-python numpy scikit-image vtracer svgelements Pillow playwright pytest`.
  Expected: all install from wheels.
- [ ] **Step 3:** Write the `.pth` file: one line, `import os; os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '0')`. This keeps Playwright's Chromium inside the venv, not in `%LOCALAPPDATA%` (it's the same trick as the bust image's `.pth`).
- [ ] **Step 4: STOP, the controller asks AC first.** "Download Playwright Chromium (~150 MB, from playwright.azureedge.net) into `ST\.venv`?" On yes, run `PY -m playwright install chromium`.
- [ ] **Step 5:** Check that it all imports:
  `PY -c "import cv2, vtracer, skimage, svgelements, playwright, PIL, numpy; print('ok')"`.
  Expected: `ok`.
- [ ] **Step 6:** Make the baseline, from `ST`:
  `PY sheet_frames.py sheets\grooming_sheet.jpg --out <scratchpad>\baseline_grooming`.
  Expected on stderr: `12 frames on a 419x599 canvas`.
- [ ] **Step 7:** Compare the baseline's `cues.json` with `ST\out\grooming\cues.json` and report any differences (eye counts per frame). Don't fix anything; the baseline only proves the env works.

### Task 2: Frame maths, geometry and keyframe loading (no GPU)

**Files:**
- Create: `ST\flf_runner.py`. This task adds the pure functions only; the CLI comes in Task 6.
- Test: `ST\test_frame_math.py`

**Interfaces:**
- Produces, in `flf_runner.py`:
  - `round_half_up(x: float) -> int`
  - `wan_length(seconds: float) -> tuple[int, float, bool]`, returning `(L, D, capped)`
  - `pick_frames(L: int, fps: float) -> list[int]`. Raises `ValueError` mentioning "RIFE" if `fps > 16`. Indices are capped at `L-1`, and the last index is always exactly `L-1`, so every step ends on its end keyframe. Without that, D·F that isn't a whole number, for example 0.75 s at 7 fps, would end a frame early.
  - `join_segments(segs: list[list], loop: bool) -> list`. Drops the first item of every segment after the first; with `loop`, drops the final item.
  - `@dataclass Geometry(W, H, scale, w, h, pw, ph, ox, oy)`: the original canvas, the scaled size, the padded size and the paste offset.
  - `fit_geometry(W: int, H: int, budget: int = 400_000, mult: int = 16) -> Geometry`:
    - `scale = sqrt(budget / (W*H))`, with `w = round(W*scale)` and `h = round(H*scale)`.
    - `pw` and `ph` are the next multiples of 16 at or above `w` and `h`.
    - The offset is centred: `ox = (pw-w)//2`, `oy = (ph-h)//2`.
  - `to_wan(img: Image.Image, g: Geometry) -> Image.Image`:
    - Flattens RGBA and LA onto white.
    - Resizes to w×h with LANCZOS.
    - Pastes onto a white pw×ph canvas at (ox, oy).
  - `from_wan(img: Image.Image, g: Geometry) -> Image.Image`: crops `(ox, oy, ox+w, oy+h)`, then resizes to W×H with LANCZOS.
  - `mean_abs_diff(a: Image.Image, b: Image.Image) -> float`: mean absolute RGB difference, 0–255.
  - `load_keys(src: str | list[str]) -> tuple[dict[int, Image.Image], dict[int, bool] | None]`:
    - A directory means `sheet_frames.py` output: it reads `frame_NN.png` for each `cues.json` frame, and eye state from `eyes_closed`.
    - A list means PNG paths, numbered 1…n, with eye state `None`.
    - Raises `ValueError` naming the file when sizes differ.

- [ ] **Step 1: Write the failing tests.** In `test_frame_math.py`:
  - **Length:**
    - `wan_length(3) == (49, 3.0, False)`
    - `wan_length(5)[:2] == (81, 5.0)`
    - `wan_length(0.5)[:2] == (9, 0.5)`
    - `wan_length(2.1)[:2] == (33, 2.0)`
    - `wan_length(6) == (81, 5.0, True)`
    - `wan_length(0.625)[0] == 13`
  - **Picks:**
    - `pick_frames(49, 16) == list(range(49))`
    - `len(pick_frames(81, 12)) == 61`
    - `pick_frames(9, 12) == [0, 1, 3, 4, 5, 7, 8]`
    - `pick_frames(9, 8) == [0, 2, 4, 6, 8]`
    - `len(pick_frames(33, 8)) == 17`
    - `pytest.raises(ValueError, match="RIFE")` for `pick_frames(49, 24)`
    - `pick_frames(13, 7)[-1] == 12`
  - **Joining:**
    - `join_segments([[1,2,3],[3,4,5]], False) == [1,2,3,4,5]`
    - `join_segments([[1,2,3],[3,4,1]], True) == [1,2,3,4]`
  - **Geometry:** `fit_geometry(419, 599)` gives `pw % 16 == ph % 16 == 0`, `w*h <= 400_000`, `pw >= w` and `ph >= h`.
  - **Round trip:** a 419×599 image with a black 50×50 square at (100,100) goes through `to_wan` then `from_wan`, comes back at size (419, 599), and `mean_abs_diff` against the original is under 3.
  - **RGBA:** a fully transparent RGBA 100×100 image, after `to_wan`, has a white pixel at its centre.
  - **`load_keys` size check:** two PNGs of different sizes raise `ValueError` matching the second file's name.
  - **`load_keys` on a directory:** `load_keys(ST/"out"/"grooming_keys")` returns 12 images, each of size (360, 509), and 12 eye states.
- [ ] **Step 2: Run the tests and see them fail.**
  `cd ST; PY -m pytest test_frame_math.py -v`.
  Expected: FAIL with ImportError / AttributeError.
- [ ] **Step 3: Implement** the functions above in `flf_runner.py`. Imports must be stdlib plus Pillow only.
- [ ] **Step 4: Run the tests and see them pass.** Same command; expected: all pass.
- [ ] **Step 5: Don't commit.** List the files in the task report.

### Task 3: The Wan container

**Files:**
- Create: `CW\Dockerfile`, `CW\docker-compose.yml`, `CW\.dockerignore`, `CW\requirements.lock`
- Create (empty folders): `CW\models\{unet,loras,vae,text_encoders}`, `CW\input`, `CW\output`, `CW\workflows`

**Interfaces:**
- Produces: a container `comfyui-wan` answering `http://127.0.0.1:8189/system_stats`, with `UnetLoaderGGUF` in `/object_info`.

- [ ] **Step 1: Machine check.** Record in the task report:
  - `nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv`
  - `docker info --format "{{.MemTotal}}"`
  - free space on C:
  - `docker ps -a --format "{{.Names}} {{.Image}} {{.Status}}"`
- [ ] **Step 2: Initial lock file.** Write `CW\requirements.lock` from
  `docker run --rm --entrypoint pip <base tag> freeze`.
  Drop lines containing `@ file:` or starting with `-e`, since constraint files can't hold them. This pins everything the base already has, so the ComfyUI-GGUF install can only add packages.
- [ ] **Step 3: Look up the ComfyUI-GGUF commit.** Run `git ls-remote https://github.com/city96/ComfyUI-GGUF HEAD` and record the hash.
- [ ] **Step 4: Write the `Dockerfile`.**
  - `FROM` the pinned base.
  - `COPY requirements.lock /opt/requirements.lock`, then `ENV PIP_CONSTRAINT=/opt/requirements.lock` (spec trap 2).
  - Last layer: `git init` + `git fetch --depth 1 origin <hash>` + `git checkout FETCH_HEAD` into `/opt/comfyui/custom_nodes/ComfyUI-GGUF`, then `pip install --no-cache-dir -r requirements.txt`.
  - No CUDA toolkit, no Manager, no `startup.sh`, no `ENTRYPOINT` override (spec traps 3, 9, 13).
- [ ] **Step 5: Write `docker-compose.yml`.**
  - Service `comfyui-wan`, `build: .`, `image: comfyui-wan:local`, `container_name: comfyui-wan`.
  - `ports: ["8189:8188"]`; environment `USER_ID=1000` and `GROUP_ID=1000`.
  - Volumes, all under `/opt/comfyui` and none under `/home/comfyui-user` (spec trap 5):
    - `./models:/opt/comfyui/models:rw`
    - `./output:/opt/comfyui/output:rw`
    - `./input:/opt/comfyui/input:rw`
    - `./workflows:/opt/comfyui/user/default/workflows:rw`
  - The nvidia GPU reservation block, copied from the bust compose file.
  - **No `restart:` key.**
- [ ] **Step 6: Write `.dockerignore`** with `/models`, `/output`, `/input`.
- [ ] **Step 7: Build.**
  `cd CW; docker compose build`.
  Expected: success, and the build-context size printed is under 1 MB.
- [ ] **Step 8: STOP, the controller asks AC first.** "Stop `comfyui-3d` to free the GPU and RAM?"
  - Before stopping, record `docker inspect comfyui-3d --format "{{.Image}} {{.Created}} {{.HostConfig.RestartPolicy.Name}}"`.
  - On yes, run `docker stop comfyui-3d`.
- [ ] **Step 9: Start and check.**
  - Run `docker compose up -d`, then poll `http://127.0.0.1:8189/system_stats` until it answers (up to 3 min).
  - Check that `curl -s http://127.0.0.1:8189/object_info/UnetLoaderGGUF` is non-empty.
  - Check that `docker logs comfyui-wan` shows no `IMPORT FAILED`.
  - Record `comfyui_version` from `/system_stats`.

### Task 4: Model files

**Files:**
- Create: the six files listed under Global Constraints, flat in `CW\models\…`

- [ ] **Step 1: Find the downloader.** Check for a Hugging Face CLI inside the container: `docker exec comfyui-wan sh -c "command -v hf || command -v huggingface-cli"`. Use whichever exists. If neither exists, stop and report: installing one on the host is outside the allowed folders.
- [ ] **Step 2: Download** each file with `--local-dir /opt/comfyui/models/_dl/<repo>`. Use the repos and paths from the handoff's model table:
  - `QuantStack/Wan2.2-I2V-A14B-GGUF`: `HighNoise/…Q4_K_M.gguf` and `LowNoise/…Q4_K_M.gguf`
  - `Comfy-Org/Wan_2.2_ComfyUI_Repackaged`: `split_files/loras/…` ×2 and `split_files/vae/wan_2.1_vae.safetensors`
  - `Comfy-Org/Wan_2.1_ComfyUI_repackaged`: `split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`

  Run each in the background; this is ~29 GB.
- [ ] **Step 3: Move the files flat** into `unet/`, `loras/`, `vae/` and `text_encoders/` (spec trap 15), then delete `_dl`.
- [ ] **Step 4: Verify** with `Get-ChildItem CW\models -Recurse -File | Select FullName, Length, LinkType`. Expected:
  - six files, none with a `LinkType`;
  - sizes about 9.7 GB ×2, 1.2 GB ×2, 254 MB and 6.7 GB.
- [ ] **Step 5: Check the models are listed.** `/object_info/UnetLoaderGGUF` lists both `.gguf` names, and `/object_info/LoraLoaderModelOnly` lists both LoRAs.

### Task 5: Workflows

**Files:**
- Create: `CW\workflows\wan22_flf2v_12gb.json` (UI format)
- Create: `ST\wan22_flf2v_12gb_api.json` (API format)

**Interfaces:**
- Produces: the API graph. Every node the runner sets carries one of these `_meta.title` values, with these inputs:

  | Title | Inputs the runner sets |
  |---|---|
  | `start_image` | `LoadImage.image` |
  | `end_image` | `LoadImage.image` |
  | `positive` | `CLIPTextEncode.text` |
  | `flf2v` | `WanFirstLastFrameToVideo.width`, `.height`, `.length` |
  | `sampler_high` | `KSamplerAdvanced.noise_seed` |
  | `sampler_low` | `KSamplerAdvanced.noise_seed` |
  | `save` | `SaveImage.filename_prefix` |

  The last node is `SaveImage` straight after `VAEDecode`. There's no frame-picking node; the runner does that.

- [ ] **Step 1: Copy the template.** Copy `video_wan2_2_14B_flf2v.json` out of the container's `comfyui_workflow_templates_media_video` package. Find it with `docker exec comfyui-wan sh -c "find / -name 'video_wan2_2_14B_flf2v.json' 2>/dev/null"`.
- [ ] **Step 2: Check which models the template needs.** If it needs any model not in the six (for example a clip-vision file), stop and ask AC.
- [ ] **Step 3: Write the UI workflow.**
  - Swap both `UNETLoader` nodes for `UnetLoaderGGUF` with the two `.gguf` files.
  - Add a `LoraLoaderModelOnly` at 1.0 after each expert.
  - Set the sampler values from Global Constraints. Use add-noise and leftover-noise exactly as in the handoff's settings table: high `enable`/`enable`, steps 0→2; low `disable`/`disable`, steps 2→4.
  - Use 544×768 and length 9 as the shown defaults.
  - Save the result as `wan22_flf2v_12gb.json`.
- [ ] **Step 4: Write the API JSON** for the same graph, with the titles above.
- [ ] **Step 5: Validate.** For each node in the API JSON, check that its `class_type` exists in `/object_info`. Expected: none missing.
- [ ] **Step 6: Check for red nodes.** Open `http://localhost:8189` in the built-in browser and load the UI workflow from the Workflows sidebar. Take a screenshot. Expected: no red or missing nodes and no missing-model warning. Attach the screenshot path to the task report.

### Task 6: Runner, single pair, smoke test

**Files:**
- Modify: `ST\flf_runner.py` (add the client, segment run and CLI)
- Test: `ST\test_frame_math.py` (add the graph and response tests)

**Interfaces:**
- Consumes: everything from Task 2, plus the titles from Task 5.
- Produces:
  - `STYLE_TAIL: str`: one sentence covering flat-colour 2D cartoon, clean dark brown outlines, plain white background, static camera and no shading.
  - `patch_graph(graph: dict, values: dict[str, dict]) -> dict`: a deep copy with inputs set by title. Raises `KeyError` naming any missing title.
  - `check_prompt_response(resp: dict) -> str`: returns `prompt_id`. Raises `RuntimeError` whose message includes every `node_errors` entry's text.
  - `class ComfyClient(base="http://127.0.0.1:8189", timeout=1800)` with:
    - `upload(png_path) -> str`: `/upload/image`, multipart, `overwrite=true`
    - `queue(graph) -> str`
    - `wait(prompt_id) -> dict`: polls `/history/<id>` every 2 s and raises `TimeoutError`
    - `images(history) -> list[bytes]`: sorted by filename, via `/view`
    - `system_stats() -> dict`

    A connection error raises `RuntimeError("ComfyUI not reachable at <base> — is comfyui-wan running?")`.
  - `class MemorySampler`: a context manager on a thread. Every 2 s it runs `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits` and `docker stats --no-stream --format "{{.MemUsage}}" comfyui-wan`. Attributes: `peak_vram_mb`, `peak_ram_mb`.
  - `run_segment(client, graph, start: Image, end: Image, seconds: float, prompt: str, seed: int, g: Geometry, out_dir: str) -> list[Image]`. Returns the L generated frames, already passed through `from_wan`, and saves them as `out_dir/gen_NNN.png`.
  - CLI: `PY flf_runner.py --start A.png --end B.png --name NAME [--seconds 0.5] [--fps 12] [--seed 42] [--prompt TEXT] [--no-exact-endpoints] [--url URL]`.
    - Writes `out/NAME/raw/seg_1-2/`, `out/NAME/frames/frame_NNNNN.png` (1-based, five digits) and `out/NAME/run.json`.
    - `run.json` holds:
      - the arguments, seed and style tail, and the per-step `L`, `D`, `N` and seconds;
      - the six model file names, read from the graph, and `comfyui_version`;
      - wall-clock seconds per step;
      - `peak_vram_mb` and `peak_ram_mb`;
      - `endpoint_diff` per step: `{"start": float, "end": float}`, generated against original, measured before any swap;
      - `exact_endpoints`.

- [ ] **Step 1: Write the failing tests.**
  - `patch_graph` on a two-node dict, each node with `_meta.title`, sets `inputs.text`, and leaves the original unchanged.
  - `patch_graph` with title `"nope"` raises `KeyError` matching `nope`.
  - `check_prompt_response({"prompt_id": "x", "node_errors": {}}) == "x"`.
  - `check_prompt_response({"error": {...}, "node_errors": {"5": {"errors": [{"message": "value not in list"}]}}})` raises `RuntimeError` matching `value not in list`.
- [ ] **Step 2: Run the tests and see them fail.**
- [ ] **Step 3: Implement** the interfaces above.
  - HTTP uses `urllib.request` only.
  - The prompt sent is `f"{prompt}. {STYLE_TAIL}"`.
  - With exact endpoints on, the frames list's first and last generated frames are replaced by the keyframe images before picking.
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Smoke test 1.** Grooming keyframes 1→2 at 0.5 s, seed 42:
  `PY flf_runner.py --start out\grooming_keys\frame_01.png --end out\grooming_keys\frame_02.png --name smoke_1-2 --prompt "the cat lifts its paw"`.
  Expected:
  - 9 files in `raw/seg_1-2`;
  - 7 files in `frames/`;
  - `run.json` has non-zero peaks.
- [ ] **Step 6: If it runs out of memory,** try these in order, one at a time, recording which helped:
  1. add `command: ["--cache-none"]` to the compose file and recreate the container;
  2. a working budget of 236 000 px (the 640×368 equivalent), via a `--budget` CLI option;
  3. stop and report, because Q3_K_M or WSL memory needs AC.
- [ ] **Step 7: Look at the frames.** Open `smoke_1-2/frames` as a contact image, for example by pasting them side by side with Pillow into the scratchpad. Report:
  - whether the start and end match the keyframes;
  - whether the cat stays flat-coloured (style drift);
  - `endpoint_diff`.
- [ ] **Step 8: Smoke test 2.** Keyframes 2→3 at 1 s (`--name smoke_2-3 --seconds 1`). Expected L = 17, N = 13. Record the time and the peaks.
- [ ] **Step 9: Repeat run.** Rerun Step 5 as `--name smoke_1-2b`. Compare `raw/seg_1-2/gen_*.png` pairwise. Report "identical", or the largest per-pixel difference.
- [ ] **Step 10: Measure model loading.** Compare the first run's time with the repeat's (spec trap 14). If loading dominates, for example more than 60% of a step, report it and propose a named volume. Don't switch to one.

### Task 7: Freeze the working environment

**Files:**
- Modify: `CW\requirements.lock`

- [ ] **Step 1: Freeze.** Write the lock file from `docker exec comfyui-wan pip freeze`, filtered as in Task 3 Step 2.
- [ ] **Step 2: Rebuild** with `cd CW; docker compose build`, then `docker compose up -d --force-recreate`.
- [ ] **Step 3: Confirm nothing moved.** `docker exec comfyui-wan pip freeze` (filtered) is identical to the lock file, and `/object_info/UnetLoaderGGUF` still answers.

### Task 8: Sequences

**Files:**
- Modify: `ST\flf_runner.py`
- Create: `ST\sequences\grooming.json`
- Test: `ST\test_frame_math.py`

**Interfaces:**
- Consumes: Tasks 2 and 6.
- Produces:
  - **Sequence file schema:**
    ```json
    {"name": "grooming_wan", "keys": "out/grooming_keys", "fps": 12, "seconds": 0.5, "seed": 42,
     "loop": false, "front": 3, "order": [1,2,3,4,5,6,7,8,9,10,11,12],
     "default_prompt": "the cat moves smoothly from the first pose to the second",
     "steps": {"1-2": {"prompt": "…", "seconds": 0.5}}}
    ```
    - `keys` is a `sheet_frames.py` output directory or a list of PNGs; relative paths resolve from `ST`.
    - The `steps` keys are `"a-b"` and are optional per step.
  - `plan_steps(order: list[int], loop: bool) -> list[tuple[int, int, str]]`:
    - Each step is `(a, b, "new" | "reverse")`.
    - A step is `"reverse"` when `(b, a)` appeared earlier as `"new"`.
    - With `loop`, if `order[-1] != order[0]`, `order[0]` is appended first.
  - `blink_warnings(steps, eyes_closed: dict[int, bool] | None) -> list[str]`. Each warning reads `"step a→b: eyes open→closed while the pose changes — a blink and a head turn should not share a step"` (or closed→open). The list is empty when `eyes_closed` is None.
  - `segment_key(a, b, seconds, prompt, seed, g: Geometry, graph: dict) -> str`: sha1 of the JSON of all of these, sorted.
  - CLI: `PY flf_runner.py --sequence sequences/grooming.json [--url URL]`. For each step:
    - if `raw/seg_a-b/seg.json` holds the same key and all L frames exist, it reuses them;
    - for `"reverse"`, it reverses the frames of `seg_b-a`;
    - otherwise it runs Wan.

    It then joins with `join_segments`, writes `frames/` and `run.json`, and adds these fields to `run.json`:
    - `blink_warnings`;
    - `keyframe_frames`, the output frame number where each order entry lands;
    - `front_frame`, the output frame number of the first occurrence of `front`.

    It prints the follow-up commands (Tasks 9–10) with `front_frame` filled in.

- [ ] **Step 1: Write the failing tests.**
  - `plan_steps([3,2,1,2,3], False) == [(3,2,"new"),(2,1,"new"),(1,2,"reverse"),(2,3,"reverse")]`
  - `plan_steps([1,2,3], True)[-1] == (3,1,"new")`
  - `blink_warnings([(7,8,"new")], {7: False, 8: True})` has one entry containing `7→8`.
  - `blink_warnings(..., None) == []`
  - `segment_key` changes when only the prompt, only the seconds, or only the seed changes, and is equal for identical inputs.
  - `keyframe_frames` for order `[1,2,3]` with N = 7 per step: `[1, 7, 13]`. Expose it as a pure `keyframe_positions(ns: list[int]) -> list[int]` and test that.
- [ ] **Step 2: Run the tests and see them fail.**
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Write the sequence file.** Write `sequences/grooming.json` with one short motion prompt per step, written from looking at each keyframe pair in `out/grooming_keys/frame_NN.png`.
- [ ] **Step 6: Run the whole grooming sequence** in the background. Expected:
  - 11 segments;
  - `frames/` holds 1 + 11·6 = 67 frames;
  - warnings printed for 7→8 and 9→10, if the eye states in `cues.json` differ there;
  - every `keyframe_frames` frame is pixel-identical (`mean_abs_diff == 0`) to the matching `out/grooming_keys/frame_NN.png`. The runner saves the keyframe image itself at those positions.

### Task 9: Frames folder into the existing tracing

**Files:**
- Modify: `ST\sheet_frames.py` (move the per-frame body out of `main` into a function; `main`'s behaviour is unchanged)
- Create: `ST\trace_frames.py`
- Test: `ST\test_trace_frames.py`

**Interfaces:**
- Produces:
  - `sheet_frames.process_frame(canvas: np.ndarray, name: str, out_dir: str, a) -> dict`. This is the body from `inside = …` through `os.remove(wpath)`. It returns `{"eyes": [...cleaned], "eyes_closed": bool, "nose": dict | None}`, and writes `name.png` and `name.svg`. `a` carries `keep_eyes`, `line_min`, `line_max`, `speck` and `open_bottom`.
  - `trace_frames.py FRAMES_DIR --out DIR [--record RUN_JSON] [--line-min --line-max --speck --open-bottom --keep-eyes]`.
    - It reads `frame_*.png` in sorted order and calls `process_frame` for each, with no alignment.
    - It writes `DIR/cues.json` as `{"source": FRAMES_DIR, "canvas": [W, H], "frames": [{"frame": i, "file": "frame_NNNNN.svg", "eyes", "eyes_closed", "nose"}]}`, with `i` 1-based.
    - With `--record`, it adds `"eyes": {"states": [...], "isolated_flips": [...]}` to that `run.json`.
  - `eye_state(n_eyes: int) -> str`: 2 gives `"open"`, 0 gives `"closed"`, 1 gives `"partial"`.
  - `isolated_flips(states: list[str]) -> list[int]`: the 1-based frame numbers whose state differs from both neighbours, where both neighbours agree.

- [ ] **Step 1: Write the failing tests.**
  - `eye_state` for 0, 1 and 2.
  - `isolated_flips(["open","closed","open","open"]) == [2]`
  - `isolated_flips(["open","open","closed","closed"]) == []`
- [ ] **Step 2: Run the tests and see them fail.**
- [ ] **Step 3: Refactor `sheet_frames.py`**, then rerun it into `<scratchpad>\after_refactor`. Expected: every file is byte-identical to Task 1's `baseline_grooming`; check with `fc /b` or a Python hash loop.
- [ ] **Step 4: Implement `trace_frames.py`**, then run the tests and see them pass.
- [ ] **Step 5: Trace the sequence.**
  `PY trace_frames.py out\grooming_wan\frames --out out\grooming_wan\svg --record out\grooming_wan\run.json`.
  Expected: 67 SVGs and one `cues.json`. Report how many frames have each eye state, and the isolated flips.
- [ ] **Step 6: Place the kit eyes.**
  `PY place_eyes.py out\grooming_wan\svg ..\cat_kit.svg --set round --front <front_frame>`.
  Expected: 67 `frame_NNNNN_round.svg` files. `place_eyes.py` builds names with `file.replace(".svg", …)`, so five-digit names work unchanged.

### Task 10: Preview for AC

**Files:**
- Create: `ST\preview_seq.py`

**Interfaces:**
- Produces: `preview_seq.py DIR [--set round] [--fps 12] [--width 300] [--cols 12]`.
  - It renders each `cues.json` frame's `frame_NNNNN_<set>.svg` (or the plain `.svg` when `--set ""`) on white with Playwright, using the same `pg.locator("svg").screenshot()` approach as `render_turn.py`.
  - It writes `DIR/preview_<set>.gif` (`duration = round(1000/fps)` ms, `loop=0`) and `DIR/contact_<set>.png`: a grid of `--cols` columns with the frame number under each cell; keyframe frames are labelled `K`, read from `run.json` `keyframe_frames` when it is in `DIR/..`.

- [ ] **Step 1: Run it.**
  `PY preview_seq.py out\grooming_wan\svg --set round`.
  Expected: a GIF of 67 frames at 83 ms per frame, and the contact sheet.
- [ ] **Step 2: Run it again with `--set ""`** (traces without kit eyes), so line boil can be judged apart from the eyes.
- [ ] **Step 3: Check the GIF.** Open the first frame and a middle frame of the GIF in the image reader. Confirm the cat is drawn, not blank, and on the canvas.

### Task 11: README section and report

**Files:**
- Modify: `ST\README.md`. Add a section "In-betweens with Wan 2.2". Add `flf_runner.py`, `trace_frames.py` and `preview_seq.py` rows to the table.

- [ ] **Step 1: Write the section.** It covers:
  - starting `comfyui-wan` and stopping `comfyui-3d`, one at a time;
  - that `comfyui-3d` stays stopped until `docker start comfyui-3d`, even across a reboot;
  - the venv (`PY`);
  - the sequence file fields;
  - the four commands from keyframes to GIF;
  - fps above 16 being refused;
  - the blink rule;
  - the negative prompt doing nothing at CFG 1;
  - the measured times and memory.
- [ ] **Step 2: The controller asks AC** whether to restart `comfyui-3d` now. If AC says yes, run `docker stop comfyui-wan` then `docker start comfyui-3d`. Check that the `docker inspect` line from Task 3 Step 8 is identical and that `http://127.0.0.1:8188/system_stats` answers.
- [ ] **Step 3: Report to AC.** Cover:
  - what ran, with times per step and peak VRAM and RAM;
  - any memory fallback used;
  - endpoint diffs and style drift;
  - eye-state counts and flips;
  - deviations from the spec;
  - the GIF and contact-sheet paths, sent with SendUserFile.

  The head-turn sequence (spec build step 8) waits for a full-size sheet; say so.
