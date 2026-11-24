"""Unit tests for script_check: word count, runtime estimate, [VERIFY] detection."""
from pipeline.script_check import check_script, estimate_runtime, find_missing_imperial, find_verify_tags
from pipeline.script_format import count_words

SCRIPT = """# Title

## Hook
[SHOT: a whale | motion=slow_push_in]
One two three four five. [VERIFY: age]

## Outro
Six seven eight nine ten.
"""


def test_word_count_ignores_tags_and_markers():
    assert count_words("One two three [VERIFY: not counted] four.") == 4
    assert count_words("It's 17.5 metres long") == 4
    res = check_script(SCRIPT)
    assert res.word_count == 10


def test_runtime_estimate_130_to_150_wpm():
    assert estimate_runtime(1300) == (8.67, 10.0)
    assert estimate_runtime(150) == (1.0, 1.15)


def test_verify_tags_found_with_line_numbers():
    tags = find_verify_tags(SCRIPT)
    assert tags == [{"line": 5, "note": "age"}]
    assert find_verify_tags("plain [VERIFY] tag") == [{"line": 1, "note": ""}]


def test_verify_allowed_in_draft_but_fails_publish():
    assert check_script(SCRIPT).passed
    res = check_script(SCRIPT, publish=True)
    assert not res.passed
    assert any("[VERIFY]" in e for e in res.errors)


def test_unverified_facts_fail_publish():
    clean = SCRIPT.replace("[VERIFY: age]", "")
    facts = [{"claim": "x", "source": "y", "verified": False}]
    assert check_script(clean, facts=facts).passed
    assert not check_script(clean, facts=facts, publish=True).passed
    ok = [{"claim": "x", "source": "y", "verified": True}]
    assert check_script(clean, facts=ok, publish=True).passed


def test_missing_required_section_fails():
    res = check_script(SCRIPT, required_sections=["Hook", "Anatomy", "Outro"])
    assert res.missing_sections == ["Anatomy"]
    assert not res.passed


def test_scene_prefix_matches_required_section():
    md = "# T\n\n## Scene 1: Hook\nHello there.\n\n## Scene 2 - Outro\nBye now.\n"
    assert check_script(md).passed


def test_runtime_target_warning():
    res = check_script(SCRIPT, target_minutes=8)
    assert any("target" in w for w in res.warnings)


def test_metric_without_imperial_is_flagged():
    assert find_missing_imperial("It was 17 m long.")
    assert not find_missing_imperial("It was 17 m (56 ft) long.")
