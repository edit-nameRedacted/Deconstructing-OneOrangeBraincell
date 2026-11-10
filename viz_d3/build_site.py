"""
build_site.py — copy what the page needs into site/, the folder Firebase Hosting uploads.

Run (from anywhere):   python viz_d3/build_site.py
Then deploy:           npx firebase-tools deploy      (from the Orange_Braincells folder)

site/ mirrors the Orange_Braincells layout, so the page's "../" paths work unchanged and the page
lives at /viz_d3/ (firebase.json redirects / there). Only local media the index still points to
(video posters, plus any post whose original link isn't a direct file) is copied; the rest of the
pictures load from Reddit and imgur. The animated sequences (viz_d3/sequences/, built by
build_sequences.py) are copied whole.
"""
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "site")

FILES = [
    "viz_d3/index.html", "viz_d3/style.css", "viz_d3/neuron_soma.svg",
    "viz_d3/media_index.json", "viz_d3/model_data.json",
    "oobc_archive/viz/oobc_viz_data.json",
    "oobc_archive/ai_opinion/reasoning_measures.csv",
    "SVG/cat_kit.svg", "SVG/white_stages.json", "SVG/tails/tail_geometry.json",
    "SVG/eye_parts.json",
]


def copy(rel):
    dst = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, rel), dst)


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "js"), os.path.join(OUT, "viz_d3", "js"))
    shutil.copytree(os.path.join(HERE, "sequences"), os.path.join(OUT, "viz_d3", "sequences"))
    for rel in FILES:
        copy(rel)
    with open(os.path.join(HERE, "media_index.json"), encoding="utf-8") as f:
        media = json.load(f)
    local = [p for e in media.values() for p in (e.get("src"), e.get("poster")) if p and not p.startswith("https://")]
    for rel in local:
        copy(rel)
    size = sum(os.path.getsize(os.path.join(d, n)) for d, _, ns in os.walk(OUT) for n in ns)
    print(f"wrote {OUT}: {len(FILES) + len(local)} files + js/ + sequences/, {size / 1e6:.1f} MB ({len(local)} local media files)")
