from typing import Tuple, List


def get_sentiment_and_news(symbol: str) -> Tuple[float, str, List[str]]:
    # Plug your previous news + sentiment logic here.
    # For now, just return bearish placeholder like your screenshot.
    score = -0.33
    label = "Bearish"
    links = [
        "https://cointelegraph.com/",  # replace with real links
    ]
    return score, label, links
