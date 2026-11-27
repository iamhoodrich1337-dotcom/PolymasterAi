from app.core.live_guard import live_mode_label


def test_live_mode_locked_by_default(monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.live_trading_enabled is False
    assert settings.live_mode_locked is True
    get_settings.cache_clear()


def test_live_label_follows_the_setting():
    assert live_mode_label(False) == "LOCKED"
    assert live_mode_label(True).startswith("UNLOCKED")
