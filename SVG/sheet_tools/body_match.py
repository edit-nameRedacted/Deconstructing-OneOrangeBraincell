"""Narrow (or widen) one keyframe's body, row by row, to the width of other keyframes on the same canvas.

For a pose drawn broader than its neighbours (the head turn's front pose is 8-10% wider at the shoulders), so the
body doesn't swell every time the animation passes it. The head (the top `keep_top` of the drawing) is left as drawn;
below it the squeeze eases in, follows the references' width row by row (smoothed), and is limited to `limit`.
Used by flf_runner.py when a sequence file has "match_body": {"3": [2, 4]}.
"""
import cv2
import numpy as np
from PIL import Image

import sheet_frames as sf


def widths(img):
    """Width of the drawing's silhouette on every row (0 where empty)."""
    m = sf.silhouette(cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR))
    w = np.zeros(m.shape[0])
    for y in np.nonzero(m.any(1))[0]:
        xs = np.nonzero(m[y])[0]
        w[y] = xs[-1] - xs[0] + 1
    return w


def _centres(img):
    m = sf.silhouette(cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR))
    c = np.full(m.shape[0], m.shape[1] / 2)
    for y in np.nonzero(m.any(1))[0]:
        xs = np.nonzero(m[y])[0]
        c[y] = (xs[0] + xs[-1]) / 2
    return c


def match_width(img, refs, keep_top=0.3, ramp=0.1, limit=(0.85, 1.12)):
    if any(r.size != img.size for r in refs):
        raise ValueError("match_width: keyframes must share one canvas size")
    w = widths(img)
    rw = np.mean([widths(r) for r in refs], axis=0)
    rows = np.nonzero(w)[0]
    top, H = rows[0], rows[-1] - rows[0]
    ratio = np.ones_like(w)
    both = (w > 0) & (rw > 0)
    ratio[both] = np.clip(rw[both] / w[both], *limit)
    y = np.arange(len(w))
    ease = np.clip((y - top - keep_top * H) / (ramp * H), 0, 1)
    ratio = 1 + ease * (ratio - 1)
    sigma = max(1.0, 0.015 * H)
    k = np.exp(-0.5 * (np.arange(-3 * sigma, 3 * sigma + 1) / sigma) ** 2)
    k /= k.sum()
    ratio = 1 + np.convolve(np.pad(ratio - 1, len(k) // 2, mode="edge"), k, mode="valid")[:len(w)]
    if np.abs(ratio - 1).max() < 1e-3:
        return img
    c = np.convolve(np.pad(_centres(img), len(k) // 2, mode="edge"), k, mode="valid")[:len(w)]
    Hh, Ww = len(w), img.size[0]
    xs = np.arange(Ww, dtype=np.float32)[None, :].repeat(Hh, 0)
    map_x = (c[:, None] + (xs - c[:, None]) / ratio[:, None]).astype(np.float32)
    map_y = np.arange(Hh, dtype=np.float32)[:, None].repeat(Ww, 1)
    out = cv2.remap(np.asarray(img.convert("RGB")), map_x, map_y, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return Image.fromarray(out)
