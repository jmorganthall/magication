"""Environment-driven configuration for the Phase 0 poller."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _park_ids() -> list[int]:
    raw = os.getenv("QUEUE_TIMES_PARK_IDS", "").strip()
    if not raw:
        return []
    return [int(part) for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Config:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql://moat:moat@localhost:5432/moat"
        )
    )
    # Explicit Queue-Times park IDs; when empty the scheduler resolves a default
    # Orlando set by name against /parks.json.
    park_ids: list[int] = field(default_factory=_park_ids)
    poll_interval_seconds: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
    )
    http_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "4"))
    )


def load_config() -> Config:
    return Config()
