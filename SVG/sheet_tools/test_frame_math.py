from pathlib import Path

import pytest
from flf_runner import pick_by_motion


def test_pick_by_motion_spreads_a_burst():
    # Wan does the move in frames 5-11 of 17 and holds still around it: picks follow the movement, not the clock
    burst = [0] * 5 + [1] * 6 + [0] * 5
    assert pick_by_motion(burst, 7, ease=0) == [0, 6, 7, 8, 9, 10, 16]


def test_pick_by_motion_matches_clock_picks_for_steady_motion():
    assert pick_by_motion([1] * 16, 7, ease=0) == [0, 3, 5, 8, 11, 13, 16]
    assert pick_by_motion([0] * 16, 7) == [0, 3, 5, 8, 11, 13, 16]      # nothing moves: fall back to the clock


def test_pick_by_motion_never_repeats_a_frame():
    snap = [0] * 7 + [1] + [0] * 8                                       # everything happens between frames 7 and 8
    p = pick_by_motion(snap, 7)
    assert p[0] == 0 and p[-1] == 16 and len(p) == 7 and all(x < y for x, y in zip(p, p[1:]))


def test_pick_by_motion_eases_in_and_out():
    p = pick_by_motion([1] * 16, 7)                                       # default ease: smaller steps at the ends
    gaps = [y - x for x, y in zip(p, p[1:])]
    assert gaps[0] < gaps[3] and gaps[-1] < gaps[3]
from PIL import Image, ImageDraw

from flf_runner import (fit_geometry, from_wan, join_segments, load_keys,
                        mean_abs_diff, pick_frames, to_wan, wan_length)

ST = Path(__file__).parent


def test_length():
    assert wan_length(3) == (49, 3.0, False)
    assert wan_length(5)[:2] == (81, 5.0)
    assert wan_length(0.5)[:2] == (9, 0.5)
    assert wan_length(2.1)[:2] == (33, 2.0)
    assert wan_length(6) == (81, 5.0, True)
    assert wan_length(0.625)[0] == 13
    with pytest.raises(ValueError):
        wan_length(0)


def test_picks():
    assert pick_frames(49, 16) == list(range(49))
    assert len(pick_frames(81, 12)) == 61
    assert pick_frames(9, 12) == [0, 1, 3, 4, 5, 7, 8]
    assert pick_frames(9, 8) == [0, 2, 4, 6, 8]
    assert len(pick_frames(33, 8)) == 17
    with pytest.raises(ValueError, match="RIFE"):
        pick_frames(49, 24)
    with pytest.raises(ValueError):
        pick_frames(49, 0)
    assert pick_frames(13, 7)[-1] == 12


def test_join():
    assert join_segments([[1, 2, 3], [3, 4, 5]], False) == [1, 2, 3, 4, 5]
    assert join_segments([[1, 2, 3], [3, 4, 1]], True) == [1, 2, 3, 4]


def test_geometry():
    g = fit_geometry(419, 599)
    assert g.pw % 16 == 0 and g.ph % 16 == 0
    assert g.w * g.h <= 400_000
    assert g.pw >= g.w and g.ph >= g.h


def test_round_trip():
    img = Image.new("RGB", (419, 599), "white")
    ImageDraw.Draw(img).rectangle((100, 100, 149, 149), fill="black")
    g = fit_geometry(419, 599)
    back = from_wan(to_wan(img, g), g)
    assert back.size == (419, 599)
    assert mean_abs_diff(img, back) < 3


def test_rgba_transparent_is_white():
    g = fit_geometry(100, 100)
    out = to_wan(Image.new("RGBA", (100, 100), (0, 0, 0, 0)), g)
    assert out.getpixel((g.pw // 2, g.ph // 2)) == (255, 255, 255)


def test_load_keys_size_mismatch(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "second.png"
    Image.new("RGB", (10, 10)).save(a)
    Image.new("RGB", (12, 10)).save(b)
    with pytest.raises(ValueError, match="second.png"):
        load_keys([str(a), str(b)])


def test_load_keys_dir():
    imgs, eyes = load_keys(str(ST / "out" / "grooming_keys"))
    assert len(imgs) == 12 and len(eyes) == 12
    assert all(im.size == (360, 509) for im in imgs.values())


def test_patch_graph():
    from flf_runner import patch_graph
    g = {"1": {"_meta": {"title": "positive"}, "inputs": {"text": "a"}},
         "2": {"_meta": {"title": "other"}, "inputs": {}}}
    out = patch_graph(g, {"positive": {"text": "b"}})
    assert out["1"]["inputs"]["text"] == "b" and g["1"]["inputs"]["text"] == "a"
    with pytest.raises(KeyError, match="nope"):
        patch_graph(g, {"nope": {"x": 1}})


def test_check_prompt_response():
    from flf_runner import check_prompt_response
    assert check_prompt_response({"prompt_id": "x", "node_errors": {}}) == "x"
    with pytest.raises(RuntimeError, match="value not in list"):
        check_prompt_response({"error": {"message": "bad"},
                               "node_errors": {"5": {"errors": [{"message": "value not in list"}]}}})


def test_parse_mem():
    from flf_runner import parse_mem_mb
    assert parse_mem_mb("12.5GiB / 31.2GiB") == 12.5 * 1024
    assert parse_mem_mb("512MiB / 1GiB") == 512
    assert parse_mem_mb("") is None


def test_picks_playback_seconds():
    assert pick_frames(17, 12, seconds=0.5) == [0, 3, 5, 8, 11, 13, 16]
    assert pick_frames(17, 12, seconds=1.0) == pick_frames(17, 12)
    assert pick_frames(9, 12, seconds=0.5) == [0, 1, 3, 4, 5, 7, 8]
    with pytest.raises(ValueError, match="RIFE"):
        pick_frames(9, 16, seconds=1.0)
    with pytest.raises(ValueError):
        pick_frames(9, 1, seconds=0.2)


def test_check_prompt_response_missing_id():
    from flf_runner import check_prompt_response
    with pytest.raises(RuntimeError, match="weird"):
        check_prompt_response({"weird": 1})


def test_plan_steps():
    from flf_runner import plan_steps
    assert plan_steps([3, 2, 1, 2, 3], False) == [(3, 2, "new"), (2, 1, "new"), (1, 2, "reverse"), (2, 3, "reverse")]
    assert plan_steps([1, 2, 3], True)[-1] == (3, 1, "new")
    assert plan_steps([1, 2, 1], True) == [(1, 2, "new"), (2, 1, "reverse")]


def test_blink_warnings():
    from flf_runner import blink_warnings
    w = blink_warnings([(7, 8, "new")], {7: False, 8: True})
    assert len(w) == 1 and "7→8" in w[0] and "open→closed" in w[0]
    assert "closed→open" in blink_warnings([(8, 9, "new")], {8: True, 9: False})[0]
    assert blink_warnings([(7, 8, "new")], {7: False, 8: False}) == []
    assert blink_warnings([(7, 8, "new")], None) == []


def test_segment_key():
    from flf_runner import segment_key
    g = fit_geometry(360, 509)
    gr = {"a": 1}
    A, B = Image.new("RGB", (4, 4), "red"), Image.new("RGB", (4, 4), "blue")
    base = segment_key(1, 2, 1.0, "p", 42, g, gr, A, B)
    assert base == segment_key(1, 2, 1.0, "p", 42, g, {"a": 1}, A.copy(), B.copy())
    assert base != segment_key(1, 2, 1.0, "q", 42, g, gr, A, B)
    assert base != segment_key(1, 2, 1.5, "p", 42, g, gr, A, B)
    assert base != segment_key(1, 2, 1.0, "p", 43, g, gr, A, B)
    assert base != segment_key(1, 2, 1.0, "p", 42, g, {"a": 2}, A, B)
    edited = A.copy()
    edited.putpixel((0, 0), (0, 0, 0))
    assert base != segment_key(1, 2, 1.0, "p", 42, g, gr, edited, B)  # hand-edited keyframe
    assert base != segment_key(1, 2, 1.0, "p", 42, g, gr, A, edited)


def test_keyframe_frames():
    from flf_runner import keyframe_frames
    assert keyframe_frames([7, 7], [1, 2, 3], False, 3) == ([1, 7, 13], 13)
    assert keyframe_frames([7, 7], [1, 2, 3], False, 1) == ([1, 7, 13], 1)
    # loop: order [1,2,3,1]; last frame dropped by join, closing entry wraps to 1
    assert keyframe_frames([7, 7, 7], [1, 2, 3, 1], True, 3) == ([1, 7, 13, 1], 13)
    assert keyframe_frames([7, 7, 7], [1, 2, 3, 1], True, 1)[1] == 1


def test_validate_cfg():
    from flf_runner import validate_cfg
    ok = {"name": "n", "keys": "k", "fps": 12, "seconds": 0.5, "seed": 1, "default_prompt": "p", "order": [1, 2],
          "front": 2}
    validate_cfg(ok)
    for k in ("name", "keys", "fps", "seconds", "seed", "default_prompt", "order"):
        with pytest.raises(ValueError, match=k):
            validate_cfg({x: v for x, v in ok.items() if x != k})
    with pytest.raises(ValueError, match="front"):
        validate_cfg({**ok, "front": 9})


def test_keyframe_positions():
    from flf_runner import keyframe_positions
    assert keyframe_positions([7, 7]) == [1, 7, 13]
    assert keyframe_positions([]) == [1]
    assert keyframe_positions([7, 5]) == [1, 7, 11]


def test_seg_roundtrip(tmp_path):
    from flf_runner import read_seg, write_seg
    assert read_seg(str(tmp_path)) == {}
    write_seg(str(tmp_path), {"key": "k", "L": 17, "wall_seconds": 61.2})
    assert read_seg(str(tmp_path)) == {"key": "k", "L": 17, "wall_seconds": 61.2}
