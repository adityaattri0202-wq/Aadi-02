"""Shared run context and stage exceptions."""
from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .paths import TopicPaths
from .runlog import RunLog


class StageFailed(RuntimeError):
    """A stage ran but its output is invalid or incomplete (exit code 3)."""


class ApprovalRequired(RuntimeError):
    """A paid stage needs --approve before it spends credits (exit code 2)."""


@dataclass
class Context:
    settings: Settings
    paths: TopicPaths
    log: RunLog
    dry_run: bool = False
    approve: bool = False
    publish: bool = False
    force: bool = False
    provider_override: str | None = None
    accent: str | None = None
