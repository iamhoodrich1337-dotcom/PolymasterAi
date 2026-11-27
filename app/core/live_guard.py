"""Single place that describes the live-trading state. Real order submission does not exist in this code base;
a future live executor must call this guard and add further conditions (owner confirmation, passed tests, etc.)."""


def live_mode_label(live_trading_enabled: bool) -> str:
    return "UNLOCKED (executor not implemented)" if live_trading_enabled else "LOCKED"
