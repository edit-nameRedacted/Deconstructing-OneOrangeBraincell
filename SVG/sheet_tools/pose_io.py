"""Shared helpers for the head-turn pose files: reading pieces out of them and measuring them.

A pose has four parts: the body (fixed), the bib (cream chest patch), the fluff (chest fur lines) and the head
(with its "cues" layer marking eyes and nose). These helpers find each part by its group id, in the files
build_head_poses.py writes (ids body_headless / bib / fluff / head) and in the one-file sheet make_pose_sheet.py
writes and Illustrator saves back (ids Pose_N / Body_N / Bib_N / Fluff_N / Head_N, plus Illustrator's numbered
copies such as head_ear3 or coat-2).
"""
import io, re
from svgelements import SVG, Group, Shape, Path

from build_head_poses import group_text, inline_styles, css_classes, fit_similarity, box_stretch  # noqa: F401

PARTS = ("body", "bib", "fluff", "head")


def base_name(gid):
    """'Head_3' -> 'head', 'head_ear12' -> 'head_ear', 'coat-2' -> 'coat', 'Body_headless' -> 'body_headless'."""
    return re.sub(r"[-_]?\d+$", "", gid or "").lower()


def part_of(gid):
    b = base_name(gid)
    if b in ("body", "body_headless"):
        return "body"
    return b if b in ("bib", "fluff", "head") else None


def measure(path, default_pose=None):
    """{pose: {"ids": {part: group id}, "body_coat"|"bib"|"fluff"|"head"|"head_ear"|"head_nose": bbox}}.
    Transforms are applied, hidden layers count, and the body's coat is measured whole (its clip ignored), so
    the same file measures the same however Illustrator rewrote it."""
    out = {}

    def add(pose, key, bb):
        rec = out.setdefault(pose, {"ids": {}})
        b = rec.setdefault(key, [1e9, 1e9, -1e9, -1e9])
        b[:] = [min(b[0], bb[0]), min(b[1], bb[1]), max(b[2], bb[2]), max(b[3], bb[3])]

    def walk(g, pose, part, role):
        for el in g:
            if isinstance(el, Group):
                gid = el.values.get("id") or ""
                p, pa, r = pose, part, role
                m = re.match(r"Pose_(\d)", gid)
                if m:
                    p = int(m.group(1))
                elif part_of(gid) and part is None:
                    pa = part_of(gid)
                    if p is not None:
                        out.setdefault(p, {"ids": {}})["ids"].setdefault(pa, gid)
                elif part == "head" and base_name(gid).startswith("head_"):
                    r = base_name(gid)[5:]
                walk(el, p, pa, r)
            elif isinstance(el, Shape):
                if pose is None or part is None:
                    continue
                gid = base_name(el.values.get("id"))
                bb = Path(el).bbox()
                if not bb:
                    continue
                if part == "body":
                    if gid == "coat":
                        add(pose, "body_coat", bb)
                elif part == "head":
                    if role != "cues":
                        add(pose, "head", bb)
                    if role in ("ear", "nose"):
                        add(pose, f"head_{role}", bb)
                else:
                    add(pose, part, bb)

    text = open(path, encoding="utf-8").read()
    text = re.sub(r"display:\s*none;?", "", text).replace(' style="display:none"', "")
    doc = SVG.parse(io.StringIO(text), reify=True)
    walk(doc, default_pose, None, None)
    return out


def strip_outer_id(fragment):
    """'<g id="Head_3" ...>' -> '<g ...>' (the first tag only)."""
    return re.sub(r'^<g([^>]*?)\s+id="[^"]*"', r"<g\1", fragment, count=1)


def ancestor_transforms(text, gid):
    """The transform attributes of the groups enclosing <g id="gid">, outermost first, joined (or "")."""
    m = re.search(rf'<g[^>]*\bid="{re.escape(gid)}"', text)
    stack = []
    for t in re.finditer(r"<(/?)g\b([^>]*?)(/?)>", text[:m.start()]):
        if t.group(1):
            stack.pop()
        elif not t.group(3):
            tr = re.search(r'\btransform="([^"]*)"', t.group(2))
            stack.append(tr.group(1) if tr else "")
    return " ".join(s for s in stack if s)
