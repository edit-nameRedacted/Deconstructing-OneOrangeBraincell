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
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                   # Orange_Braincells
DATA = os.path.join(ROOT, "oobc_archive", "viz", "oobc_viz_data.json")
MEDIA = os.path.join(ROOT, "oobc_media")
OUT = os.path.join(HERE, "media_index.json")


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
    index = {}
    for post in posts:
        entry = entry_for(post["id"])
        if entry:
            index[post["id"]] = entry
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)
    kinds = [e["type"] for e in index.values()]
    print(f"wrote {OUT}: {len(index)} of {len(posts)} posts "
          f"({kinds.count('image')} photos, {kinds.count('video')} videos)")
