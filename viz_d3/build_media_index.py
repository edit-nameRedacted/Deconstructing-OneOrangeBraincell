"""
build_media_index.py — list each post's photo or video, for the page's example pictures.

Run (from anywhere):   python viz_d3/build_media_index.py
Writes:                viz_d3/media_index.json
Re-run it if the posts in the data file or the files in oobc_media change.

The scraper saved each post's media in oobc_media/<post id>/:
    photos  img1.jpg, img2.jpg, ...        (a gallery has several)
    videos  video.mp4, plus frame1.jpg ... frame4.jpg taken from it
For every post in the visualization's data file this writes one entry:
    {"type": "image", "src": "oobc_media/<id>/img1.jpg", "count": <images in the post>}
    {"type": "video", "src": "oobc_media/<id>/video.mp4", "poster": "oobc_media/<id>/frame1.jpg"}
Paths are relative to the Orange_Braincells folder. Posts with no media are left out, and the page
simply won't pick them as examples.

For the hosted site, "src" is the post's original link (media_url in the enriched CSV) whenever that
is a direct image or video file, so the 558 MB of media is not re-hosted. Video posters stay local
(a few KB each) and get copied by build_site.py, as does any post whose link is not a direct file.
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                   # Orange_Braincells
DATA = os.path.join(ROOT, "oobc_archive", "viz", "oobc_viz_data.json")
MEDIA = os.path.join(ROOT, "oobc_media")
OUT = os.path.join(HERE, "media_index.json")
CSV = os.path.join(ROOT, "oobc_heyday_2022-04_08_top40_enriched.csv")
DIRECT = (".jpg", ".jpeg", ".png", ".mp4")


def original_links():
    """post id -> its original media link, when that link is a direct file (first one of a gallery)."""
    if not os.path.exists(CSV):
        return {}
    with open(CSV, encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        links = {r["post_id"]: (r["media_url"].split() or [""])[0] for r in rows}
    return {k: v for k, v in links.items() if v.startswith("https://") and v.lower().endswith(DIRECT)}


def entry_for(post_id):
    folder = os.path.join(MEDIA, post_id)
    if not os.path.isdir(folder):
        return None
    files = sorted(os.listdir(folder))
    rel = lambda name: f"oobc_media/{post_id}/{name}"
    if "video.mp4" in files:
        frames = [f for f in files if f.startswith("frame") and f.endswith(".jpg")]
        return {"type": "video", "src": rel("video.mp4"), "poster": rel(frames[0]) if frames else None}
    images = [f for f in files if f.startswith("img") and f.endswith(".jpg")]
    if images:
        return {"type": "image", "src": rel(images[0]), "count": len(images)}
    return None


if __name__ == "__main__":
    with open(DATA, encoding="utf-8") as f:
        posts = json.load(f)["posts"]
    links = original_links()
    index = {}
    for post in posts:
        entry = entry_for(post["id"])
        if entry:
            link = links.get(post["id"])
            if link and link.lower().endswith(".mp4") == (entry["type"] == "video"):
                entry["src"] = link
            index[post["id"]] = entry
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)
    kinds = [e["type"] for e in index.values()]
    print(f"wrote {OUT}: {len(index)} of {len(posts)} posts "
          f"({kinds.count('image')} photos, {kinds.count('video')} videos), "
          f"{sum(e['src'].startswith('https://') for e in index.values())} linked to the original")
