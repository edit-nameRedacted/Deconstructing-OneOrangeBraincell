"""Collect the picked Qwen kneading edits (make_knead_qwen.sh -> out/knead_qwen/<edit>/seed_<n>.png) into
a keyframe dir for flf_runner. Faces are untouched, so every key takes its eye cue from paw_keys frame 1.
  1 both paws down (paw_keys frame 1)   2 left-hand foot lifted   3 left-hand foot pushing (claws)
  4 middle foot lifted                  5 middle foot pushing (claws)
usage: make_knead_keys.py [OUT=out/knead_loop_keys]   (change PICKS to swap a seed)
"""
import json, os, shutil, sys

SRC = "out/paw_keys"
PICKS = {2: ("lift_L", 2024), 3: ("push_L", 42), 4: ("lift_M", 2024), 5: ("push_M", 2024)}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "out/knead_loop_keys"
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(SRC, "cues.json"), encoding="utf-8") as f:
        cues = json.load(f)
    eye = next(e for e in cues["frames"] if e["frame"] == 1)
    files = {1: os.path.join(SRC, "frame_01.png")}
    files.update({k: f"out/knead_qwen/{edit}/seed_{seed}.png" for k, (edit, seed) in PICKS.items()})
    frames = []
    for k, path in sorted(files.items()):
        shutil.copyfile(path, os.path.join(out, f"frame_{k:02d}.png"))
        frames.append(dict(eye, frame=k, file=f"frame_{k:02d}.svg", source=path))
    with open(os.path.join(out, "cues.json"), "w", encoding="utf-8") as f:
        json.dump(dict(cues, frames=frames, built_by="make_knead_keys.py"), f, indent=1)
    print(f"{len(frames)} keyframes -> {out}")


if __name__ == "__main__":
    main()
