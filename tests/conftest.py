"""Shared fixtures: a throwaway project copy so tests never touch the real topic."""
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.config import load_settings  # noqa: E402
from pipeline.providers.mock import MockProvider  # noqa: E402


@pytest.fixture
def project(tmp_path):
    shutil.copytree(REPO / "config", tmp_path / "config")
    src = REPO / "topics" / "livyatan"
    dst = tmp_path / "topics" / "livyatan"
    dst.mkdir(parents=True)
    for name in ("topic.yaml", "script.md"):
        shutil.copy(src / name, dst / name)
    MockProvider.calls.clear()
    return tmp_path


@pytest.fixture
def style():
    return load_settings(REPO).style
