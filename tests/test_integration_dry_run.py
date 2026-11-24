"""Integration: full pipeline with the mock provider.

1. Dry run of every stage: no provider calls, no generated files, and a valid
   manifest.json linking every shot (to planned paths).
2. Approval gate: a paid stage without --approve exits 2 and spends nothing.
3. Approved mock run produces assets; a re-run is idempotent.
"""
import json

from pipeline import STAGES
from pipeline.__main__ import main
from pipeline.config import load_settings
from pipeline.context import Context
from pipeline.manifest import validate_manifest
from pipeline.paths import TopicPaths
from pipeline.providers.mock import MockProvider


def run(root, stage, *extra):
    return main([stage, "--topic", "livyatan", "--root", str(root), "--provider", "mock", *extra])


def test_full_dry_run_produces_valid_manifest(project):
    for stage in STAGES:
        assert run(project, stage, "--dry-run") == 0, stage

    assert MockProvider.calls == []
    p = TopicPaths(project, "livyatan")
    for folder in (p.images_dir, p.clips_dir, p.voiceover_dir):
        assert not folder.exists() or not any(folder.iterdir())

    shots = json.loads(p.shots_json.read_text())
    manifest = json.loads(p.manifest_json.read_text())
    assert validate_manifest(manifest, shots) == []
    assert manifest["dry_run"] is True
    assert [e["shot_id"] for e in manifest["shots"]] == [s["id"] for s in shots]
    for entry, shot in zip(manifest["shots"], shots):
        assert entry["image"]["path"].startswith("images/")
        assert (entry["clip"] is not None) == shot["hero"]
        assert entry["audio"]["path"].startswith("voiceover/")
    assert p.timeline_csv.exists() and p.timeline_edl.exists() and p.subtitles_srt.exists()
    assert p.report_md.exists() and p.sources_md.exists()
    for stage in STAGES:
        assert (p.logs_dir / f"{stage}.log").exists()


def test_paid_stage_requires_approval(project):
    assert run(project, "script_check") == 0
    assert run(project, "shot_plan") == 0
    for stage in ("image_generate", "motion_generate", "voiceover"):
        assert run(project, stage) == 2, stage
    assert MockProvider.calls == []
    assert "awaiting_approval" in (project / "topics/livyatan/logs/image_generate.log").read_text()


def test_approved_mock_run_is_idempotent(project):
    for stage in ("script_check", "shot_plan"):
        assert run(project, stage) == 0
    for stage in ("image_generate", "motion_generate", "voiceover"):
        assert run(project, stage, "--approve") == 0, stage
    first = len(MockProvider.calls)
    assert first > 0
    assert run(project, "manifest") == 0

    p = TopicPaths(project, "livyatan")
    manifest = json.loads(p.manifest_json.read_text())
    assert manifest["ready_for_edit"] is True
    assert all(e["audio"]["duration_sec"] for e in manifest["shots"])

    for stage in ("image_generate", "motion_generate", "voiceover"):
        assert run(project, stage, "--approve") == 0
    assert len(MockProvider.calls) == first  # nothing regenerated


def test_edited_prompt_regenerates_only_that_shot(project):
    for stage in ("script_check", "shot_plan"):
        run(project, stage)
    run(project, "image_generate", "--approve")
    p = TopicPaths(project, "livyatan")
    shots = json.loads(p.shots_json.read_text())
    shots[0]["image_prompt"] += " Extra detail."
    p.shots_json.write_text(json.dumps(shots))
    settings = load_settings(project)
    from pipeline import image_generate
    from pipeline.runlog import RunLog
    with RunLog(p, "probe", quiet=True) as log:
        ctx = Context(settings=settings, paths=p, log=log, provider_override="mock")
        assert [s["id"] for s in image_generate.pending(ctx, shots)] == [shots[0]["id"]]
