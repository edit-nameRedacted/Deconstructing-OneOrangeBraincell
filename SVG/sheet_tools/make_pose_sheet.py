"""Put all five head-turn poses in one file, side by side, each on its own copy of the body, for corrections
in Illustrator.

Usage:  python3 make_pose_sheet.py POSES_DIR OUT.svg
  POSES_DIR  build_head_poses.py output (body_headless.svg, pose_N_head.svg, poses.json)

Each pose is a group Pose_N holding Body_N (for reference: leave it where it is), Bib_N, Fluff_N and Head_N
(with its cues layer). Move, scale, stretch or redraw the bib, fluff and head as you like, then save as SVG and
read it back with apply_pose_edits.py. Poses are 200 units apart; the labels under them are ignored.
"""
import argparse, os, re
from pose_io import group_text, strip_outer_id

GAP = 200


def numbered_ids(fragment, n):
    """Give every inner id a -N suffix, so the five copies don't share ids."""
    return re.sub(r'\bid="([^"]+)"', lambda m: f'id="{m.group(1)}-{n}"', fragment)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("poses")
    ap.add_argument("out")
    a = ap.parse_args()
    body_text = open(os.path.join(a.poses, "body_headless.svg"), encoding="utf-8").read()
    defs = re.search(r"<defs>.*?</defs>", body_text, re.S).group(0)
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', body_text).group(1).split()]
    body = strip_outer_id(group_text(body_text, "Body_headless"))
    cols, labels = [], []
    for n in range(1, 6):
        t = open(os.path.join(a.poses, f"pose_{n}_head.svg"), encoding="utf-8").read()
        parts = {p: numbered_ids(strip_outer_id(group_text(t, p)), n) for p in ("bib", "fluff", "head")}
        b = numbered_ids(body, n)
        cols.append(f'<g id="Pose_{n}" transform="translate({(n - 1) * GAP},0)">'
                    f'<g id="Body_{n}">{b}</g>'
                    f'<g id="Bib_{n}">{parts["bib"]}</g>'
                    f'<g id="Fluff_{n}">{parts["fluff"]}</g>'
                    f'<g id="Head_{n}">{parts["head"]}</g></g>')
        labels.append(f'<text x="{(n - 1) * GAP + vb[2] / 2 + vb[0]}" y="{vb[1] + vb[3] + 14}" '
                      f'text-anchor="middle" font-family="Arial" font-size="11" fill="#7A6A60">Pose {n}</text>')
    W = GAP * 4 + vb[2]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb[0]} {vb[1]} {W} {vb[3] + 22}">\n{defs}\n'
           + "\n".join(cols) + f'\n<g id="Labels">{"".join(labels)}</g>\n</svg>\n')
    open(a.out, "w", encoding="utf-8").write(svg)
    print(f"wrote {a.out} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
