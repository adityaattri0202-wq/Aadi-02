"""Write ``sources.md``: every fact in topic.yaml with its source and status."""
from __future__ import annotations

from pathlib import Path


def render_sources(topic: dict) -> str:
    lines = [f"# Sources: {topic.get('name', '')}", "",
             "Generated from topic.yaml by script_check. Edit topic.yaml, not this file.", "",
             "| # | Fact | Source | Verified |", "|---|------|--------|----------|"]
    for i, fact in enumerate(topic.get("facts", []), 1):
        claim = str(fact["claim"]).replace("|", "\\|")
        source = str(fact.get("source") or "TODO: add source").replace("|", "\\|")
        lines.append(f"| {i} | {claim} | {source} | {'yes' if fact.get('verified') else 'NO'} |")
    unverified = sum(1 for f in topic.get("facts", []) if not f.get("verified"))
    lines += ["", f"Unverified facts: {unverified} of {len(topic.get('facts', []))}."]
    return "\n".join(lines) + "\n"


def write_sources(topic: dict, path: Path) -> None:
    path.write_text(render_sources(topic), encoding="utf-8")
