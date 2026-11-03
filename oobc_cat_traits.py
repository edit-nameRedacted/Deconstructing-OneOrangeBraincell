"""First-pass cat traits from r/OneOrangeBraincell posts, using a local vision model in Ollama.

For each post in a CSV made by oobc_top_week.py (it needs the reddit_url column), this script:
  1. looks the post up in the Arctic Shift archive to find its media
     (single image, every image of a gallery, or frames sampled from a video);
  2. downloads the media into a cache folder, shrinking each image to --max-side pixels;
  3. sends the images from one post together to the model in a single request, with a JSON schema
     the reply has to follow;
  4. writes one row per cat to <posts>_cats.csv, every raw reply to <posts>_cats_raw.jsonl, and
     <posts>_cats_review.html, a page showing each post's images beside its labels for checking by eye.

The fields per cat: % orange / white / other of the visible fur, main colour (orange_or_orange_and_white / tortie_or_calico / not_orange),
visibility, age class, body condition and estimated weight, coat pattern, and where the white is.
The model writes its visual cues *before* each label. Lessons from testing, built into the prompt:
  - It is told not to assume a cat is orange (the subreddit has brown tabbies and torbies too), and
    describes every cat; orange_cat_count counts only main_colour == orange_or_orange_and_white.
  - For the coat it answers yes/no (tabby stripes? brown/black patches? white fur?) and the script
    derives coat_pattern, because small models call ordinary orange tabby stripes "brown".
  - If visibility is poor it is told to answer "unclear" rather than guess age and weight.
The model thinks before answering (Ollama "think"), which keeps the cue fields descriptive; cue fields
also have a minimum length. --no-think is faster but the 9B model then copies labels into the cues.
Weight is the weakest field: a 4B model gave nearly every adult 4.5-5 kg. Treat body_condition as
the main measure and est_weight_kg as a rough guess.

Requirements: Python 3.9+, Pillow (pip install pillow), Ollama running locally with a vision
model pulled, and ffmpeg on PATH for videos (without it a video gets its single preview image).

Usage:
  ollama pull qwen3.5:9b          # 6.6 GB, fits a 12 GB card with room for 4 images
  python3 oobc_cat_traits.py oobc_top_30days.csv
  python3 oobc_cat_traits.py oobc_top_30days.csv --model gemma3:12b --out traits_gemma.csv

Re-running skips posts already answered by the same model and PROMPT_VERSION, and retries failures.
Use --redo to analyse everything again.
"""
import argparse, base64, csv, html, io, json, os, re, shutil, subprocess, sys, time
import urllib.error, urllib.parse, urllib.request

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is needed: pip install pillow")

ARCHIVE = "https://arctic-shift.photon-reddit.com/api/posts/ids"
UA = "oobc-research-script/0.1"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"  # external-preview.redd.it refuses script UAs

AGE = ["kitten", "youth", "adult", "senior", "unclear"]
BODY = ["underweight", "lean", "ideal", "overweight", "obese", "unclear"]
COAT = ["pure_orange", "orange_with_brown", "orange_with_white",
        "orange_with_brown_and_white", "unclear"]
WHITE_COVER = ["none", "minimal", "moderate", "extensive", "unclear"]
WHITE_LOC = ["chin_muzzle", "face_blaze", "neck_throat", "chest", "stomach_belly",
             "front_paws", "back_paws", "legs", "tail_tip", "back_flank", "other"]

PROMPT_VERSION = "v4"  # bump when the prompt or schema changes; resume only reuses replies from the same version

COLOUR = ["orange_or_orange_and_white", "tortie_or_calico", "not_orange"]
VIS = ["good", "partial", "poor"]
CUE = {"type": "string", "minLength": 25}  # forces a description, not a copy of the label
PCT = {"type": "integer", "minimum": 0, "maximum": 100}

SCHEMA = {
    "type": "object",
    "properties": {
        "cat_count": {"type": "integer"},
        "cats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "where_in_images": {"type": "string"},
                    "colour_cues": CUE,
                    "main_colour": {"type": "string", "enum": COLOUR},
                    "visibility": {"type": "string", "enum": VIS},
                    "age_cues": CUE,
                    "age_class": {"type": "string", "enum": AGE},
                    "body_cues": CUE,
                    "body_condition": {"type": "string", "enum": BODY},
                    "est_weight_kg": {"type": "number"},
                    "coat_cues": CUE,
                    "tabby_stripes": {"type": "boolean"},
                    "brown_or_black_patches": {"type": "boolean"},
                    "white_fur": {"type": "boolean"},
                    "white_coverage": {"type": "string", "enum": WHITE_COVER},
                    "white_locations": {"type": "array",
                                        "items": {"type": "string", "enum": WHITE_LOC}},
                    "pct_orange": PCT,
                    "pct_white": PCT,
                    "pct_other": PCT,
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["where_in_images", "colour_cues", "main_colour", "visibility",
                             "age_cues", "age_class", "body_cues", "body_condition", "est_weight_kg",
                             "coat_cues", "tabby_stripes", "brown_or_black_patches", "white_fur",
                             "white_coverage", "white_locations", "pct_orange", "pct_white",
                             "pct_other", "confidence"],
            },
        },
        "other_animals": {"type": "string"},
    },
    "required": ["cat_count", "cats", "other_animals"],
}

PROMPT = """You are coding photos of domestic cats for a research dataset. The {n} image(s) attached \
come from ONE social-media post{video_note}. The post comes from a forum about orange cats, but do not \
assume any cat is orange: look at the fur. Describe EVERY cat you can see. If the same cat appears in \
several images, describe it once. In other_animals, name any animals that are not cats as a short \
plain phrase, e.g. "one green iguana" or "none". Only living animals count: toys, figures and \
pictures do not.

For each cat, write the cues first, then the label. A cue field must describe what you actually SEE \
in this image (fur colours and where, face shape, body outline, size against objects) in at least one \
full sentence. Never just repeat a label name in a cue field.

where_in_images: e.g. "image 1, left; images 2-4".

colour_cues, then main_colour:
- orange_or_orange_and_white: the fur is orange, ginger, red or cream-orange. White patches, however large, still count here.
- tortie_or_calico: orange mixed with patches or stripes of brown, grey or black (tortoiseshell, torbie, calico).
- not_orange: brown, grey, black or silver tabby, black, grey, white, or any other colour without real orange. A brown tabby with warm-toned fur is not_orange.

visibility:
- good: most of the cat's body and face are clearly visible.
- partial: about half the cat is visible, or it is somewhat blurred.
- poor: the cat is mostly hidden, far away, very blurred, or seen only from behind or as a small part (an ear, a tail).
When visibility is poor, use "unclear" for age_class and body_condition and -1 for est_weight_kg.

age_cues, then age_class:
- kitten: under about 6 months. Head and ears large for the body, short muzzle, round face, small paws, fluffy fur.
- youth: about 6 months to 2 years. Adult proportions but lanky or slender, long legs, narrow face, no jowls.
- adult: about 2 to 10 years. Fully filled out, mature face; intact males may have broad cheeks.
- senior: over about 10 years. Bony spine or hips, sunken or thin look, scruffy or matted coat, cloudy eyes, thinning muzzle.
- unclear: the cat is too small, blurred or hidden to judge.

body_cues, then body_condition and est_weight_kg:
- body_condition: underweight (ribs, hips and spine visible), lean, ideal (visible waist), overweight (no waist, belly pad), obese (round, wide, sagging belly), or unclear. Long fur makes a cat look bigger; judge the body under it.
- est_weight_kg: your best single number for THIS cat, judged from its size against objects in the frame (hands, furniture, doors) and its body condition. Rough guide: 8-week kitten about 1 kg; small or slim adult 3-4 kg; typical adult 4-5 kg; large or overweight adult 5.5-7 kg; obese 7-10 kg. Use -1 if you cannot judge at all.

coat_cues, then three yes/no answers about the coat:
- tabby_stripes: true if the cat has tabby stripes, swirls or spots in a darker shade of its own colour. Almost every orange cat has darker-orange stripes. These stripes are not brown patches.
- brown_or_black_patches: on an orange or tortie/calico cat, true ONLY for patches of fur that are a different colour from the orange: brown, chocolate, grey or black (as on a tortoiseshell or calico). Darker orange tabby stripes are NOT brown patches, however dark they look. On a not_orange cat, false.
- white_fur: true only for clearly WHITE fur. Cream or pale-orange fur on the chest or belly is NOT white.

white_coverage (none if white_fur is false): none, minimal (small spots, e.g. a white chin or toes), moderate (chest, belly and paws), extensive (white is the main colour, orange mostly on head/back/tail), or unclear.

white_locations: every place you can SEE clearly white fur, from this list: chin_muzzle, face_blaze \
(white stripe up the face), neck_throat, chest, stomach_belly, front_paws, back_paws, legs (above the paws), \
tail_tip, back_flank, other. Use an empty list if there is no white. Only list places you can actually see; \
if the belly is hidden, do not guess it.

pct_orange, pct_white, pct_other: of the fur you can SEE on this cat, roughly what percentage is \
orange (including cream-orange and the darker orange tabby stripes), clearly white, and any other colour \
(brown, black, grey). The three must add up to 100. Use steps of 5. A cat with only a white chin is \
about 95/5/0; a typical orange-and-white bicolour about 60/40/0; a calico about 30/40/30.

confidence: your overall confidence in this cat's labels (low, medium, high).

If there is no cat at all, return cat_count 0 and an empty cats list."""


def http_get(url, ua=UA, timeout=60, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                raise
            err = e
        except Exception as e:
            err = e
        time.sleep(2 ** attempt)
    raise err


def post_id(row):
    m = re.search(r"/comments/([a-z0-9]+)", row.get("reddit_url", ""))
    return m.group(1) if m else (row.get("post_id") or row.get("id"))


def archive_lookup(ids):
    out = {}
    for i in range(0, len(ids), 100):
        data = json.loads(http_get(ARCHIVE + "?ids=" + ",".join(ids[i:i + 100])))["data"]
        out.update({p["id"]: p for p in data})
    return out


def media_plan(post, max_images):
    """Return (kind, [(source_url, ua)], video_url or None, duration)."""
    p = post
    if p.get("crosspost_parent_list"):
        p = p["crosspost_parent_list"][0]
    video = ((p.get("secure_media") or p.get("media") or {}) or {}).get("reddit_video")
    preview = (p.get("preview") or {}).get("images") or []
    preview_url = html.unescape(preview[0]["source"]["url"]) if preview else None
    if video:
        return "video", ([(preview_url, BROWSER_UA)] if preview_url else []), \
            video.get("fallback_url"), video.get("duration") or 0
    if p.get("is_gallery") and p.get("media_metadata"):
        order = [it["media_id"] for it in (p.get("gallery_data") or {}).get("items", [])] \
            or list(p["media_metadata"])
        urls = []
        for mid in order:
            m = p["media_metadata"].get(mid) or {}
            if m.get("status") not in (None, "valid") or m.get("e") != "Image":
                continue
            ext = (m.get("m") or "image/jpg").split("/")[-1].replace("jpeg", "jpg")
            urls.append((f"https://i.redd.it/{mid}.{ext}", UA))
        return "gallery", urls[:max_images], None, 0
    url = p.get("url") or ""
    if re.search(r"\.(jpe?g|png|webp)(\?|$)", url, re.I):
        return "image", [(url, UA)], None, 0
    if preview_url:  # gifs, imgur and other links: fall back to Reddit's preview still
        return "preview", [(preview_url, BROWSER_UA)], None, 0
    return "none", [], None, 0


def shrink(raw_bytes, max_side):
    im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def video_frames(video_url, duration, n, max_side, folder):
    if not shutil.which("ffmpeg"):
        return []
    mp4 = os.path.join(folder, "video.mp4")
    if not os.path.exists(mp4):
        with open(mp4, "wb") as f:
            f.write(http_get(video_url, timeout=180))
    if not duration:
        try:
            duration = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                capture_output=True, text=True).stdout.strip())
        except ValueError:
            duration = 10
    frames = []
    for k in range(n):  # evenly spaced, skipping the very start and end
        t = duration * (k + 1) / (n + 1)
        path = os.path.join(folder, f"frame{k + 1}.jpg")
        if not os.path.exists(path):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1",
                            "-vf", f"scale='min({max_side},iw)':'min({max_side},ih)':force_original_aspect_ratio=decrease",
                            "-q:v", "3", path], check=False)
        if os.path.exists(path):
            frames.append(open(path, "rb").read())
    return frames


def gather_images(pid, post, args):
    folder = os.path.join(args.media_dir, pid)
    os.makedirs(folder, exist_ok=True)
    kind, stills, video_url, duration = media_plan(post, args.max_images)
    images = []
    if kind == "video" and video_url:
        try:
            images = video_frames(video_url, duration, args.frames, args.max_side, folder)
        except Exception as e:
            print(f"  video download failed ({e}); using preview still", file=sys.stderr)
        if images:
            return kind, images
        kind = "video_preview"
    for i, (url, ua) in enumerate(stills, 1):
        path = os.path.join(folder, f"img{i}.jpg")
        try:
            if not os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(shrink(http_get(url, ua=ua), args.max_side))
            images.append(open(path, "rb").read())
        except Exception as e:
            print(f"  could not fetch {url[:70]} ({e})", file=sys.stderr)
    return kind, images


def ask_model(images, kind, args):
    video_note = " (frames sampled from a short video, in time order)" if kind == "video" else ""
    body = {
        "model": args.model,
        "messages": [{"role": "user",
                      "content": PROMPT.format(n=len(images), video_note=video_note),
                      "images": [base64.b64encode(b).decode() for b in images]}],
        "format": SCHEMA,
        "stream": False,
        "think": args.think,
        "keep_alive": "10m",
        "options": {"temperature": 0, "num_ctx": args.num_ctx, "seed": 1, "num_predict": args.max_tokens},
    }
    url = args.ollama.rstrip("/") + "/api/chat"
    for attempt in range(3):
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=args.timeout) as r:
                reply = json.load(r)
            if reply.get("done_reason") == "length" and body.get("think"):
                # thinking ran past the cap: ask again without it rather than lose the post
                print("  thinking hit --max-tokens; retrying this post without thinking", file=sys.stderr)
                body["think"] = False
                continue
            return (json.loads(reply["message"]["content"]), reply.get("message", {}).get("thinking", ""),
                    bool(body.get("think")))
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if "think" in msg and "think" in body:  # model without a thinking switch
                body.pop("think")
                continue
            raise RuntimeError(f"Ollama {e.code}: {msg[:300]}")
    raise RuntimeError("Ollama refused the request")


def fur_pct(c):
    """The model's three percentages, rescaled to sum to 100 (they sometimes don't)."""
    vals = [c.get(k) if isinstance(c.get(k), (int, float)) and c.get(k) >= 0 else 0
            for k in ("pct_orange", "pct_white", "pct_other")]
    total = sum(vals)
    if not total:
        return {"pct_orange": "", "pct_white": "", "pct_other": ""}
    return dict(zip(("pct_orange", "pct_white", "pct_other"), (round(100 * v / total) for v in vals)))


def n_orange(res):
    return sum(1 for c in res.get("cats") or [] if c.get("main_colour") == COLOUR[0])


def summary(res):
    return f"{len(res.get('cats') or [])} cat(s), {n_orange(res)} orange"


def coat_pattern(c):
    """Derived in code from the model's yes/no answers, so the label can't contradict them."""
    if c.get("main_colour") == "not_orange":
        return "not_orange"
    if c.get("visibility") == "poor" and not (c.get("white_fur") or c.get("brown_or_black_patches")):
        return "unclear"
    brown, white = bool(c.get("brown_or_black_patches")), bool(c.get("white_fur") or c.get("white_locations"))
    return {(False, False): "pure_orange", (True, False): "orange_with_brown",
            (False, True): "orange_with_white", (True, True): "orange_with_brown_and_white"}[brown, white]


def lb(kg):
    return round(kg * 2.2046, 1) if isinstance(kg, (int, float)) and kg > 0 else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("posts_csv")
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--out", default=None, help="per-cat CSV (default: <posts_csv>_cats.csv)")
    ap.add_argument("--raw", default=None, help="JSONL of raw replies (default: <posts_csv>_cats_raw.jsonl)")
    ap.add_argument("--media-dir", default="oobc_media")
    ap.add_argument("--frames", type=int, default=4, help="frames sampled per video")
    ap.add_argument("--max-images", type=int, default=4, help="images used per gallery")
    ap.add_argument("--max-side", type=int, default=896, help="longest side of each image sent, in px")
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--ollama", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=6000,
                    help="cap on thinking + answer tokens per post; past it the post is retried without thinking")
    ap.add_argument("--no-think", dest="think", action="store_false",
                    help="switch off the model's thinking step (faster, but cue fields get terse)")
    args = ap.parse_args()
    if not args.ollama.startswith("http"):
        args.ollama = "http://" + args.ollama
    args.ollama = args.ollama.replace("//0.0.0.0", "//127.0.0.1")  # OLLAMA_HOST=0.0.0.0 is a bind address, not one to connect to
    stem = os.path.splitext(args.posts_csv)[0]
    args.out = args.out or stem + "_cats.csv"
    args.raw = args.raw or stem + "_cats_raw.jsonl"

    rows = list(csv.DictReader(open(args.posts_csv, encoding="utf-8")))
    ids = [post_id(r) for r in rows]
    done = {}
    if os.path.exists(args.raw) and not args.redo:
        for line in open(args.raw, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("model") == args.model and rec.get("prompt") == PROMPT_VERSION and "result" in rec:
                done[rec["post_id"]] = rec
    todo = [i for i in ids if i and i not in done]
    print(f"{len(ids)} posts; {len(done)} already analysed with {args.model} (prompt {PROMPT_VERSION}); {len(todo)} to go",
          file=sys.stderr)
    posts = archive_lookup(todo) if todo else {}

    with open(args.raw, "a", encoding="utf-8") as raw:
        for n, pid in enumerate(todo, 1):
            post = posts.get(pid)
            rec = {"post_id": pid, "model": args.model, "prompt": PROMPT_VERSION}
            if not post:
                rec["error"] = "not in archive"
            else:
                kind, images = gather_images(pid, post, args)
                rec.update(media_kind=kind, n_images=len(images))
                if not images:
                    rec["error"] = "no usable images"
                else:
                    t0 = time.time()
                    try:
                        rec["result"], thinking, rec["thought"] = ask_model(images, kind, args)
                        if thinking:
                            rec["thinking"] = thinking
                        rec["seconds"] = round(time.time() - t0, 1)
                    except Exception as e:
                        rec["error"] = str(e)
            raw.write(json.dumps(rec, ensure_ascii=False) + "\n")
            raw.flush()
            if "result" in rec:
                done[pid] = rec
            res = rec.get("result") or {}
            print(f"[{n}/{len(todo)}] {pid} {rec.get('media_kind', '')} x{rec.get('n_images', 0)}: "
                  f"{rec.get('error') or summary(res)}"
                  f"{'  ' + str(rec['seconds']) + 's' if 'seconds' in rec else ''}", file=sys.stderr)

    # Per-cat table, in the order of the input CSV. One row with blank cat fields for posts with no cats.
    keep = ["rank", "score", "title", "posted_utc", "reddit_url"]
    cat_cols = ["main_colour", "visibility", "age_class", "age_cues", "body_condition", "est_weight_kg", "est_weight_lb", "body_cues",
                "coat_pattern", "tabby_stripes", "brown_or_black_patches", "white_fur",
                "white_coverage", "white_locations", "pct_orange", "pct_white", "pct_other", "coat_cues", "colour_cues",
                "confidence", "where_in_images"]
    header = ["post_id"] + [k for k in keep if k in rows[0]] + \
        ["media_kind", "n_images", "cat_count", "orange_cat_count", "cat_n"] + cat_cols + \
        ["white_" + w for w in WHITE_LOC] + ["other_animals", "model", "thought", "error"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for row, pid in zip(rows, ids):
            rec = done.get(pid)
            if rec is None:  # look for the last failed attempt, if any, to report its error
                rec = {"post_id": pid, "model": args.model, "error": "not analysed"}
                if os.path.exists(args.raw):
                    for line in open(args.raw, encoding="utf-8"):
                        r = json.loads(line)
                        if r["post_id"] == pid and r.get("model") == args.model \
                                and r.get("prompt") == PROMPT_VERSION:
                            rec = r
            res = rec.get("result") or {}
            base = {"post_id": pid, **{k: row[k] for k in keep if k in row},
                    "media_kind": rec.get("media_kind", ""), "n_images": rec.get("n_images", ""),
                    "cat_count": len(res.get("cats") or []) if "result" in rec else "",
                    "orange_cat_count": n_orange(res) if "result" in rec else "",
                    "other_animals": res.get("other_animals", ""), "model": rec.get("model"),
                    "thought": {True: "yes", False: "no"}.get(rec.get("thought"), ""),
                    "error": rec.get("error", "")}
            cats = res.get("cats") or []
            if not cats:
                w.writerow(base)
            for i, c in enumerate(cats, 1):
                locs = c.get("white_locations") or []
                kg = c.get("est_weight_kg")
                w.writerow({**base, "cat_n": i,
                            **{k: c.get(k, "") for k in cat_cols if k not in
                               ("white_locations", "est_weight_kg", "est_weight_lb", "coat_pattern",
                                "pct_orange", "pct_white", "pct_other")},
                            **fur_pct(c),
                            "coat_pattern": coat_pattern(c),
                            "est_weight_kg": kg if isinstance(kg, (int, float)) and kg > 0 else "",
                            "est_weight_lb": lb(kg),
                            "white_locations": ";".join(locs),
                            **{"white_" + x: int(x in locs) for x in WHITE_LOC}})
    review = os.path.splitext(args.out)[0] + "_review.html"
    write_review(review, args.out, args.media_dir)
    print(f"wrote {args.out}, {args.raw} and {review}", file=sys.stderr)


def write_review(path, cats_csv, media_dir):
    """A plain page: each post's images next to the model's labels, for checking by eye."""
    esc = html.escape
    rel = os.path.relpath(media_dir, os.path.dirname(os.path.abspath(path)) or ".")
    by_post = {}
    for r in csv.DictReader(open(cats_csv, encoding="utf-8")):
        by_post.setdefault(r["post_id"], []).append(r)
    parts = ["<!doctype html><meta charset=utf-8><title>Cat traits review</title><style>"
             "body{font:14px system-ui,sans-serif;margin:16px;background:#fafafa;color:#222}"
             ".post{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;margin:0 0 16px}"
             ".imgs img{height:180px;margin:0 4px 4px 0;border-radius:4px}"
             "table{border-collapse:collapse;margin-top:6px}td{padding:2px 10px 2px 0;vertical-align:top}"
             "td:first-child{color:#777;white-space:nowrap}.cues{color:#555;font-size:12px}"
             "@media(prefers-color-scheme:dark){body{background:#181818;color:#ddd}"
             ".post{background:#222;border-color:#333}}</style>"]
    for pid, rs in by_post.items():
        r0 = rs[0]
        folder = os.path.join(media_dir, pid)
        files = sorted(f for f in os.listdir(folder) if f.endswith(".jpg")) if os.path.isdir(folder) else []
        parts.append(f"<div class=post><b>#{esc(r0.get('rank', ''))} {esc(r0.get('title', ''))}</b> "
                     f"<a href='{esc(r0.get('reddit_url', ''))}'>reddit</a> · {esc(r0['media_kind'])} · "
                     f"{esc(r0['cat_count'] or '0')} cat(s), {esc(r0['orange_cat_count'] or '0')} orange {esc(r0['error'])}<div class=imgs>"
                     + "".join(f"<img src='{esc(rel)}/{pid}/{f}'>" for f in files) + "</div>")
        for r in rs:
            if not r["cat_n"]:
                continue
            parts.append(
                f"<table><tr><td>cat {r['cat_n']}</td><td><b>{esc(r['main_colour'])}</b> · {esc(r['where_in_images'])} · visibility "
                f"{esc(r['visibility'])} · confidence {esc(r['confidence'])}</td></tr>"
                f"<tr><td>age</td><td><b>{esc(r['age_class'])}</b> <span class=cues>{esc(r['age_cues'])}</span></td></tr>"
                f"<tr><td>body</td><td><b>{esc(r['body_condition'])}, ~{esc(r['est_weight_kg'])} kg "
                f"({esc(r['est_weight_lb'])} lb)</b> <span class=cues>{esc(r['body_cues'])}</span></td></tr>"
                f"<tr><td>coat</td><td><b>{esc(r['coat_pattern'])}</b>, {esc(r['pct_orange'])}% orange / "
                f"{esc(r['pct_white'])}% white / {esc(r['pct_other'])}% other, white: {esc(r['white_coverage'])} "
                f"[{esc(r['white_locations'])}] <span class=cues>{esc(r['coat_cues'])}</span></td></tr></table>")
        if r0["other_animals"] and r0["other_animals"].strip(". ").lower() not in ("none", ""):
            parts.append(f"<div class=cues>Other animals: {esc(r0['other_animals'])}</div>")
        parts.append("</div>")
    open(path, "w", encoding="utf-8").write("".join(parts))


if __name__ == "__main__":
    main()
