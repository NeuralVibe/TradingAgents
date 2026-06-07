import pytest
import numpy as np
import pandas as pd
from backend.app.quant_engine import SignalExtractor, BacktestEngine

def test_signal_extractor_parse_recommendation():
    """Verify rating-to-side mapping is parsed correctly."""
    assert SignalExtractor.parse_recommendation("**Rating**: Buy\nEnter at $150") == "BUY"
    assert SignalExtractor.parse_recommendation("**Rating**: Overweight") == "OVERWEIGHT"
    assert SignalExtractor.parse_recommendation("**Rating**: Sell") == "SELL"
    assert SignalExtractor.parse_recommendation("**Rating**: Underweight") == "UNDERWEIGHT"
    assert SignalExtractor.parse_recommendation("**Rating**: Hold") == "HOLD"
    assert SignalExtractor.parse_recommendation("") == "HOLD"

def test_signal_extractor_extract_confidence():
    """Verify confidence values are parsed or inferred correctly."""
    # Extracted from text
    assert SignalExtractor.extract_confidence("Confidence: 85%", "BUY") == 0.85
    assert SignalExtractor.extract_confidence("신뢰도: 0.90", "BUY") == 0.90
    assert SignalExtractor.extract_confidence("확신도: 75", "SELL") == 0.75
    
    # Inferred from side/rating keywords
    assert SignalExtractor.extract_confidence("Rating: Strong Buy", "BUY") == 0.90
    assert SignalExtractor.extract_confidence("Rating: Buy", "BUY") == 0.80
    assert SignalExtractor.extract_confidence("Rating: Overweight", "BUY") == 0.65
    assert SignalExtractor.extract_confidence("Rating: Hold", "HOLD") == 0.50

def test_signal_extractor_extract_horizon_days():
    """Verify holding horizon periods are parsed correctly."""
    assert SignalExtractor.extract_horizon_days("Horizon: 5 days") == 5
    assert SignalExtractor.extract_horizon_days("투자 기간: 10일") == 10
    assert SignalExtractor.extract_horizon_days("Time Horizon: 2 weeks") == 10
    assert SignalExtractor.extract_horizon_days("Horizon: 1 month") == 21
    assert SignalExtractor.extract_horizon_days("No matching horizon text") == 5

def test_signal_extractor_extract_price_target():
    """Verify target price is extracted correctly."""
    assert SignalExtractor.extract_price_target("Price Target: $155.50") == 155.50
    assert SignalExtractor.extract_price_target("목표가: 180,000") == 180000.0
    assert SignalExtractor.extract_price_target("No target") is None

def test_signal_extractor_parse_decision_to_signal():
    """Verify full decision parser outputs standardized dictionary."""
    text = (
        "**Rating**: Buy\n"
        "**Executive Summary**: Buy AAPL immediately.\n"
        "**Time Horizon**: 10 days\n"
        "**Price Target**: $175.25\n"
        "Confidence: 90%"
    )
    sig = SignalExtractor.parse_decision_to_signal("AAPL", "2026-05-25", text)
    assert sig["ticker"] == "AAPL"
    assert sig["date"] == "2026-05-25"
    assert sig["side"] == "BUY"
    assert sig["confidence"] == 0.90
    assert sig["horizon_days"] == 10
    assert sig["price_target"] == 175.25

def test_backtest_engine_summary_math():
    """Verify the metrics math matches theoretical expectations under controlled inputs."""
    # Mock daily values
    equity_curve = [
        {"date": "2026-05-01", "portfolio_value": 100000.0, "cash": 100000.0, "benchmark_value": 400.0},
        {"date": "2026-05-02", "portfolio_value": 101000.0, "cash": 101000.0, "benchmark_value": 402.0},
        {"date": "2026-05-03", "portfolio_value": 102010.0, "cash": 102010.0, "benchmark_value": 404.0},
        {"date": "2026-05-04", "portfolio_value": 101000.0, "cash": 101000.0, "benchmark_value": 402.0},
        {"date": "2026-05-05", "portfolio_value": 103000.0, "cash": 103000.0, "benchmark_value": 406.0},
    ]
    
    trades = [
        {"ticker": "NVDA", "profit": 2000.0},
        {"ticker": "AAPL", "profit": -1000.0},
        {"ticker": "TSLA", "profit": 1500.0},
    ]
    
    prices_df = pd.DataFrame({
        "SPY": [400.0, 402.0, 404.0, 402.0, 406.0]
    }, index=pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05"]))
    
    summary = BacktestEngine._calculate_backtest_summary(
        equity_curve=equity_curve,
        trades=trades,
        prices_df=prices_df,
        benchmark="SPY",
        trading_dates=prices_df.index
    )
    
    assert summary["cumulative_return"] == 0.03 # 3% cumulative gain
    assert summary["total_trades"] == 3
    assert summary["winning_trades"] == 2
    assert summary["losing_trades"] == 1
    assert summary["win_rate"] == pytest.approx(0.6667, abs=1e-4)
    assert summary["profit_factor"] == 3.5 # 3500 gross gain / 1000 loss
    assert summary["max_drawdown"] == pytest.approx(-0.0099, abs=1e-4) # peak was 102010, bottom 101000 -> -0.99%

def test_backtest_uses_next_trading_day_for_entry(monkeypatch):
    """A signal generated on D should enter on the next trading date, not D."""
    prices = pd.DataFrame(
        {
            "AAPL": [100.0, 110.0, 120.0],
            "SPY": [400.0, 404.0, 408.0],
        },
        index=pd.to_datetime(["2026-05-01", "2026-05-04", "2026-05-05"]),
    )
    monkeypatch.setattr(
        BacktestEngine,
        "fetch_price_history",
        staticmethod(lambda tickers, start_date, end_date: prices),
    )

    result = BacktestEngine.run_portfolio_backtest(
        signals=[
            {
                "ticker": "AAPL",
                "date": "2026-05-01",
                "side": "BUY",
                "confidence": 1.0,
                "horizon_days": 1,
                "price_target": None,
            }
        ],
        start_date="2026-05-01",
        end_date="2026-05-05",
        initial_capital=100000.0,
        slippage=0.0,
    )

    assert len(result["trades"]) == 1
    assert result["trades"][0]["entry_date"] == "2026-05-04"
    assert result["trades"][0]["entry_price"] == 110.0


def test_backtest_skips_signal_without_next_trading_day(monkeypatch):
    """A signal on the final trading date has no executable next bar."""
    prices = pd.DataFrame(
        {
            "AAPL": [100.0, 110.0],
            "SPY": [400.0, 404.0],
        },
        index=pd.to_datetime(["2026-05-01", "2026-05-04"]),
    )
    monkeypatch.setattr(
        BacktestEngine,
        "fetch_price_history",
        staticmethod(lambda tickers, start_date, end_date: prices),
    )

    result = BacktestEngine.run_portfolio_backtest(
        signals=[
            {
                "ticker": "AAPL",
                "date": "2026-05-04",
                "side": "BUY",
                "confidence": 1.0,
                "horizon_days": 1,
                "price_target": None,
            }
        ],
        start_date="2026-05-01",
        end_date="2026-05-04",
        initial_capital=100000.0,
        slippage=0.0,
    )

    assert result["trades"] == []


def test_backtest_does_not_trade_before_first_valid_price(monkeypatch):
    """Missing entry-bar prices must not be filled from future prices."""
    prices = pd.DataFrame(
        {
            "AAPL": [np.nan, np.nan, 120.0],
            "SPY": [400.0, 404.0, 408.0],
        },
        index=pd.to_datetime(["2026-05-01", "2026-05-04", "2026-05-05"]),
    )
    monkeypatch.setattr(
        BacktestEngine,
        "fetch_price_history",
        staticmethod(lambda tickers, start_date, end_date: prices),
    )

    result = BacktestEngine.run_portfolio_backtest(
        signals=[
            {
                "ticker": "AAPL",
                "date": "2026-05-01",
                "side": "BUY",
                "confidence": 1.0,
                "horizon_days": 1,
                "price_target": None,
            }
        ],
        start_date="2026-05-01",
        end_date="2026-05-05",
        initial_capital=100000.0,
        slippage=0.0,
    )

    assert result["trades"] == []


def test_fetch_price_history_does_not_backfill(monkeypatch):
    """fetch_price_history should leave leading NaNs instead of using bfill."""
    columns = pd.MultiIndex.from_product([["Close"], ["AAPL", "SPY"]])
    downloaded = pd.DataFrame(
        [[np.nan, 400.0], [110.0, 404.0]],
        columns=columns,
        index=pd.to_datetime(["2026-05-01", "2026-05-04"]),
    )

    def fake_download(tickers, start, end, auto_adjust, progress):
        return downloaded

    monkeypatch.setattr("backend.app.quant_engine.yf.download", fake_download)

    prices = BacktestEngine.fetch_price_history(
        ["AAPL", "SPY"],
        start_date="2026-05-01",
        end_date="2026-05-04",
    )

    assert pd.isna(prices.loc[pd.Timestamp("2026-05-01"), "AAPL"])
    assert prices.loc[pd.Timestamp("2026-05-04"), "AAPL"] == 110.0


def _patch_backtest_history(monkeypatch, close_prices, ohlc_prices=None):
    monkeypatch.setattr(
        BacktestEngine,
        "fetch_price_history",
        staticmethod(lambda tickers, start_date, end_date: close_prices),
    )
    if ohlc_prices is not None:
        monkeypatch.setattr(
            BacktestEngine,
            "fetch_ohlc_history",
            staticmethod(lambda tickers, start_date, end_date: ohlc_prices),
        )


def _buy_signal(**overrides):
    signal = {
        "ticker": "AAPL",
        "date": "2026-05-01",
        "side": "BUY",
        "confidence": 1.0,
        "horizon_days": 5,
        "price_target": None,
    }
    signal.update(overrides)
    return signal


def _close_prices():
    return pd.DataFrame(
        {
            "AAPL": [99.0, 100.0, 102.0, 108.0, 109.0],
            "SPY": [400.0, 401.0, 402.0, 403.0, 404.0],
        },
        index=pd.to_datetime(["2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07"]),
    )


def _ohlc_prices(highs, lows):
    return pd.DataFrame(
        {
            ("High", "AAPL"): highs,
            ("Low", "AAPL"): lows,
        },
        index=pd.to_datetime(["2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07"]),
    )


def test_backtest_exits_early_on_stop_loss(monkeypatch):
    close_prices = _close_prices()
    ohlc_prices = _ohlc_prices(
        highs=[100.0, 101.0, 103.0, 109.0, 110.0],
        lows=[98.0, 99.0, 94.0, 107.0, 108.0],
    )
    _patch_backtest_history(monkeypatch, close_prices, ohlc_prices)

    result = BacktestEngine.run_portfolio_backtest(
        signals=[_buy_signal(stop_loss=95.0, take_profit=120.0)],
        start_date="2026-05-01",
        end_date="2026-05-07",
        initial_capital=100000.0,
        slippage=0.01,
    )

    trade = result["trades"][0]
    assert trade["entry_date"] == "2026-05-04"
    assert trade["exit_date"] == "2026-05-05"
    assert trade["exit_reason"] == "stop_loss"
    assert trade["entry_price"] == 101.0
    assert trade["exit_price"] == 95.0
    assert trade["raw_return"] == pytest.approx(round((95.0 * 0.99 - 101.0) / 101.0, 4))


def test_backtest_exits_early_on_take_profit(monkeypatch):
    close_prices = _close_prices()
    ohlc_prices = _ohlc_prices(
        highs=[100.0, 101.0, 111.0, 109.0, 110.0],
        lows=[98.0, 99.0, 98.0, 107.0, 108.0],
    )
    _patch_backtest_history(monkeypatch, close_prices, ohlc_prices)

    result = BacktestEngine.run_portfolio_backtest(
        signals=[_buy_signal(stop_loss=95.0, take_profit=110.0)],
        start_date="2026-05-01",
        end_date="2026-05-07",
        initial_capital=100000.0,
        slippage=0.0,
    )

    trade = result["trades"][0]
    assert trade["entry_date"] == "2026-05-04"
    assert trade["exit_date"] == "2026-05-05"
    assert trade["exit_reason"] == "take_profit"
    assert trade["exit_price"] == 110.0


def test_backtest_stop_loss_wins_when_stop_and_take_profit_hit_same_day(monkeypatch):
    close_prices = _close_prices()
    ohlc_prices = _ohlc_prices(
        highs=[100.0, 101.0, 111.0, 109.0, 110.0],
        lows=[98.0, 99.0, 94.0, 107.0, 108.0],
    )
    _patch_backtest_history(monkeypatch, close_prices, ohlc_prices)

    result = BacktestEngine.run_portfolio_backtest(
        signals=[_buy_signal(stop_loss=95.0, take_profit=110.0)],
        start_date="2026-05-01",
        end_date="2026-05-07",
        initial_capital=100000.0,
        slippage=0.0,
    )

    trade = result["trades"][0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["exit_price"] == 95.0


def test_backtest_exits_on_horizon_when_stop_and_take_profit_not_hit(monkeypatch):
    close_prices = _close_prices()
    ohlc_prices = _ohlc_prices(
        highs=[100.0, 101.0, 103.0, 109.0, 110.0],
        lows=[98.0, 99.0, 97.0, 107.0, 108.0],
    )
    _patch_backtest_history(monkeypatch, close_prices, ohlc_prices)

    result = BacktestEngine.run_portfolio_backtest(
        signals=[_buy_signal(stop_loss=50.0, take_profit=200.0, horizon_days=2)],
        start_date="2026-05-01",
        end_date="2026-05-07",
        initial_capital=100000.0,
        slippage=0.0,
    )

    trade = result["trades"][0]
    assert trade["entry_date"] == "2026-05-04"
    assert trade["exit_date"] == "2026-05-06"
    assert trade["exit_reason"] == "horizon"
    assert trade["exit_price"] == 108.0


def test_backtest_preserves_horizon_exit_without_stop_or_take_profit(monkeypatch):
    close_prices = _close_prices()

    def fail_if_ohlc_requested(tickers, start_date, end_date):
        raise AssertionError("OHLC data should not be requested without stop/take-profit inputs")

    _patch_backtest_history(monkeypatch, close_prices)
    monkeypatch.setattr(
        BacktestEngine,
        "fetch_ohlc_history",
        staticmethod(fail_if_ohlc_requested),
    )

    result = BacktestEngine.run_portfolio_backtest(
        signals=[_buy_signal(horizon_days=1)],
        start_date="2026-05-01",
        end_date="2026-05-07",
        initial_capital=100000.0,
        slippage=0.0,
    )

    trade = result["trades"][0]
    assert trade["entry_date"] == "2026-05-04"
    assert trade["exit_date"] == "2026-05-05"
    assert trade["exit_reason"] == "horizon"
    assert trade["exit_price"] == 102.0
