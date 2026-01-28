import random
import datetime

def get_top_movers(symbols, n=10, seed=None):
    """
    Returns a rotating subset of n symbols from the master list.
    Rotation is based on the current day (or a provided seed).
    """
    if not symbols or n >= len(symbols):
        return symbols
    if seed is None:
        # Use the current day as a seed for daily rotation
        seed = int(datetime.date.today().strftime('%Y%m%d'))
    random.seed(seed)
    return random.sample(symbols, n)