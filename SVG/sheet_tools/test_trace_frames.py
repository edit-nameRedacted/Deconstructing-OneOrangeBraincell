from trace_frames import eye_state, fill_gaps, isolated_flips, lid_ramp, place_shut


def test_place_shut_interpolates_long_runs_and_holds_open_ends():
    a, b = [eye(100, 100), eye(160, 100)], [eye(120, 110), eye(180, 110)]
    found = [a, [], [], [], [], b, [], []]
    known = {0: a, 5: b}
    p = place_shut(found, known)
    assert sorted(p) == [1, 2, 3, 4, 6, 7]
    assert p[1][0]["x"] == 104.0 and p[4][1]["y"] == 108.0          # interpolated between frames 1 and 6
    assert p[7][0]["x"] == 120 and p[6] == p[7]                      # after the last known frame: held


def test_lid_ramp_eases_into_and_out_of_drawn_shut_eyes():
    s = ["open"] * 3 + ["closed"] * 3 + ["open"] * 3
    assert lid_ramp(s) == [0, 0.33, 0.67, 1, 1, 1, 0.67, 0.33, 0]
    assert lid_ramp(s, ramp=1) == [0, 0, 0.5, 1, 1, 1, 0.5, 0, 0]
    assert lid_ramp(["closed", "closed", "open", "open", "open"]) == [1, 1, 0.67, 0.33, 0]   # run at the start
    assert lid_ramp(["open", "filled", "open"]) == [0, 0, 0]                                 # nothing shut: no lids


def eye(x, y, w=20, h=20):
    return {"x": x, "y": y, "w": w, "h": h, "pupil": [x, y]}


def test_fill_gaps_interpolates_short_gaps():
    found = [[eye(100, 100), eye(160, 100)], [], [eye(110, 120, 30), eye(170, 120, 30)]]
    fills = fill_gaps(found)
    assert list(fills) == [1]
    left, right = fills[1]
    assert (left["x"], left["y"], left["w"]) == (105.0, 110.0, 25)
    assert right["pupil"] == [165.0, 110.0]


def test_fill_gaps_replaces_sliver_sized_eyes():
    two = [eye(100, 100), eye(160, 100)]
    tiny = [eye(98, 102, 8, 8), eye(158, 102, 8, 8)]      # half-lidded: only a sliver of white was found
    fills = fill_gaps([two, two, tiny, two, two])
    assert list(fills) == [2] and fills[2][0]["w"] == 20
    one_tiny = [eye(98, 102, 8, 8), eye(160, 100)]
    assert list(fill_gaps([two, two, one_tiny, two, two])) == [2]


def test_fill_gaps_leaves_long_runs_and_open_ends():
    two = [eye(100, 100), eye(160, 100)]
    assert fill_gaps([[], two, [], [], [], two, []]) == {}       # 3 shut frames: a real blink; ends have one side only
    assert sorted(fill_gaps([two, [], [eye(1, 1)], two])) == [1, 2]   # one eye alone counts as missing


def test_eye_state():
    assert eye_state(2) == "open"
    assert eye_state(0) == "closed"
    assert eye_state(1) == "partial"


def test_isolated_flips():
    assert isolated_flips(["open", "closed", "open", "open"]) == [2]
    assert isolated_flips(["open", "open", "closed", "closed"]) == []
