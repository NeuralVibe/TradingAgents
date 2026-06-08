import numpy as np
import pandas as pd

from backend.app.quant_engine import BacktestEngine
from backend.app.validation_engine import (
    POINT_IN_TIME_RISK_FLAGS,
    ValidationEngine,
)


def _price_frame():
    dates = pd.date_range("2026-01-01", "2026-04-30", freq="D")
    steps = np.arange(len(dates))
    return pd.DataFrame(
        {
            "AAA": 100.0 + steps * 0.45,
            "BBB": 90.0 - steps * 0.08,
            "SPY": 400.0 + steps * 0.2,
        },
        index=dates,
    )


def _signals():
    return [
        {
            "ticker": "AAA",
            "date": "2026-01-05",
            "side": "BUY",
            "confidence": 0.8,
            "horizon_days": 5,
            "risk_reward_ratio": 1.6,
            "price_attractiveness_score": 0.65,
            "volatility_regime": "normal",
            "risk_flags": ["custom_flag"],
            "calculation_basis": {
                "quant_price_setup": {"selected_stop_method": "atr_stop"}
            },
        },
        {
            "ticker": "AAA",
            "date": "2026-01-20",
            "side": "BUY",
            "confidence": 0.7,
            "horizon_days": 6,
            "risk_reward_ratio": 0.9,
            "price_attractiveness_score": 0.7,
            "volatility_regime": "normal",
            "risk_flags": [],
            "calculation_basis": {},
        },
        {
            "ticker": "BBB",
            "date": "2026-02-10",
            "side": "OVERWEIGHT",
            "confidence": 0.6,
            "horizon_days": 5,
            "risk_reward_ratio": 1.4,
            "price_attractiveness_score": 0.2,
            "volatility_regime": "high",
            "risk_flags": ["near_resistance"],
            "calculation_basis": {"signal_gate": {"original_side": "BUY"}},
        },
        {
            "ticker": "AAA",
            "date": "2026-03-01",
            "side": "SELL",
            "confidence": 0.5,
            "horizon_days": 5,
            "risk_reward_ratio": None,
            "price_attractiveness_score": None,
            "volatility_regime": "normal",
            "risk_flags": [],
            "calculation_basis": {},
        },
    ]


def _patch_prices(monkeypatch):
    prices = _price_frame()

    def fake_fetch_price_history(tickers, start_date, end_date):
        columns = [ticker for ticker in tickers if ticker in prices.columns]
        return prices.loc[pd.to_datetime(start_date) : pd.to_datetime(end_date), columns]

    monkeypatch.setattr(
        BacktestEngine,
        "fetch_price_history",
        staticmethod(fake_fetch_price_history),
    )
    monkeypatch.setattr(
        BacktestEngine,
        "fetch_ohlc_history",
        staticmethod(lambda tickers, start_date, end_date: pd.DataFrame()),
    )


def test_generate_walk_forward_windows_has_no_train_test_overlap():
    windows = ValidationEngine.generate_walk_forward_windows(
        "2026-01-01",
        "2026-04-30",
        train_window_days=30,
        test_window_days=15,
        step_days=15,
    )

    assert windows
    for window in windows:
        assert pd.to_datetime(window["train_end"]) < pd.to_datetime(window["test_start"])
        assert pd.to_datetime(window["test_start"]) <= pd.to_datetime(window["test_end"])


def test_parameter_grid_combination_count():
    grid = ValidationEngine.build_parameter_grid(
        sizing_modes=["fixed", "confidence"],
        slippage_values=[0.0, 0.001],
        min_risk_reward_values=[1.0, 1.5],
        min_price_attractiveness_values=[0.25, 0.5],
    )

    assert len(grid) == 16
    assert grid[0] == {
        "sizing_mode": "fixed",
        "slippage": 0.0,
        "min_risk_reward": 1.0,
        "min_price_attractiveness": 0.25,
    }


def test_filter_signals_uses_risk_reward_and_price_attractiveness():
    filtered, events = ValidationEngine.filter_signals(
        _signals(),
        min_risk_reward=1.2,
        min_price_attractiveness=0.35,
    )

    assert [signal["date"] for signal in filtered] == ["2026-01-05", "2026-03-01"]
    assert [event["flag"] for event in events] == [
        "filtered_low_risk_reward",
        "filtered_low_price_attractiveness",
    ]


def test_parameter_sweep_selects_best_parameters(monkeypatch):
    _patch_prices(monkeypatch)

    result = ValidationEngine.run_parameter_sweep(
        signals=_signals(),
        start_date="2026-01-01",
        end_date="2026-04-30",
        initial_capital=100000.0,
        sizing_modes=["fixed"],
        slippage_values=[0.0],
        min_risk_reward_values=[1.0, 1.5],
        min_price_attractiveness_values=[0.25],
        min_trades=1,
    )

    assert result["best_parameters"] is not None
    assert len(result["results"]) == 2
    assert result["results"][0]["score"] >= result["results"][1]["score"]
    assert result["ticker_breakdown"]
    assert result["regime_breakdown"]


def test_insufficient_trade_count_is_flagged(monkeypatch):
    _patch_prices(monkeypatch)

    result = ValidationEngine.run_parameter_sweep(
        signals=_signals()[:1],
        start_date="2026-01-01",
        end_date="2026-01-31",
        initial_capital=100000.0,
        sizing_modes=["fixed"],
        slippage_values=[0.0],
        min_risk_reward_values=[1.0],
        min_price_attractiveness_values=[0.25],
        min_trades=99,
    )

    assert "insufficient_trade_count" in result["results"][0]["risk_flags"]


def test_risk_flag_aggregation_includes_point_in_time_zero_flags():
    counts = ValidationEngine.risk_flag_counts(_signals())
    details = ValidationEngine.risk_flag_details(_signals())

    assert counts["custom_flag"] == 1
    assert counts["near_resistance"] == 1
    for flag in POINT_IN_TIME_RISK_FLAGS:
        assert flag in counts

    pit_rows = [row for row in details if row["flag"] in POINT_IN_TIME_RISK_FLAGS]
    assert len(pit_rows) == len(POINT_IN_TIME_RISK_FLAGS)
    assert any(row["flag"] == "quant_price_setup_unavailable" and row["count"] == 0 for row in pit_rows)


def test_backtest_trade_preserves_source_signal_metadata(monkeypatch):
    _patch_prices(monkeypatch)

    result = BacktestEngine.run_portfolio_backtest(
        signals=_signals()[:1],
        start_date="2026-01-01",
        end_date="2026-01-31",
        initial_capital=100000.0,
        sizing_mode="fixed",
        slippage=0.0,
    )

    assert result["trades"]
    trade = result["trades"][0]
    assert trade["signal_date"] == "2026-01-05"
    assert trade["signal_risk_flags"] == ["custom_flag"]
    assert trade["signal_calculation_basis"]["quant_price_setup"]["selected_stop_method"] == "atr_stop"


def test_risk_flag_details_uses_completed_trades_for_affected_trade_count():
    trades = [
        {
            "ticker": "AAA",
            "entry_date": "2026-01-06",
            "signal_date": "2026-01-05",
            "signal_risk_flags": ["custom_flag"],
        }
    ]

    details = ValidationEngine.risk_flag_details(_signals(), trades=trades)
    by_flag = {row["flag"]: row for row in details}

    assert by_flag["custom_flag"]["count"] == 1
    assert by_flag["custom_flag"]["affected_trade_count"] == 1
    assert by_flag["near_resistance"]["count"] == 1
    assert by_flag["near_resistance"]["affected_trade_count"] == 0


def test_filtered_risk_flag_count_does_not_imply_affected_trade_count(monkeypatch):
    _patch_prices(monkeypatch)

    result = ValidationEngine.run_parameter_sweep(
        signals=_signals()[:2],
        start_date="2026-01-01",
        end_date="2026-01-31",
        initial_capital=100000.0,
        sizing_modes=["fixed"],
        slippage_values=[0.0],
        min_risk_reward_values=[1.2],
        min_price_attractiveness_values=[0.0],
        min_trades=0,
    )
    by_flag = {row["flag"]: row for row in result["risk_flag_details"]}

    assert by_flag["filtered_low_risk_reward"]["count"] == 1
    assert by_flag["filtered_low_risk_reward"]["affected_trade_count"] == 0
    assert by_flag["custom_flag"]["affected_trade_count"] == 1


def test_walk_forward_validation_returns_window_metrics(monkeypatch):
    _patch_prices(monkeypatch)

    result = ValidationEngine.run_walk_forward_validation(
        signals=_signals(),
        start_date="2026-01-01",
        end_date="2026-04-30",
        initial_capital=100000.0,
        train_window_days=25,
        test_window_days=25,
        step_days=25,
        min_trades_per_window=0,
        sizing_modes=["fixed"],
        slippage_values=[0.0],
        min_risk_reward_values=[1.0],
        min_price_attractiveness_values=[0.25],
    )

    assert result["windows"]
    assert result["summary"]["total_windows"] == len(result["windows"])
    for window in result["windows"]:
        assert pd.to_datetime(window["train_end"]) < pd.to_datetime(window["test_start"])
        assert "selected_parameters" in window
        assert "test_summary" in window


def test_validation_summary_combines_base_sweep_and_walk_forward(monkeypatch):
    _patch_prices(monkeypatch)

    result = ValidationEngine.build_validation_summary(
        signals=_signals(),
        start_date="2026-01-01",
        end_date="2026-04-30",
        initial_capital=100000.0,
        train_window_days=25,
        test_window_days=25,
        step_days=25,
        min_trades_per_window=0,
        sizing_modes=["fixed"],
        slippage_values=[0.0],
        min_risk_reward_values=[1.0],
        min_price_attractiveness_values=[0.25],
    )

    assert "base_summary" in result
    assert result["best_parameters"] is not None
    assert result["summary"]["total_windows"] == len(result["windows"])
    assert result["calculation_basis"]["signal_count"] == len(_signals())
