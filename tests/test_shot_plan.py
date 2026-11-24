"""Unit tests for shot_plan: the style prefix is always present."""
import pytest

from pipeline.context import StageFailed
from pipeline.shot_plan import apply_style, build_shots, validate_shots
from tests.conftest import REPO


def test_every_image_prompt_starts_with_prefix(style):
    md = (REPO / "topics" / "livyatan" / "script.md").read_text(encoding="utf-8")
    shots = build_shots(md, style)
    assert len(shots) > 5
    for shot in shots:
        assert shot["image_prompt"].startswith(style.prompt_prefix), shot["id"]
    assert validate_shots(shots, style) == []


def test_prefix_applied_to_implicit_shots(style):
    md = "# T\n\n## Hook\nFirst paragraph here.\n\nSecond paragraph here.\n\n## Outro\nBye.\n"
    shots = build_shots(md, style)
    assert [s["id"] for s in shots] == ["s01_01", "s01_02", "s02_01"]
    assert all(s["image_prompt"].startswith(style.prompt_prefix) for s in shots)
    assert all(s["motion"] == "none" and not s["hero"] for s in shots)


def test_prefix_not_duplicated_and_never_dropped(style):
    once = apply_style(style, "a whale")
    assert apply_style(style, once) .count(style.prompt_prefix) == 1
    assert apply_style(style, "").startswith(style.prompt_prefix)


def test_validate_rejects_prompt_without_prefix(style):
    bad = [{"id": "s01_01", "image_prompt": "a whale", "motion": "none", "duration_sec": 3}]
    assert any("style prefix" in e for e in validate_shots(bad, style))


def test_shot_options_parsed(style):
    md = ("# T\n\n## Hook\n[SHOT: a tooth | motion=parallax | overlay=36 cm (14 in) | dur=4]\nText.\n\n"
          "## Outro\nBye.\n")
    shot = build_shots(md, style)[0]
    assert shot["motion"] == "parallax" and shot["hero"]
    assert shot["overlay_text"] == "36 cm (14 in)"
    assert shot["duration_sec"] == 4.0


def test_bad_motion_is_an_error(style):
    md = "# T\n\n## Hook\n[SHOT: x | motion=zoom]\nText.\n"
    with pytest.raises(StageFailed):
        build_shots(md, style)


def test_verify_tags_not_spoken(style):
    md = "# T\n\n## Hook\nIt lived long ago [VERIFY: age].\n"
    shot = build_shots(md, style)[0]
    assert "VERIFY" not in shot["narration"] and shot["needs_verify"]
