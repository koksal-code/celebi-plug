"""Base provider — minimal abstract pattern, no framework."""

from __future__ import annotations

from typing import Any

from legal_guard import ensure_source


class BaseProvider:
    """Lightweight provider base. Subclasses set ``category`` and ``source_id``."""

    category: str = ""
    source_id: str = ""

    def __init__(self) -> None:
        if not self.category or not self.source_id:
            raise RuntimeError(
                f"{type(self).__name__} missing category/source_id"
            )
        # legal_guard raises if the source is not whitelisted
        self.policy = ensure_source(self.category, self.source_id)

    # subclasses override these as needed
    def is_available(self) -> bool:
        return True

    def describe(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "source": self.source_id,
            "license": self.policy.license,
            "public": self.policy.public,
        }
