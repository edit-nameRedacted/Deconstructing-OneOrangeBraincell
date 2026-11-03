"""'What the internet thinks': word-family frequencies in each post's comments.
Excludes bots, deleted/removed comments and the post author's own replies. Links are stripped.
Two versions per family: share of all words (every commenter counts the same) and an upvote-weighted
version (each comment weighted by max(score, 0) + 1, so endorsed comments count more).
Families are fixed lists, written after looking at the corpus vocabulary but without hand codes."""
import csv, glob, json, math, os, re, collections
here = os.path.dirname(os.path.abspath(__file__)); arc = os.path.join(here, "..")
posts = {p["id"]: p for p in map(json.loads, open(os.path.join(arc, "heyday_posts_raw.jsonl"), encoding="utf-8"))}
BOTS = {"automoderator", "savevideo", "savevideobot", "remindmebot", "haikusbot", "sneakpeekbot", "gifreversingbot",
        "amputatorbot", "wikimobilelinkbot", "auddbot", "songfinderbot", "couldwouldshouldbot", "same_subreddit_bot",
        "sub_doesnt_exist_bot", "alphabet_order_bot", "random-gif-bot", "upside_down-bot", "exclaim_bot", "good_human_bot_v2",
        "of_patrol_bot", "friendly_bot_", "oppai_bot", "repostsleuthbot", "stabbot", "vredditdownloader"}
# "orange" used to mean dumb (community usage); hand-checked on all matches, colour uses excluded
ORANGE_DUMB = r"""orange (?:cat )?(?:behaviou?r|things|moments?|energy|vibes|activit(?:y|ies)|logic|thoughts?|brain(?! ?cells?))|(?<!from )(?:so|very|too|peak|extra|max(?:imum)?|truly|certified|full|such|being|just|most|ultra|pure)(?: very)? orange\b(?! (?:cats?|boys?|bois?|girls?|kitt(?:y|ies|ens?)|tabb(?:y|ies)|fur|hair|bab(?:y|ies)|guys?|man|men|lady|ones?|fluff|floof|males?|females?|and white|colou?r|in colou?r|marmalade|sphynx|stripes?|coat|tom|patch(?:es)?|eyes?|nose|tail|paws?)\b)(?! too)|(?:he|she|they)(?:'s| s| is| are| was) (?:so |very |just |too |extra )?orange\b(?! (?:cats?|boys?|bois?|girls?|kitt(?:y|ies|ens?)|tabb(?:y|ies)|fur|hair|bab(?:y|ies)|guys?|man|men|lady|ones?|fluff|floof|males?|females?|and white|colou?r|in colou?r|marmalade|sphynx|stripes?|coat|tom|patch(?:es)?|eyes?|nose|tail|paws?)\b)(?! too| with| like)|(?<!back )(?<!orange )(?:to|ever) orange\b(?! (?:cats?|boys?|bois?|girls?|kitt(?:y|ies|ens?)|tabb(?:y|ies)|fur|hair|bab(?:y|ies)|guys?|man|men|lady|ones?|fluff|floof|males?|females?|and white|colou?r|in colou?r|marmalade|sphynx|stripes?|coat|tom|patch(?:es)?|eyes?|nose|tail|paws?)\b)|orang(?:ing|ed)\b|orange af\b"""
FAM = {  # single words / emoji, and multi-word phrases (matched on the cleaned text)
 "cute":   {"w": "cute cutie cuties adorable sweet sweetie precious pretty beautiful handsome gorgeous lovely cuddly floofy majestic", "p": ""},
 "funny":  {"w": "lol lmao lmfao rofl haha hahaha hahahaha hehe funny hilarious laughing laughed laugh silly goofy goof derp derpy ridiculous 😂 🤣", "p": "i'm dead|i'm dying|i am dying|can't stop laughing"},
 "braincell": {"w": "braincell braincells", "p": "brain cell|brain cells|one cell|the cell"},
 "dumb":   {"w": "dumb stupid idiot idiots dummy dumbass dense brainless airhead dork doofus doof dingus derp derpy buffering loading smoothbrain", "p": ORANGE_DUMB + "|smooth brain|head empty|empty head|no thoughts|zero thoughts|not a single thought|nobody home|lights are on|silly goose"},
 "smart":  {"w": "smart smarter clever genius intelligent brilliant mastermind outsmarted outsmart calculated figured", "p": "big brain|galaxy brain|evil genius|figured it out|has the braincell|has the brain cell|his turn|her turn"},
 "body":   {"w": "chonk chonky chonker chunk chunky fat fatty thicc thick loaf round chubby pudgy heavy floof floofy fluffy fluff", "p": "absolute unit|big boy|big guy"},
 "calm":   {"w": "relaxed chill cozy comfy comfortable sleepy peaceful lazy blissful content", "p": ""},
 "kin":    {"w": "baby babies boy son kid kiddo child bby", "p": "my boy|good boy|sweet boy|orange boy|fur baby|furbaby|cat dad|cat mom"},
 "love":   {"w": "love loved loves adore ❤ ❤️ 🧡 😍 🥰 💕 💖", "p": ""},
 "grief":  {"w": "rip condolences passed loss grief grieving", "p": "rainbow bridge|sorry for your loss|run free|miss him|miss her"},
}
for f in FAM.values():
    f["set"] = set(f["w"].split()); f["re"] = re.compile(r"\b(?:" + f["p"] + r")\b") if f["p"] else None
TOK = re.compile(r"[a-z']+|[\U0001F300-\U0001FAFF☀-➿]")
def clean(s): return re.sub(r"https?://\S+|\[([^\]]*)\]\([^)]*\)|r/\w+|u/\w+", r"\1", s.lower())
def is_bot(a): a = (a or "").lower(); return a in BOTS or a.endswith("bot") or a.endswith("_bot")

rows = []
for fp in sorted(glob.glob(os.path.join(arc, "comments", "*.json"))):
    pid = os.path.basename(fp)[:-5]; op = posts[pid]["author"]
    cm = [c for c in json.load(open(fp, encoding="utf-8"))
          if c["body"] not in ("[deleted]", "[removed]") and not is_bot(c["author"])
          and not c.get("is_submitter") and c["author"] != op]
    words = 0; wwords = 0.0; cnt = collections.Counter(); wcnt = collections.Counter(); hit_c = collections.Counter()
    halves = [collections.Counter(), collections.Counter()]; hw = [0, 0]
    for i, c in enumerate(sorted(cm, key=lambda c: c["created_utc"])):
        t = clean(c["body"]); toks = TOK.findall(t); n = len(toks)
        if not n: continue
        wt = max(c["score"] or 0, 0) + 1
        words += n; wwords += n * wt; hw[i % 2] += n
        for k, f in FAM.items():
            m = sum(1 for x in toks if x in f["set"]) + (len(f["re"].findall(t)) if f["re"] else 0)
            if m:
                cnt[k] += m; wcnt[k] += m * wt; hit_c[k] += 1; halves[i % 2][k] += m
    r = {"post_id": pid, "n_comments": len(cm), "n_words": words}
    for k in FAM:
        r[f"cm_{k}_per1k"] = round(1000 * cnt[k] / words, 2) if words else ""
        r[f"cm_{k}_per1k_upvoted"] = round(1000 * wcnt[k] / wwords, 2) if wwords else ""
        r[f"cm_{k}_pct_comments"] = round(100 * hit_c[k] / len(cm), 1) if cm else ""
    fc = cnt["funny"] + cnt["cute"]; wfc = wcnt["funny"] + wcnt["cute"]
    r["cm_funny_vs_cute"] = round(cnt["funny"] / fc, 3) if fc else ""
    r["cm_funny_vs_cute_upvoted"] = round(wcnt["funny"] / wfc, 3) if wfc else ""
    ds = cnt["dumb"] + cnt["smart"]
    r["cm_dumb_vs_smart"] = round(cnt["dumb"] / ds, 3) if ds else ""
    for h in (0, 1):
        for k in FAM: r[f"_h{h}_{k}"] = 1000 * halves[h][k] / hw[h] if hw[h] else float("nan")
        r[f"_h{h}_fvc"] = halves[h]["funny"] / (halves[h]["funny"] + halves[h]["cute"]) if halves[h]["funny"] + halves[h]["cute"] else float("nan")
    rows.append(r)
cols = [k for k in rows[0] if not k.startswith("_")]
with open(os.path.join(here, "comment_lexicon_by_post.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows({k: r[k] for k in cols} for r in rows)
json.dump([{k: v for k, v in r.items() if k.startswith("_") or k == "post_id"} for r in rows],
          open(os.path.join(here, "_split_halves.json"), "w"))
print(len(rows), "posts;", sum(r["n_comments"] for r in rows), "comments;", sum(r["n_words"] for r in rows), "words")
