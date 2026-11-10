import os
import cv2
import sheet_frames as sf

KEYS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "grooming_keys")


def eyes_of(name):
    img = cv2.imread(os.path.join(KEYS, name))
    return sf.eyes_and_nose(img, sf.silhouette(img))[0]


def test_whisker_pocket_on_the_outline_is_not_an_eye():
    # keyframe 3, head turned: a pocket of paper closed off by whiskers at the cheek outline (around x 111, y 217)
    # used to outrank the real left eye; both real eyes sit high on the face
    eyes = eyes_of("frame_03.png")
    assert len(eyes) == 2
    assert all(e["y"] < 170 for e in eyes)
    assert [round(e["x"] / 10) for e in eyes] == [12, 18]


def test_split_and_half_lidded_eyes_are_found():
    raw = os.path.join(os.path.dirname(KEYS), "grooming_wan", "raw")       # cached Wan frames: stable across retiming
    for f, xs in (("seg_9-10/gen_005.png", [180, 238]),    # a pupil splits the right white
                  ("seg_10-11/gen_011.png", [165, 233])):  # almond, half-lidded
        img = cv2.imread(os.path.join(raw, f))
        eyes = sf.eyes_and_nose(img, sf.silhouette(img))[0]
        assert len(eyes) == 2 and all(abs(e["x"] - x) <= 8 for e, x in zip(eyes, xs)), (f, eyes)


def test_frontal_keyframe_unchanged():
    eyes = eyes_of("frame_01.png")
    assert [(e["x"], e["y"]) for e in eyes] == [(150.0, 136.5), (210.5, 140.0)]


def test_label_just_below_the_feet_is_not_part_of_the_frame():
    import numpy as np
    img = np.full((600, 600, 3), 255, np.uint8)
    img[100:400, 200:400] = (52, 142, 215)                     # the drawing (BGR orange) ...
    img[100:400, 200:204] = img[396:400, 200:400] = (41, 46, 70)  # ... with a dark outline
    img[415:445, 290:305] = (41, 46, 70)                        # a label 15 px under its feet
    frames, comp, ink = sf.find_frames(img, 0.5)
    (x, y, w, h, i), = frames
    assert y + h <= 410 and not (comp[430, 297] == i)            # the joining margin (~4 px) stays, the label goes


def test_small_sheet_cats_close_together_stay_apart():
    # the original 1024 px head-turn sheet: five cats, two of them only ~15 px apart
    img = cv2.imread(os.path.join(os.path.dirname(KEYS), "..", "sheets", "head_turn_sheet_1024.webp"))
    frames, _, _ = sf.find_frames(img, 0.5)
    assert len(frames) == 5
