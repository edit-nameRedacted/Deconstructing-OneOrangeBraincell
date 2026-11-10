"""Wan 2.2 first/last-frame in-between runner: pure frame maths and keyframe IO."""
import json
import math
import os
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat


def round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def wan_length(seconds: float) -> tuple[int, float, bool]:
    if seconds <= 0:
        raise ValueError("seconds must be > 0")
    L = 4 * round_half_up(16 * seconds / 4) + 1
    capped = L > 81
    if capped:
        L = 81
    return L, (L - 1) / 16, capped


def pick_frames(L: int, fps: float, seconds: float | None = None) -> list[int]:
    if fps <= 0:
        raise ValueError("fps must be > 0")
    if fps > 16:
        raise ValueError("fps > 16 needs RIFE interpolation (Wan generates 16 fps)")
    if seconds is None:
        N = round_half_up((L - 1) / 16 * fps) + 1
        picks = [min(round_half_up(16 * j / fps), L - 1) for j in range(N)]
    else:
        N = round_half_up(seconds * fps) + 1
        if N < 2:
            raise ValueError("seconds*fps must give at least 2 frames")
        if N > L:
            raise ValueError(f"{N} frames wanted but Wan made only {L}: needs RIFE interpolation")
        picks = [min(round_half_up(j * (L - 1) / (N - 1)), L - 1) for j in range(N)]
    picks[-1] = L - 1
    return picks


def pick_by_motion(motion: list[float], N: int, ease: float = 0.5) -> list[int]:
    """Pick N of the len(motion)+1 generated frames so each picked frame moves an equal share of the step's total
    movement (motion[i] = change from frame i to i+1), eased in and out by `ease` (0 = even, 1 = full smoothstep).
    Wan tends to do a step's move in a short burst and hold still around it; picking by the clock then turns the burst
    into a one-frame snap. First and last frame are always picked; no frame is picked twice."""
    L = len(motion) + 1
    total = sum(motion)
    if total <= 0:
        return [min(round_half_up(j * (L - 1) / (N - 1)), L - 1) for j in range(N)]
    cum = [0.0]
    for m in motion:
        cum.append(cum[-1] + m / total)
    picks = []
    for j in range(N):
        t = j / (N - 1)
        t += ease * (t * t * (3 - 2 * t) - t)
        picks.append(min(range(L), key=lambda i: abs(cum[i] - t)))
    picks[0], picks[-1] = 0, L - 1
    for j in range(1, N):                      # strictly increasing: nudge repeats forward, then back from the end
        picks[j] = max(picks[j], picks[j - 1] + 1)
    for j in range(N - 2, -1, -1):
        picks[j] = min(picks[j], picks[j + 1] - 1)
    return picks


def join_segments(segs: list[list], loop: bool) -> list:
    out = list(segs[0])
    for s in segs[1:]:
        out += s[1:]
    return out[:-1] if loop else out


@dataclass
class Geometry:
    W: int
    H: int
    scale: float
    w: int
    h: int
    pw: int
    ph: int
    ox: int
    oy: int


def fit_geometry(W: int, H: int, budget: int = 400_000, mult: int = 16) -> Geometry:
    scale = math.sqrt(budget / (W * H))
    w, h = round_half_up(W * scale), round_half_up(H * scale)
    pw, ph = -(-w // mult) * mult, -(-h // mult) * mult
    return Geometry(W, H, scale, w, h, pw, ph, (pw - w) // 2, (ph - h) // 2)


def _flatten(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info:
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    return img.convert("RGB")


def to_wan(img: Image.Image, g: Geometry) -> Image.Image:
    small = _flatten(img).resize((g.w, g.h), Image.LANCZOS)
    canvas = Image.new("RGB", (g.pw, g.ph), "white")
    canvas.paste(small, (g.ox, g.oy))
    return canvas


def from_wan(img: Image.Image, g: Geometry) -> Image.Image:
    crop = img.crop((g.ox, g.oy, g.ox + g.w, g.oy + g.h))
    return crop.resize((g.W, g.H), Image.LANCZOS)


def mean_abs_diff(a: Image.Image, b: Image.Image) -> float:
    return sum(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean) / 3


def load_keys(src):
    """Dir (sheet_frames output) -> ({frame: img}, {frame: eyes_closed}); list of PNGs -> keys 1..n, eyes None."""
    if isinstance(src, (str, os.PathLike)):
        d = str(src)
        with open(os.path.join(d, "cues.json"), encoding="utf-8") as f:
            entries = json.load(f)["frames"]
        items = [(e["frame"], os.path.join(d, e["file"].replace(".svg", ".png"))) for e in entries]
        eyes = {e["frame"]: e["eyes_closed"] for e in entries}
    else:
        items = list(enumerate(src, 1))
        eyes = None
    imgs, size = {}, None
    for key, path in items:
        if not os.path.isfile(path):
            raise ValueError(f"missing keyframe file: {path}")
        im = _flatten(Image.open(path))
        if size is None:
            size = im.size
        elif im.size != size:
            raise ValueError(f"{os.path.basename(path)}: size {im.size} != {size}")
        imgs[key] = im
    return imgs, eyes


# ---------------------------------------------------------------- ComfyUI client + CLI
import argparse
import copy
import hashlib
import io
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ST_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPH_PATH = os.path.join(ST_DIR, "wan22_flf2v_12gb_api.json")
STYLE_TAIL = ("Flat-colour 2D cartoon with clean dark brown outlines on a plain white background, "
              "static camera, no shading.")
MODEL_TITLES = {"unet_high": "unet_name", "unet_low": "unet_name", "lora_high": "lora_name",
                "lora_low": "lora_name", "vae": "vae_name", "clip": "clip_name"}


def patch_graph(graph: dict, values: dict) -> dict:
    out = copy.deepcopy(graph)
    by_title = {n.get("_meta", {}).get("title"): n for n in out.values()}
    missing = [t for t in values if t not in by_title]
    if missing:
        raise KeyError(f"graph has no node titled: {', '.join(missing)}")
    for title, inputs in values.items():
        by_title[title]["inputs"].update(inputs)
    return out


def check_prompt_response(resp: dict) -> str:
    msgs = [e.get("message", "") + " " + e.get("details", "")
            for n in (resp.get("node_errors") or {}).values() for e in n.get("errors", [])]
    if resp.get("error") or msgs:
        top = resp.get("error")
        top = top.get("message", top) if isinstance(top, dict) else top
        raise RuntimeError(f"ComfyUI rejected prompt: {top}; " + "; ".join(m.strip() for m in msgs))
    if "prompt_id" not in resp:
        raise RuntimeError(f"unexpected /prompt response: {json.dumps(resp)[:500]}")
    return resp["prompt_id"]


class ComfyClient:
    def __init__(self, base="http://127.0.0.1:8189", timeout=1800):
        self.base, self.timeout = base.rstrip("/"), timeout

    def _open(self, req):
        try:
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 400:  # /prompt validation errors come as 400 with a JSON body
                return e.read()
            raise
        except urllib.error.URLError as e:
            raise RuntimeError(f"ComfyUI not reachable at {self.base} — is comfyui-wan running?") from e

    def _json(self, path, data=None):
        req = urllib.request.Request(self.base + path, data=None if data is None else json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(self._open(req))

    def upload(self, png_path, name=None) -> str:
        name = name or os.path.basename(png_path)
        b = uuid.uuid4().hex
        body = b""
        for k, v in (("overwrite", "true"), ("type", "input")):
            body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        body += (f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
                 f'Content-Type: image/png\r\n\r\n').encode()
        with open(png_path, "rb") as f:
            body += f.read()
        body += f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(self.base + "/upload/image", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        return json.loads(self._open(req))["name"]

    def queue(self, graph) -> str:
        return check_prompt_response(self._json("/prompt", {"prompt": graph, "client_id": uuid.uuid4().hex}))

    def wait(self, prompt_id) -> dict:
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            h = self._json(f"/history/{prompt_id}").get(prompt_id)
            if h:
                st = h.get("status", {})
                if st.get("status_str") == "error":
                    msgs = [m[1].get("exception_message", str(m[1])) for m in st.get("messages", [])
                            if m and m[0] == "execution_error"]
                    raise RuntimeError(f"ComfyUI job {prompt_id} failed: {'; '.join(msgs) or st}")
                if h.get("outputs"):
                    return h
            time.sleep(2)
        raise TimeoutError(f"ComfyUI job {prompt_id} not finished after {self.timeout}s")

    def images(self, history) -> list:
        files = [i for o in history["outputs"].values() for i in o.get("images", []) if i.get("type") == "output"]
        files.sort(key=lambda i: i["filename"])
        return [self._open(urllib.request.Request(
            self.base + "/view?" + urllib.parse.urlencode(
                {"filename": i["filename"], "subfolder": i.get("subfolder", ""), "type": "output"})))
            for i in files]

    def system_stats(self) -> dict:
        return self._json("/system_stats")


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""


def parse_mem_mb(s):
    """'12.3GiB / 31.2GiB' -> 12.3*1024 (first figure); None if unparsable."""
    m = re.match(r"\s*([\d.]+)\s*([KMGT]?i?B)", s or "", re.I)
    if not m:
        return None
    f = {"b": 1 / 1048576, "kb": 1 / 1024, "kib": 1 / 1024, "mb": 1, "mib": 1, "gb": 1024, "gib": 1024,
         "tb": 1048576, "tib": 1048576}[m.group(2).lower()]
    return float(m.group(1)) * f


class MemorySampler:
    def __init__(self, interval=2.0):
        self.interval, self.peak_vram_mb, self.peak_ram_mb = interval, None, None
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _sample(self):
        v = _run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).splitlines()
        try:
            self.peak_vram_mb = max(self.peak_vram_mb or 0, float(v[0]))
        except (IndexError, ValueError):
            pass
        r = parse_mem_mb(_run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", "comfyui-wan"]))
        if r is not None:
            self.peak_ram_mb = max(self.peak_ram_mb or 0, r)

    def _loop(self):
        while not self._stop.is_set():
            self._sample()
            self._stop.wait(self.interval)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self._t.join()


def run_segment(client, graph, start, end, seconds, prompt, seed, g, out_dir, tag="seg"):
    L, D, capped = wan_length(seconds)
    if capped:
        print(f"WARNING: {seconds}s exceeds Wan's 81-frame cap; clamped to L=81 ({D}s)")
    tmp = out_dir.rstrip("/\\") + "_in"  # keep uploads out of the gen_* folder
    os.makedirs(tmp, exist_ok=True)
    names = []
    for side, im in (("start", start), ("end", end)):
        p = os.path.join(tmp, f"{tag}_{side}.png")
        to_wan(im, g).save(p)
        names.append(client.upload(p, f"{tag}_{side}.png"))
    pfx = f"flf/{tag}_{seed}_{time.time_ns()}"
    gr = patch_graph(graph, {
        "start_image": {"image": names[0]}, "end_image": {"image": names[1]},
        "positive": {"text": f"{prompt}. {STYLE_TAIL}"},
        "flf2v": {"width": g.pw, "height": g.ph, "length": L},
        "sampler_high": {"noise_seed": seed}, "sampler_low": {"noise_seed": seed},
        "save": {"filename_prefix": pfx}})
    imgs = client.images(client.wait(client.queue(gr)))
    if len(imgs) != L:
        raise RuntimeError(f"expected {L} frames from ComfyUI, got {len(imgs)}")
    frames = []
    for i, b in enumerate(imgs):
        fr = from_wan(Image.open(io.BytesIO(b)).convert("RGB"), g)
        fr.save(os.path.join(out_dir, f"gen_{i:03d}.png"))
        frames.append(fr)
    return frames


def plan_steps(order, loop):
    order = list(order)
    if loop and order[-1] != order[0]:
        order.append(order[0])
    seen, steps = set(), []
    for a, b in zip(order, order[1:]):
        steps.append((a, b, "reverse" if (b, a) in seen else "new"))
        if steps[-1][2] == "new":
            seen.add((a, b))
    return steps


def blink_warnings(steps, eyes_closed):
    if not eyes_closed:
        return []
    out = []
    for a, b, _ in steps:
        if eyes_closed[a] != eyes_closed[b]:
            d = "open→closed" if eyes_closed[b] else "closed→open"
            out.append(f"step {a}→{b}: eyes {d} while the pose changes — "
                       "a blink and a head turn should not share a step")
    return out


def segment_key(a, b, seconds, prompt, seed, g, graph, img_a, img_b):
    """seconds = GENERATION seconds; prompt = full text as sent (with STYLE_TAIL); images are hashed by content."""
    px = [hashlib.sha1(im.convert("RGB").tobytes()).hexdigest() for im in (img_a, img_b)]
    blob = json.dumps({"a": a, "b": b, "seconds": seconds, "prompt": prompt, "seed": seed,
                       "g": g.__dict__, "graph": graph, "px": px}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()


def keyframe_positions(ns):
    pos = [1]
    for n in ns:
        pos.append(pos[-1] + n - 1)
    return pos


def keyframe_frames(ns, order, loop, front):
    """Output frame number of each order entry, and of the first occurrence of `front`."""
    kf = keyframe_positions(ns)
    if loop:
        kf[-1] = 1  # the closing entry wraps to the first frame (join_segments drops the duplicate)
    return kf, kf[order.index(front)] if front in order else None


def validate_cfg(cfg):
    for k in ("name", "keys", "fps", "seconds", "seed", "default_prompt", "order"):
        if k not in cfg:
            raise ValueError(f"sequence file is missing required key '{k}'")
    if cfg.get("front") is not None and cfg["front"] not in cfg["order"]:
        raise ValueError(f"front {cfg['front']} is not in order")


def build_plan(cfg, keys, eyes):
    """Validate everything and return (per-step plan dicts, blink warnings). No GPU, no server."""
    order = cfg["order"]
    for k in order:
        if k not in keys:
            raise ValueError(f"order keyframe {k} not in keys")
    steps = plan_steps(order, cfg.get("loop", False))
    per = cfg.get("steps", {})
    used = {f"{a}-{b}" for a, b, _ in steps}
    for k in per:
        if k not in used:
            print(f"WARNING: steps['{k}'] is not an adjacent pair in the order; unused")
    for a, b, mode in steps:
        if mode == "reverse" and f"{a}-{b}" in per and "prompt" in per[f"{a}-{b}"]:
            print(f"WARNING: steps['{a}-{b}'] targets a reverse step; its prompt is ignored (uses {b}-{a} reversed)")
    plan, fwd_L = [], {}
    for a, b, mode in steps:
        s = per.get(f"{a}-{b}", {})
        sec = s.get("seconds", cfg["seconds"])
        gen = max(sec, s.get("gen_seconds", cfg.get("gen_seconds", 1.0)))
        prompt = s.get("prompt", cfg["default_prompt"])
        if mode == "reverse":
            L, gen = fwd_L[(b, a)], None
        else:
            L = fwd_L[(a, b)] = wan_length(gen)[0]
        picks = pick_frames(L, cfg["fps"], seconds=sec)  # raises if impossible
        plan.append({"a": a, "b": b, "mode": mode, "seconds": sec, "gen_seconds": gen, "prompt": prompt,
                     "L": L, "picks": picks, **({"seed": s["seed"]} if "seed" in s else {})})
    return plan, blink_warnings(steps, eyes)


def write_seg(seg_dir, info):
    with open(os.path.join(seg_dir, "seg.json"), "w", encoding="utf-8") as f:
        json.dump(info, f)


def read_seg(seg_dir):
    try:
        with open(os.path.join(seg_dir, "seg.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _load_cached(seg_dir, key, L):
    try:
        with open(os.path.join(seg_dir, "seg.json"), encoding="utf-8") as f:
            ok = json.load(f).get("key") == key
        paths = [os.path.join(seg_dir, f"gen_{i:03d}.png") for i in range(L)]
        if ok and all(os.path.isfile(p) for p in paths):
            return [Image.open(p).convert("RGB") for p in paths]
    except (OSError, ValueError):
        pass
    return None


def run_sequence(cfg, keys, graph, plan, warns, url, exact=True, args_record=None):
    root = os.path.join(ST_DIR, "out", cfg["name"])
    frames_dir = os.path.join(root, "frames")
    g = fit_geometry(*next(iter(keys.values())).size, budget=cfg.get("budget", 400_000))
    titled = {n["_meta"]["title"]: n["inputs"] for n in graph.values() if "_meta" in n}
    models = {t: titled[t][k] for t, k in MODEL_TITLES.items()}
    client = ComfyClient(url)
    version = client.system_stats().get("system", {}).get("comfyui_version")
    seed = cfg["seed"]
    gens, diffs, steps_out, segs = {}, {}, [], []
    with MemorySampler() as mem:
        for s in plan:
            a, b, t0 = s["a"], s["b"], time.time()
            mode, generated = s["mode"], None
            if mode == "reverse":
                gen, diff = gens[(b, a)][::-1], {"start": diffs[(b, a)]["end"], "end": diffs[(b, a)]["start"]}
            else:
                seg_dir = os.path.join(root, "raw", f"seg_{a}-{b}")
                os.makedirs(seg_dir, exist_ok=True)
                step_seed = s.get("seed", seed)   # a step can have its own seed (another take of the same move)
                key = segment_key(a, b, s["gen_seconds"], f"{s['prompt']}. {STYLE_TAIL}", step_seed, g, graph,
                                  keys[a], keys[b])
                gen = _load_cached(seg_dir, key, s["L"])
                mode = "cached"
                if gen is None:
                    mode = "new"
                    t1 = time.time()
                    with MemorySampler() as seg_mem:
                        gen = run_segment(client, graph, keys[a], keys[b], s["gen_seconds"], s["prompt"], step_seed, g,
                                          seg_dir, tag=f"{cfg['name']}_{a}-{b}")
                    write_seg(seg_dir, {"key": key, "L": s["L"], "wall_seconds": round(time.time() - t1, 1),
                                        "peak_vram_mb": seg_mem.peak_vram_mb, "peak_ram_mb": seg_mem.peak_ram_mb,
                                        "comfyui_version": version})
                else:  # the real generation's stats; None if seg.json predates them
                    generated = read_seg(seg_dir)
                    generated = generated if "wall_seconds" in generated else None
                diff = {"start": mean_abs_diff(gen[0], keys[a]), "end": mean_abs_diff(gen[-1], keys[b])}
                gens[(a, b)], diffs[(a, b)] = list(gen), diff
            gen = list(gen)
            picks = s["picks"]
            if cfg.get("retime", "motion") == "motion":   # by how far Wan's frames moved, not by the clock
                picks = pick_by_motion([mean_abs_diff(x, y) for x, y in zip(gen, gen[1:])], len(picks))
            if exact:
                gen[0], gen[-1] = keys[a], keys[b]
            segs.append([gen[i] for i in picks])
            steps_out.append({"pair": f"{a}-{b}", "a": a, "b": b, "mode": mode, "seconds": s["seconds"],
                              "gen_seconds": s["gen_seconds"], "fps": cfg["fps"], "L": s["L"],
                              "D": (s["L"] - 1) / 16, "N": len(s["picks"]), "picks": picks, "prompt": s["prompt"],
                              "seed": s.get("seed", seed),
                              "wall_seconds": round(time.time() - t0, 1), "endpoint_diff": diff,
                              **({"generated": generated} if mode == "cached" else {})})
            print(f"step {a}->{b} [{mode}] L={s['L']} N={len(s['picks'])} "
                  f"diff start={diff['start']:.2f} end={diff['end']:.2f}")
    loop = cfg.get("loop", False)
    frames = join_segments(segs, loop)
    shutil.rmtree(frames_dir, ignore_errors=True)  # only now: a failed run keeps the previous output; stale frames must not survive
    os.makedirs(frames_dir)
    for n, im in enumerate(frames, 1):
        im.save(os.path.join(frames_dir, f"frame_{n:05d}.png"))
    order = [plan[0]["a"]] + [s["b"] for s in plan]
    kf, front_frame = keyframe_frames([len(s["picks"]) for s in plan], order, loop, cfg.get("front"))
    run = {"args": args_record or cfg, "seed": seed, "style_tail": STYLE_TAIL, "steps": steps_out,
           "models": models, "comfyui_version": version, "peak_vram_mb": mem.peak_vram_mb,
           "peak_ram_mb": mem.peak_ram_mb, "exact_endpoints": exact, "geometry": g.__dict__,
           "blink_warnings": warns, "order": order, "loop": loop, "gen_seconds": cfg.get("gen_seconds", 1.0),
           "retime": cfg.get("retime", "motion"),
           "keyframe_frames": kf, "total_frames": len(frames),
           "front_frame": front_frame}
    with open(os.path.join(root, "run.json"), "w", encoding="utf-8") as f:
        json.dump(run, f, indent=2)
    return run


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # cp1252 consoles choke on →
    ap = argparse.ArgumentParser()
    ap.add_argument("--sequence", help="sequence JSON (see sequences/grooming.json)")
    ap.add_argument("--dry-run", action="store_true", help="validate and print the plan; no server contact")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--name")
    ap.add_argument("--seconds", type=float, default=0.5, help="playback length")
    ap.add_argument("--gen-seconds", type=float, default=1.0, help="minimum Wan clip length (short clips drift)")
    ap.add_argument("--fps", type=float, default=12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--prompt", default="the character moves")
    ap.add_argument("--budget", type=int, default=400_000)
    ap.add_argument("--no-exact-endpoints", action="store_true")
    ap.add_argument("--retime", choices=("motion", "clock"),
                    help="pick frames by how far Wan's frames moved (default; smooths Wan's bursts) or by the clock")
    ap.add_argument("--url", default="http://127.0.0.1:8189")
    a = ap.parse_args(argv)
    with open(GRAPH_PATH, encoding="utf-8") as f:
        graph = json.load(f)

    if a.sequence:
        with open(a.sequence, encoding="utf-8") as f:
            cfg = json.load(f)
        validate_cfg(cfg)
        src = cfg["keys"]
        src = [os.path.join(ST_DIR, p) for p in src] if isinstance(src, list) else os.path.join(ST_DIR, src)
        record = {"sequence": a.sequence, **cfg}
    else:
        if not (a.start and a.end and a.name):
            ap.error("--start, --end and --name are required without --sequence")
        src = [a.start, a.end]
        cfg = {"name": a.name, "fps": a.fps, "seconds": a.seconds, "gen_seconds": a.gen_seconds, "seed": a.seed,
               "order": [1, 2], "loop": False, "default_prompt": a.prompt, "budget": a.budget}
        record = vars(a)
    if a.retime:
        cfg["retime"] = a.retime
    keys, eyes = load_keys(src)
    for t, refs in cfg.get("match_body", {}).items():   # e.g. {"3": [2, 4]}: a pose drawn broader than its neighbours
        from body_match import match_width             # cv2/numpy: only loaded when asked for
        keys[int(t)] = match_width(keys[int(t)], [keys[r] for r in refs])
        print(f"keyframe {t}: body width matched to keyframes {refs}")
    plan, warns = build_plan(cfg, keys, eyes)

    total = len(join_segments([[0] * len(s["picks"]) for s in plan], cfg.get("loop", False)))
    for s in plan:
        print(f"{s['a']:>2}->{s['b']:<2} {s['mode']:<7} L={s['L']} N={len(s['picks'])} "
              f"play={s['seconds']}s gen={s['gen_seconds']}s  {s['prompt']}")
    for w in warns:
        print("WARNING:", w)
    print(f"expected frames: {total}")
    if a.dry_run:
        return
    run = run_sequence(cfg, keys, graph, plan, warns, a.url, not a.no_exact_endpoints, record)
    print(f"total={run['total_frames']} keyframe_frames={run['keyframe_frames']} front_frame={run['front_frame']} "
          f"peak_vram={run['peak_vram_mb']} peak_ram={run['peak_ram_mb']}")
    if a.sequence:
        print(f"next (Tasks 9-10): trace/export out/{cfg['name']}/frames, front frame = {run['front_frame']}")


if __name__ == "__main__":
    main()
