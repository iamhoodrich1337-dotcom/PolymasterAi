from app.backtesting.metrics import compute_metrics

def test_metrics_with_mixed_pnls():
    m = compute_metrics([2.0, -1.0, 3.0, -1.0], initial_capital=100)
    assert m.total_trades == 4
    assert m.win_rate == 0.5
    assert m.profit_factor == 2.5
    assert m.roi == 0.03
