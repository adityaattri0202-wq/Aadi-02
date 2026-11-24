"""Per-stage run log: ``topics/<slug>/logs/<stage>.log`` (appended each run)."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from .paths import TopicPaths


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunLog:
    """Timestamped log lines to file and console, plus counts and an end summary."""

    def __init__(self, paths: TopicPaths, stage: str, dry_run: bool = False, quiet: bool = False):
        self.stage = stage
        self.dry_run = dry_run
        self.quiet = quiet
        self.counts: dict[str, int] = {}
        self.errors: list[str] = []
        self.status = "ok"
        paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self.path = paths.logs_dir / f"{stage}.log"
        self._fh = None
        self._t0 = 0.0

    def __enter__(self) -> "RunLog":
        self._fh = open(self.path, "a", encoding="utf-8")
        self._t0 = time.monotonic()
        self._write("INFO", f"=== start stage={self.stage} dry_run={self.dry_run} ===", echo=False)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None and self.status == "ok":
            self.status = "error"
            self.error(f"{type(exc).__name__}: {exc}")
        took = time.monotonic() - self._t0
        self._write("INFO", f"=== end status={self.status} duration={took:.2f}s "
                            f"counts={self.counts} errors={len(self.errors)} ===", echo=False)
        self._fh.close()

    def _write(self, level: str, msg: str, echo: bool = True) -> None:
        line = f"{_now()} [{level}] {msg}"
        if self._fh:
            self._fh.write(line + "\n")
            self._fh.flush()
        if echo and not self.quiet:
            stream = sys.stderr if level == "ERROR" else sys.stdout
            print(f"[{self.stage}] {msg}" if level == "INFO" else f"[{self.stage}] {level}: {msg}", file=stream)

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def warning(self, msg: str) -> None:
        self._write("WARN", msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)
        self._write("ERROR", msg)

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n
