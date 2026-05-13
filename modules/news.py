"""News module — RSS default, NewsAPI when key available."""

from __future__ import annotations

import os
from typing import Any

from providers.news import DEFAULT_RSS_FEEDS, NewsAPIProvider, RSSProvider


def _provider_name() -> str:
    return (os.environ.get("CELEBI_NEWS_PROVIDER") or "rss").strip().lower()


def _is_turkish_query(query: str) -> bool:
    q = (query or "").lower()
    if not q:
        return False
    turkish_hints = ("istanbul", "ankara", "izmir", "antalya", "fethiye", "türk", "turk")
    if any(hint in q for hint in turkish_hints):
        return True
    return any(ch in q for ch in "çğıöşüÇĞİÖŞÜ")


def fetch(query: str | None = None, *, limit: int = 15) -> list[dict[str, Any]]:
    name = _provider_name()
    if name == "newsapi":
        provider = NewsAPIProvider()
        if provider.is_available() and query:
            try:
                return provider.search(query, limit=limit)
            except Exception:  # noqa: BLE001 — fall back to RSS on any error
                pass
    feeds_key = "tr" if _is_turkish_query(query or "") else "global"
    feeds = DEFAULT_RSS_FEEDS.get(feeds_key) or DEFAULT_RSS_FEEDS["global"]
    items = RSSProvider().fetch(feeds, limit=limit * 2)
    if query:
        q_low = query.lower()
        filtered = [it for it in items if q_low in (it.get("title") or "").lower()
                    or q_low in (it.get("summary") or "").lower()]
        if filtered:
            return filtered[:limit]
    return items[:limit]
