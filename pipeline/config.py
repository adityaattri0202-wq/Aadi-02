"""Load and validate the YAML config in ``config/`` and ``topics/<slug>/topic.yaml``."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

MOTIONS = ("none", "slow_push_in", "slow_pan", "parallax")


class ConfigError(RuntimeError):
    """Raised for missing or invalid configuration."""


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"Missing file: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping")
    return data


def _one_line(text) -> str:
    return " ".join(str(text or "").split())


@dataclass
class StyleSpec:
    """Visual style. ``prompt_prefix`` starts every image prompt."""

    name: str
    prompt_prefix: str
    prompt_suffix: str
    negative_prompt: str
    width: int
    height: int
    clip_seconds: float
    motion_prompts: dict
    words_per_minute: float
    min_shot_sec: float
    pad_sec: float
    fps: int

    @classmethod
    def from_dict(cls, d: dict, source: str = "style spec") -> "StyleSpec":
        prefix = _one_line(d.get("prompt_prefix"))
        if not prefix:
            raise ConfigError(f"{source}: prompt_prefix is required")
        image, motion, timing = d.get("image", {}), d.get("motion", {}), d.get("timing", {})
        return cls(
            name=str(d.get("name", "unnamed")),
            prompt_prefix=prefix,
            prompt_suffix=_one_line(d.get("prompt_suffix")),
            negative_prompt=_one_line(d.get("negative_prompt")),
            width=int(image.get("width", 1920)),
            height=int(image.get("height", 1080)),
            clip_seconds=float(motion.get("clip_seconds", 5)),
            motion_prompts={k: _one_line(v) for k, v in (motion.get("prompts") or {}).items()},
            words_per_minute=float(timing.get("words_per_minute", 140)),
            min_shot_sec=float(timing.get("min_shot_sec", 3.0)),
            pad_sec=float(timing.get("pad_sec", 0.35)),
            fps=int(timing.get("fps", 30)),
        )


@dataclass
class Settings:
    """Everything a stage needs from ``config/``."""

    root: Path
    style: StyleSpec
    style_path: Path
    audience: dict
    providers: dict
    costs: dict

    def provider_for(self, kind: str, override: str | None = None) -> str:
        """Provider name for kind 'image' | 'video' | 'voice'."""
        name = override or self.providers.get(kind)
        if not name:
            raise ConfigError(f"config/providers.yaml: no provider set for '{kind}'")
        return str(name)

    def voice_for(self, provider: str, accent: str | None = None) -> str:
        voices = self.audience.get("voices", {})
        accent = accent or voices.get("default_accent", "us")
        table = voices.get(accent)
        if not isinstance(table, dict):
            raise ConfigError(f"config/audience.yaml: no voices for accent '{accent}' (use us or uk)")
        voice = table.get(provider)
        if not voice:
            raise ConfigError(f"config/audience.yaml: no '{accent}' voice set for provider '{provider}'")
        return str(voice)


def load_settings(root: Path, style_path: Path | None = None) -> Settings:
    cfg = root / "config"
    style_path = Path(style_path) if style_path else cfg / "style_spec.yaml"
    return Settings(
        root=root,
        style=StyleSpec.from_dict(load_yaml(style_path), str(style_path)),
        style_path=style_path,
        audience=load_yaml(cfg / "audience.yaml"),
        providers=load_yaml(cfg / "providers.yaml"),
        costs=load_yaml(cfg / "costs.yaml"),
    )


def load_topic(path: Path) -> dict:
    topic = load_yaml(path)
    for key in ("name", "target_minutes"):
        if key not in topic:
            raise ConfigError(f"{path}: '{key}' is required")
    facts = topic.get("facts") or []
    for i, fact in enumerate(facts, 1):
        if not isinstance(fact, dict) or not fact.get("claim"):
            raise ConfigError(f"{path}: fact #{i} needs a 'claim'")
        fact.setdefault("verified", False)
        fact.setdefault("source", "")
    topic["facts"] = facts
    return topic
