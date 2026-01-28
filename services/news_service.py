# services/news_service.py
from __future__ import annotations

import time
import hashlib
from typing import Any, Dict, List, Optional

from services.news_providers import CryptoPanicProvider, RSSProvider, NewsItem, _env_or_literal
from services.news_scoring import score_item, infer_symbols


class NewsService:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg or {}
        self.news_cfg = (cfg or {}).get("news") or {}
        self.enabled = bool(self.news_cfg.get("enabled", False))
        self.min_impact = float(self.news_cfg.get("min_impact_to_attach", 0.65))
        self.window_minutes = int(self.news_cfg.get("window_minutes", 90))
        self.max_items = int(self.news_cfg.get("max_items_per_symbol", 3))

        # In-memory cache: url_hash -> enriched record
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ts: Dict[str, int] = {}

        providers = self.news_cfg.get("providers") or {}

        self.cp = None
        if (providers.get("cryptopanic") or {}).get("enabled", False):
            token = _env_or_literal((providers["cryptopanic"].get("token") or ""))
            self.cp = CryptoPanicProvider(
                token=token,
                filter_mode=providers["cryptopanic"].get("filter", "hot"),
                languages=providers["cryptopanic"].get("languages", "en"),
            )

        self.rss = None
        if (providers.get("rss") or {}).get("enabled", False):
            feeds = providers["rss"].get("feeds") or []
            self.rss = RSSProvider(feeds=feeds)

        # Known symbols (for relevance)
        # Derive from your config symbols, stripping pairs
        all_syms = set()
        for s in (cfg.get("symbols") or []):
            all_syms.add(s.split("/")[0].upper())
        # Add equities universe tickers if present
        universes = cfg.get("universes") or {}
        eq = (universes.get("equities_us") or {}).get("symbols") or []
        for s in eq:
            all_syms.add(str(s).upper())
        self.known_symbols = sorted(all_syms)

        self.aliases = {
            "BITCOIN": "BTC",
            "ETHEREUM": "ETH",
            "SOLANA": "SOL",
        }

    def _key(self, item: NewsItem) -> str:
        h = hashlib.sha256((item.url or item.title).encode("utf-8")).hexdigest()[:24]
        return h

    def _within_window(self, ts: int) -> bool:
        return (int(time.time()) - ts) <= self.window_minutes * 60

    def fetch_all(self) -> List[NewsItem]:
        if not self.enabled:
            return []

        items: List[NewsItem] = []
        if self.cp:
            items.extend(self.cp.fetch(limit=80))
        if self.rss:
            items.extend(self.rss.fetch(limit_per_feed=25))

        # basic dedupe by url/title hash
        seen = set()
        out = []
        for it in items:
            k = self._key(it)
            if k in seen:
                continue
            seen.add(k)
            out.append(it)
        return out

    def get_snapshot_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Returns a compact snapshot safe to store in signal_snapshot/trade.meta.
        """
        if not self.enabled:
            return {"enabled": False, "items": [], "aggregate": {}}

        base = symbol.split("/")[0].upper()
        now = int(time.time())

        items = self.fetch_all()

        enriched = []
        for it in items:
            k = self._key(it)

            # cached?
            if k in self._cache and self._within_window(self._cache_ts.get(k, now)):
                rec = self._cache[k]
            else:
                s = score_item(it)
                syms = infer_symbols(it.title, self.known_symbols, self.aliases)
                rec = {
                    "ts": it.ts,
                    "source": it.source,
                    "title": it.title,
                    "url": it.url,
                    "symbols": syms,
                    "impact": s["impact"],
                    "category": s["category"],
                    "bias": s["bias"],
                    "why": s["why"],
                }
                self._cache[k] = rec
                self._cache_ts[k] = now

            # relevance
            if base in (rec.get("symbols") or []) and rec.get("impact", 0.0) >= self.min_impact:
                enriched.append(rec)

        # sort by impact then recency
        enriched.sort(key=lambda r: (r.get("impact", 0.0), r.get("ts", 0)), reverse=True)
        top = enriched[: self.max_items]

        agg = {
            "impact_max": max([r["impact"] for r in top], default=0.0),
            "impact_sum": sum([r["impact"] for r in top], start=0.0),
            "dominant_bias": (top[0]["bias"] if top else "unknown"),
            "count": len(top),
        }

        return {"enabled": True, "items": top, "aggregate": agg, "ts": now}
