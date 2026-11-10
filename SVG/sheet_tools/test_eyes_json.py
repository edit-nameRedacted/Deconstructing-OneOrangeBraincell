from eyes_json import flag_frames, smooth_track, track_sides


def pair(lx, rx, y=100):
    return [{"x": lx, "y": y}, {"x": rx, "y": y}]


def test_track_sides_keeps_each_eye_on_its_side():
    frames = [pair(100, 160), pair(104, 162), pair(108, 166)]
    sides, swaps, unsure = track_sides(frames)
    assert [[e["x"] for e in s] for s in sides] == [[100, 160], [104, 162], [108, 166]]
    assert swaps == [] and unsure == []


def test_track_sides_follows_an_eye_across_and_reports_the_crossing():
    # the left eye sits higher (y 90) than the right (y 110); on frame 3 it has moved past the right eye in x
    hi_lo = lambda lx, rx: [{"x": lx, "y": 90}, {"x": rx, "y": 110}]
    frames = [hi_lo(100, 160), hi_lo(126, 134), [{"x": 129, "y": 110}, {"x": 131, "y": 90}]]
    sides, swaps, unsure = track_sides(frames)
    assert (sides[2][0]["x"], sides[2][0]["y"]) == (131, 90)   # still the same (higher) eye, now right of the other
    assert swaps == [3]


def test_track_sides_reports_close_calls():
    frames = [pair(100, 160), pair(104, 156), pair(130, 131)]   # frame 3: both pairings about as close
    _, _, unsure = track_sides(frames)
    assert unsure == [3]


def test_smooth_track_removes_a_spike_and_pins_keyframes():
    raw = [10, 10, 30, 10, 10, 10]
    out = smooth_track(raw, pinned={1: 10, 6: 10})
    assert out[0] == 10 and out[5] == 10
    assert max(out) < 15                                    # the one-frame spike is gone


def test_flags():
    spacing = [60, 60, 80, 60, 60]
    angle = [0, 0, 0, 15, 0]
    f = flag_frames(spacing, angle, swaps=[2], single_frontal=[5])
    kinds = {(x["frame"], x["why"]) for x in f}
    assert (3, "spacing") in kinds and (4, "angle") in kinds
    assert (2, "swap") in kinds and (5, "one eye, head frontal") in kinds
    assert (1, "spacing") not in kinds
