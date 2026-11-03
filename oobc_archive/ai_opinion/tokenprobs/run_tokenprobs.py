"""Stage 1 (exploration, no hand codes): next-token probabilities from qwen3.5:9b for each post.
The assistant's reply is pre-written up to an opening ("This cat is so" / "What a"); we keep the
top-20 candidates for the next token. Reasoning off, temperature 0. Resumable (skips done pairs)."""
import base64, csv, glob, json, os, time, urllib.request
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.abspath(os.path.join(here, "..", "..", ".."))
OUT = os.path.join(here, "tokenprobs_raw.jsonl")
OPENINGS = ["This cat is so", "What a"]
USER = "Here is a photo."
ids = [r["post_id"] for r in csv.DictReader(open(os.path.join(root, "Orange Braincell Data - InProgress.csv"), encoding="utf-8-sig"))]
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        d = json.loads(l); done.add((d["post_id"], d["opening"]))
t0 = time.time(); n = 0
with open(OUT, "a", encoding="utf-8") as out:
    for pid in ids:
        files = sorted(glob.glob(os.path.join(root, "oobc_media", pid, "*.jpg")))[:4]
        if not files: continue
        ims = [base64.b64encode(open(f, "rb").read()).decode() for f in files]
        for op in OPENINGS:
            if (pid, op) in done: continue
            body = {"model": "qwen3.5:9b", "stream": False, "think": False, "logprobs": True, "top_logprobs": 20,
                    "keep_alive": "10m", "options": {"num_predict": 1, "temperature": 0, "seed": 1, "num_ctx": 8192},
                    "messages": [{"role": "user", "content": USER, "images": ims},
                                 {"role": "assistant", "content": op}]}
            req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=600))
            top = [{"token": t["token"], "logprob": t["logprob"]} for t in r["logprobs"][0]["top_logprobs"]]
            out.write(json.dumps({"post_id": pid, "opening": op, "n_images": len(files), "top": top}) + "\n"); out.flush()
            n += 1
        if n and n % 20 == 0: print(f"{n} calls, {time.time()-t0:.0f}s", flush=True)
print(f"done: {n} new calls in {time.time()-t0:.0f}s", flush=True)
