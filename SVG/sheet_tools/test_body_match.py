import numpy as np
from PIL import Image
from body_match import match_width, widths


def cat(body_w, head_w=60, H=200, W=200):
    """A stand-in cat: a head (rows 10-60) and a body (rows 70-190) as dark-outlined orange blocks on white."""
    a = np.full((H, W, 3), 255, np.uint8)
    for (y0, y1, w) in ((10, 60, head_w), (60, 70, 30), (70, 190, body_w)):
        x0 = W // 2 - w // 2
        a[y0:y1, x0:x0 + w] = (215, 142, 52)
        a[y0:y1, x0:x0 + 3] = a[y0:y1, x0 + w - 3:x0 + w] = (70, 46, 41)
    return Image.fromarray(a)


def test_body_is_narrowed_to_the_references_and_head_left_alone():
    out = match_width(cat(120), [cat(100), cat(100)], keep_top=0.3)
    w = widths(out)
    assert abs(w[130] - 100) <= 3          # body now as wide as the references
    assert abs(w[30] - 60) <= 1            # head untouched
    assert np.array_equal(np.asarray(out)[:40], np.asarray(cat(120))[:40])


def test_body_can_be_widened_about_ten_percent():
    out = match_width(cat(100), [cat(110)], keep_top=0.3)
    assert abs(widths(out)[130] - 110) <= 3


def test_matching_bodies_are_left_unchanged():
    img = cat(100)
    assert np.array_equal(np.asarray(match_width(img, [cat(100)])), np.asarray(img))
