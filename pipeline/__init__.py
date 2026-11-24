"""Faceless educational video pipeline.

Modular, file-based, resumable stages:

    script_check -> shot_plan -> image_generate -> motion_generate
    -> voiceover -> manifest -> review_report

Run one stage with ``python -m pipeline <stage> --topic <slug>``.
Paid stages (image_generate, motion_generate, voiceover) stop at an approval
gate unless ``--approve`` is given; every stage supports ``--dry-run``.
"""

STAGES = (
    "script_check",
    "shot_plan",
    "image_generate",
    "motion_generate",
    "voiceover",
    "manifest",
    "review_report",
)
PAID_STAGES = ("image_generate", "motion_generate", "voiceover")
__version__ = "0.1.0"
