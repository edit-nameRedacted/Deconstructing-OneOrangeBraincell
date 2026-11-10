"""Build the pose editor page (one self-contained HTML file) from the current poses.

Usage:  python3 make_pose_editor.py POSES_DIR OUT.html
The page shows each pose on the body; its saved edits are matrices that apply_pose_edits.py --edits reads.
"""
import json, os, re, sys
from pose_io import group_text, strip_outer_id

poses_dir, out = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
body_text = open(os.path.join(poses_dir, "body_headless.svg"), encoding="utf-8").read()
rec = json.load(open(os.path.join(poses_dir, "poses.json")))["poses"]
data = {
    "defs": re.search(r"<defs>(.*?)</defs>", body_text, re.S).group(1),
    "body": strip_outer_id(group_text(body_text, "Body_headless")),
    "poses": {}, "derived": {n: rec[str(n)]["derived"] for n in range(1, 6)},
}
for n in range(1, 6):
    t = open(os.path.join(poses_dir, f"pose_{n}_head.svg"), encoding="utf-8").read()
    data["poses"][n] = {p: strip_outer_id(group_text(t, p)) for p in ("bib", "fluff", "head")}
    data.setdefault("order", {})[n] = sorted(("bib", "fluff", "head"), key=lambda p: t.find(f'<g id="{p}"'))
page = open(os.path.join(here, "editor_template.html"), encoding="utf-8").read()
page = page.replace("/*DATA*/", "const DATA = " + json.dumps(data, separators=(",", ":")).replace("</", "<\\/") + ";")
open(out, "w", encoding="utf-8").write(page)
print(f"wrote {out} ({len(page) // 1024} KB)")
