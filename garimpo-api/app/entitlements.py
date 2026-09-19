"""Limites por plano (fonte única). Espelha `src/lib/entitlements.ts` do front."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entitlements:
    min_interval_minutes: float
    max_alerts: int
    max_destinations: int
    max_pages: int


_TABLE = {
    "FREE": Entitlements(1, 1, 1, 1),
    "PRO": Entitlements(0.25, 10, 3, 2),
    "ELITE": Entitlements(1 / 6, 30, 10, 3),
}


def entitlements_for(plan: str) -> Entitlements:
    return _TABLE.get(plan, _TABLE["FREE"])
