import numpy as np
from PIL import Image
from join_keys import join


def blob(W, H, x0, x1, y0, y1):
    a = np.full((H, W, 3), 255, np.uint8)
    a[y0:y1, x0:x1] = (215, 142, 52)
    a[y0:y1, x0:x0 + 3] = a[y0:y1, x1 - 3:x1] = a[y1 - 3:y1, x0:x1] = (70, 46, 41)
    return Image.fromarray(a)


def test_join_lines_up_the_bases_and_scales():
    a = blob(200, 300, 40, 120, 50, 250)          # 200 tall, base middle at x 80, floor at 250
    b = blob(400, 400, 200, 300, 100, 300)         # 200 tall, base middle at x 250, floor at 300
    out = join([a, b], scales=[0.5, 1.0])
    assert out[0].size == out[1].size
    def base(im):
        m = np.asarray(im).min(2) < 200
        ys, xs = np.nonzero(m)
        return xs[ys >= ys.max() - 3].mean(), ys.max()
    (ax, ay), (bx, by) = base(out[0]), base(out[1])
    assert abs(ax - bx) <= 2 and abs(ay - by) <= 2
    hs = [np.nonzero((np.asarray(im).min(2) < 200).any(1))[0] for im in out]
    assert abs((hs[0][-1] - hs[0][0]) - 100) <= 3 and abs((hs[1][-1] - hs[1][0]) - 200) <= 3
