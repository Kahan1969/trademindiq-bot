# services/news_scoring.py
from __future__ import annotations

import re
from typing import Dict, List, Tuple
from services.news_providers import NewsItem

# High-signal keywords for volume swings
KEYWORD_WEIGHTS: List[Tuple[str, float, str]] = [
    ("listing", 0.85, "listing"),
    ("delist", 0.90, "delisting"),
    ("hack", 0.95, "hack_exploit"),
    ("exploit", 0.95, "hack_exploit"),
    ("breach", 0.85, "hack_exploit"),
    ("sec", 0.80, "regulation_legal"),
    ("lawsuit", 0.80, "regulation_legal"),
    ("etf", 0.75, "etf_macro"),
    ("halt", 0.85, "outage_incident"),
    ("outage", 0.80, "outage_incident"),
    ("airdrop", 0.70, "airdrop"),
    ("partnership", 0.65, "partnership"),
    ("upgrade", 0.60, "protocol_upgrade"),
]

SYMBOL_REGEX = re.compile(r"\b([A-Z]{2,6})\b")

def infer_symbols(title: str, known: List[str], aliases: Dict[str, str]) -> List[str]:
    """
    known: ["BTC","ETH","SOL"...]
    aliases: {"BITCOIN":"BTC","ETHEREUM":"ETH",...}
    """
    t = title.upper()
    syms = set()

    for k, v in aliases.items():
        if k.upper() in t:
            syms.add(v.upper())

    # also capture tickers
    for m in SYMBOL_REGEX.findall(t):
        if m in known:
            syms.add(m)

    return sorted(syms)

def score_item(item: NewsItem) -> Dict:
    t = item.title.lower()
    best = 0.25
    cat = "other"
    for kw, w, c in KEYWORD_WEIGHTS:
        if kw in t:
            if w > best:
                best = w
                cat = c
    # crude bias heuristics (safe defaults)
    bias = "unknown"
    if cat in ("listing", "partnership", "protocol_upgrade", "airdrop"):
        bias = "bullish"
    if cat in ("delisting", "hack_exploit", "outage_incident", "regulation_legal"):
        bias = "bearish"

    why = f"Keyword-driven: {cat}"
    return {"impact": float(best), "category": cat, "bias": bias, "why": why}
