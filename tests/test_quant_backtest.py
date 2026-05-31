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
