from app.config import get_settings

def test_live_mode_locked_by_default():
    s = get_settings()
    assert s.live_trading_enabled is False
    assert s.live_mode_locked is True
