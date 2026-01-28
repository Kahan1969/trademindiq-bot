from typing import List, Dict, Any
import numpy as np


def ema(values: List[float], period: int) -> List[float]:
    arr = np.array(values, dtype=float)
    if len(arr) < period:
        return [float("nan")] * len(arr)
    alpha = 2 / (period + 1)
    ema_vals = [arr[0]]
    for price in arr[1:]:
        ema_vals.append(alpha * price + (1 - alpha) * ema_vals[-1])
    return ema_vals


def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return [float("nan")] * len(closes)
    alpha = 1 / period
    atr_vals = [trs[0]]
    for tr in trs[1:]:
        atr_vals.append(alpha * tr + (1 - alpha) * atr_vals[-1])
    # pad first element to align length
    return [float("nan")] + atr_vals


def rel_volume(volumes: List[float], lookback: int = 20) -> float:
    if len(volumes) < lookback + 1:
        return 1.0
    recent = volumes[-1]
    avg_prev = sum(volumes[-(lookback + 1):-1]) / lookback
    if avg_prev <= 0:
        return 1.0
    return recent / avg_prev


def gap_percent(prev_close: float, current_open: float) -> float:
    if prev_close <= 0:
        return 0.0
    return (current_open - prev_close) / prev_close * 100.0


def compute_all(candles: List[List[float]]) -> Dict[str, Any]:
    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    vols = [c[5] for c in candles]
    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    atr14 = atr(highs, lows, closes, 14)
    rv = rel_volume(vols, 20)
    g = gap_percent(closes[-2], candles[-1][1]) if len(candles) >= 2 else 0.0
    return {
        "closes": closes,
        "ema9": ema9,
        "ema20": ema20,
        "ema50": ema50,
        "atr14": atr14,
        "rel_vol": rv,
        "gap_pct": g,
        "volumes": vols,
    }
