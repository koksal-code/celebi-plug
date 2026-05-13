"""News providers — RSS (default, token-free) + NewsAPI."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from utils.http import HttpError, get_json, get_text

from .base import BaseProvider


# Curated public RSS shortcuts. Keys are coarse region tags; the module
# layer picks the closest match for a given query.
DEFAULT_RSS_FEEDS: dict[str, list[str]] = {
    "tr": [
        "https://www.trthaber.com/sondakika.rss",
        "https://www.hurriyet.com.tr/rss/anasayfa",
        "https://www.ntv.com.tr/son-dakika.rss",
    ],
    "global": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.reuters.com/Reuters/worldNews",
    ],
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return value


class RSSProvider(BaseProvider):
    category = "news"
    source_id = "rss"

    def fetch(self, feeds: list[str], *, limit: int = 20) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for url in feeds:
            try:
                body = get_text(url, timeout=6.0)
            except HttpError:
                continue
            items.extend(self._parse(body, source_url=url))
            if len(items) >= limit:
                break
        items.sort(key=lambda it: it.get("published") or "", reverse=True)
        return items[:limit]

    def _parse(self, body: str, *, source_url: str) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []
        out: list[dict[str, Any]] = []
        # RSS 2.0
        for item in root.findall(".//item"):
            title = _strip_html(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            description = _strip_html(item.findtext("description") or "")
            pub = _parse_date(item.findtext("pubDate"))
            if not title or not link:
                continue
            out.append({
                "title": title,
                "summary": description[:280],
                "url": link,
                "published": pub,
                "source": source_url,
            })
        # Atom fallback
        if not out:
            atom_ns = "{http://www.w3.org/2005/Atom}"
            for entry in root.findall(f".//{atom_ns}entry"):
                title = _strip_html(entry.findtext(f"{atom_ns}title") or "")
                link_el = entry.find(f"{atom_ns}link")
                link = link_el.get("href") if link_el is not None else ""
                summary = _strip_html(entry.findtext(f"{atom_ns}summary") or "")
                pub = _parse_date(entry.findtext(f"{atom_ns}updated"))
                if not title or not link:
                    continue
                out.append({
                    "title": title,
                    "summary": summary[:280],
                    "url": link,
                    "published": pub,
                    "source": source_url,
                })
        return out


class NewsAPIProvider(BaseProvider):
    category = "news"
    source_id = "newsapi"

    BASE = "https://newsapi.org/v2/everything"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = (api_key or os.environ.get("NEWSAPI_KEY") or "").strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("NEWSAPI_KEY required")
        data = get_json(
            self.BASE,
            params={
                "q": query,
                "pageSize": min(limit, 100),
                "sortBy": "publishedAt",
                "language": "tr",
            },
            headers={"X-Api-Key": self.api_key},
            timeout=8.0,
        )
        out: list[dict[str, Any]] = []
        for art in data.get("articles") or []:
            out.append({
                "title": art.get("title"),
                "summary": (art.get("description") or "")[:280],
                "url": art.get("url"),
                "published": art.get("publishedAt"),
                "source": (art.get("source") or {}).get("name"),
            })
        return out
