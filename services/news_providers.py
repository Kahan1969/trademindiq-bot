# services/news_providers.py
from __future__ import annotations

import os
import time
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

try:
    import feedparser
except Exception:
    feedparser = None


def _env_or_literal(v: str) -> str:
    if isinstance(v, str) and v.startswith("ENV:"):
        return os.getenv(v.replace("ENV:", ""), "")
    return v or ""


@dataclass
class NewsItem:
    ts: int
    source: str
    title: str
    url: str
    raw: Dict[str, Any]


class CryptoPanicProvider:
    def __init__(self, token: str, filter_mode: str = "hot", languages: str = "en") -> None:
        self.token = token
        self.filter_mode = filter_mode
        self.languages = languages

    def fetch(self, limit: int = 50) -> List[NewsItem]:
        if not self.token:
            return []

        # Common CryptoPanic endpoint pattern
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": self.token,
            "public": "true",
            "filter": self.filter_mode,
            "kind": "news",
            "currencies": "",      # you can add "BTC,ETH,SOL" later if you want
            "regions": "",
            "languages": self.languages,
        }

        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json() or {}
        results = data.get("results") or []

        out: List[NewsItem] = []
        for it in results[:limit]:
            title = (it.get("title") or "").strip()
            link = (it.get("url") or it.get("original_url") or "").strip()
            published_at = it.get("published_at") or ""
            # If ts missing, use now
            ts = int(time.time())
            out.append(NewsItem(ts=ts, source="cryptopanic", title=title, url=link, raw=it))
        return out


class RSSProvider:
    def __init__(self, feeds: List[Dict[str, str]]) -> None:
        self.feeds = feeds

    def fetch(self, limit_per_feed: int = 20) -> List[NewsItem]:
        if feedparser is None:
            raise RuntimeError("feedparser not installed. Run: python3 -m pip install feedparser")

        out: List[NewsItem] = []
        now = int(time.time())

        for f in self.feeds:
            name = f.get("name") or "rss"
            url = f.get("url") or ""
            if not url:
                continue

            d = feedparser.parse(url)
            entries = d.entries or []
            for e in entries[:limit_per_feed]:
                title = (getattr(e, "title", "") or "").strip()
                link = (getattr(e, "link", "") or "").strip()
                # Many RSS feeds provide published_parsed; if missing, use now
                ts = now
                out.append(NewsItem(ts=ts, source=name, title=title, url=link, raw={"entry": dict(e)}))

        return out
