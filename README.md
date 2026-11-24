# Faceless Video Pipeline

A modular, file-based, resumable pipeline for faceless, animated, educational
YouTube videos for a US/UK English audience. Each topic folder ends with a
script, shot list, image prompts, voiceover, images/clips, sources and a
timeline you can import into DaVinci Resolve or CapCut.

First topic: **Livyatan** (`topics/livyatan/`).

## Directory tree

```
config/
  style_spec.yaml     "Naturalist Plate" style + fixed prompt prefix
  audience.yaml       US/UK English, metric + imperial units, US/UK voices
  providers.yaml      which provider does image / video / voice
  costs.yaml          per-unit prices for estimates (fill in; null = unknown)
pipeline/
  __main__.py         CLI: python -m pipeline <stage> --topic <slug> ...
  script_check.py     1. validate script, word count, runtime, [VERIFY]
  shot_plan.py        2. script.md -> shots.json (style prefix enforced)
  image_generate.py   3. images/      (paid, approval-gated)
  motion_generate.py  4. clips/       (paid, hero shots only)
  voiceover.py        5. voiceover/   (paid, US or UK accent)
  manifest.py         6. manifest.json, timeline.csv/.edl, subtitles.srt
  review_report.py    7. review_report.md with counts and cost estimates
  render.py           8. free local ffmpeg render -> topics/<slug>/<slug>_final.mp4
  approval.py         cost estimates + human approval gate
  assets.py           fingerprints that make stages idempotent
  config.py paths.py runlog.py context.py script_format.py sources.py new_topic.py
  providers/
    base.py           abstract adapter: generate_image / generate_video / generate_voice
    mock.py           offline mock (tests)
    openart.py        STUB, TODO: fill from OpenArt API docs
    viewmax.py        STUB, TODO: fill from Viewmax API docs
    edge_tts_voice.py free voice provider (optional `pip install edge-tts`)
topics/livyatan/
  topic.yaml          name, target length, facts (all verified: false for now)
  script.md           original narration, scene by scene, with [VERIFY] tags
  shots.json  sources.md  manifest.json  timeline.csv  timeline.edl
  subtitles.srt  review_report.md  script_check.json
  images/ clips/ voiceover/ logs/   (generated, git-ignored)
tests/                unit + integration tests
run_all.sh            all stages in order, pausing at each paid stage
.env.example          API key names (copy to .env; never commit .env)
legacy/               the earlier Streamlit prototype
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -r requirements.txt
cp .env.example .env        # fill in keys, then:
set -a; source .env; set +a
```

Keys are read **only** from environment variables.

Before any real (paid) run you must fill in:

| What | Where |
|---|---|
| OpenArt API calls (endpoint, payload, polling, download) | `pipeline/providers/openart.py` (TODOs) |
| Viewmax API calls | `pipeline/providers/viewmax.py` (TODOs) |
| Viewmax US/UK voice ids | `config/audience.yaml` |
| Prices | `config/costs.yaml` |

The stubs raise `NotImplementedError` before any network call, so nothing is
sent to an unverified endpoint. To get real voiceover today without Viewmax,
set `voice: edge_tts` in `config/providers.yaml` and `pip install edge-tts`.

## Add a topic

```bash
python -m pipeline new_topic --topic megalodon --name "Megalodon"
```

Then edit `topics/megalodon/topic.yaml` (target length, facts with sources) and
write `script.md` fresh. Script format:

```markdown
# Title
## Hook                                   <- each "##" heading is a scene
[SHOT: what we see | motion=slow_push_in | overlay=36 cm (14 in) | dur=4]
Narration for this shot. Unchecked facts get a tag [VERIFY: note].
```

- `motion`: `none` (still image), `slow_push_in`, `slow_pan` or `parallax`.
  Any value other than `none` makes it a hero shot that gets a video clip.
- A scene with no `[SHOT]` lines gets one still shot per paragraph.
- Lines starting with `>` are notes and are not spoken.
- Write measurements as metric first with imperial in brackets: `17 m (56 ft)`.

## Run

```bash
# Plan everything, call no APIs, spend nothing:
./run_all.sh livyatan --dry-run

# One stage at a time:
python -m pipeline script_check   --topic livyatan
python -m pipeline shot_plan      --topic livyatan
python -m pipeline review_report  --topic livyatan        # see the costs first
python -m pipeline image_generate --topic livyatan --dry-run
python -m pipeline image_generate --topic livyatan --approve
python -m pipeline motion_generate --topic livyatan --approve
python -m pipeline voiceover      --topic livyatan --approve --accent uk
python -m pipeline manifest       --topic livyatan
python -m pipeline render         --topic livyatan        # final MP4 (local, free)

# Full run that asks before each paid stage:
./run_all.sh livyatan
```

Options: `--dry-run`, `--approve`, `--publish` (script_check fails on any
`[VERIFY]` or unverified fact), `--force` (rebuild), `--provider mock`,
`--accent us|uk`, `--style path.yaml`.

**Approval gate.** `image_generate`, `motion_generate` and `voiceover` print
the item count and estimated cost, then stop with exit code 2 unless
`--approve` is given. Unknown prices show as UNKNOWN and still need approval.

**Resumable.** Each asset has a sidecar `.json` with a fingerprint of its
inputs. Re-running skips finished assets; changing one prompt regenerates
only that shot; failed items are retried on the next run.

**Dry run.** It never calls a provider. Free local stages (script_check,
shot_plan, manifest, review_report) still write their files. In a dry run the
manifest links assets by their planned paths with `"status": "planned"`.

**Logs.** `topics/<slug>/logs/<stage>.log`, with timestamps, counts, errors
and the final status of each run.

Exit codes: 0 ok, 1 config/provider error, 2 needs approval, 3 stage failed.

## Editing

- **DaVinci Resolve:** File > Import > Timeline > `timeline.edl`, with
  `images/`, `clips/` and `voiceover/` in the media pool. Also import
  `subtitles.srt`.
- **CapCut:** import the media folders and `subtitles.srt`, and use
  `timeline.csv` (start/end per shot) as the cut list.

## Publishing checklist

1. Check every fact in `topic.yaml` against its source; set `verified: true`.
2. Remove each `[VERIFY]` tag from `script.md` once the claim is confirmed.
3. `python -m pipeline script_check --topic <slug> --publish` must pass.

Scripts are written fresh for each topic. The pipeline contains no third-party
channel text. Check each provider's terms for commercial use.

## Tests

```bash
python -m pytest -q
```
