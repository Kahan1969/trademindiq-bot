from dataclasses import dataclass

@dataclass
class BotState:
    trading_enabled: bool = True     # pause/resume scanning & execution
    live_enabled: bool = False       # PAPER vs LIVE
    one_tap_enabled: bool = True     # enable /buy /sell buttons
