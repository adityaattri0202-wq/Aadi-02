"""Cost estimates and the human approval gate for paid stages.

No paid stage calls a provider unless ``gate()`` returns True, and it only
does that when the user passed ``--approve`` and it is not a dry run.
"""
from __future__ import annotations

from dataclasses import dataclass

from .context import ApprovalRequired
from .runlog import RunLog

# kind -> (key in costs.yaml, unit label, divisor applied to raw units)
_COST_KEYS = {
    "image": ("image", "image", 1),
    "video": ("video_per_second", "second", 1),
    "voice": ("voice_per_1k_chars", "1k chars", 1000),
}


@dataclass
class CostEstimate:
    provider: str
    kind: str
    units: float          # in unit_label units
    unit_label: str
    unit_cost: float | None
    currency: str

    @property
    def total(self) -> float | None:
        return None if self.unit_cost is None else round(self.units * self.unit_cost, 4)

    def describe(self) -> str:
        if self.total is None:
            return (f"{self.units:g} {self.unit_label}(s) x UNKNOWN price "
                    f"(fill config/costs.yaml) via {self.provider}")
        return (f"{self.units:g} {self.unit_label}(s) x {self.unit_cost:g} = "
                f"{self.total:.2f} {self.currency} via {self.provider}")


def estimate(costs: dict, provider: str, kind: str, raw_units: float) -> CostEstimate:
    key, label, divisor = _COST_KEYS[kind]
    table = (costs.get("providers") or {}).get(provider) or {}
    price = table.get(key)
    return CostEstimate(provider, kind, round(raw_units / divisor, 3), label,
                        None if price is None else float(price), str(costs.get("currency", "USD")))


def gate(log: RunLog, stage: str, item_ids: list[str], est: CostEstimate,
         approve: bool, dry_run: bool) -> bool:
    """Print the plan. Return True only if the stage may now spend credits."""
    log.info(f"Plan: {len(item_ids)} item(s) to generate; estimated cost: {est.describe()}")
    if item_ids:
        shown = ", ".join(item_ids[:15]) + (" ..." if len(item_ids) > 15 else "")
        log.info(f"Pending: {shown}")
    log.count("planned", len(item_ids))
    if not item_ids:
        log.info("Nothing to do: all outputs already exist.")
        return False
    if dry_run:
        log.info("[dry-run] No API calls made, no credits spent.")
        return False
    if not approve:
        log.status = "awaiting_approval"
        raise ApprovalRequired(
            f"{stage} would spend credits ({est.describe()}). "
            f"Review the plan, then re-run with --approve."
        )
    log.info("Approved with --approve; starting generation.")
    return True
