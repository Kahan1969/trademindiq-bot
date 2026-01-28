import io
import matplotlib.pyplot as plt
from typing import List


def build_ema_chart(closes: List[float], ema9: List[float],
                    ema20: List[float], ema50: List[float],
                    title: str) -> bytes:
    fig, ax = plt.subplots()
    ax.plot(closes, label="Close")
    ax.plot(ema9, label="EMA9")
    ax.plot(ema20, label="EMA20")
    ax.plot(ema50, label="EMA50")
    ax.set_title(title)
    ax.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
