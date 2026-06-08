import pandas as pd
import pytest

from tradingagents.quant.price_evaluation import (
    calculate_atr,
    calculate_position_size_pct,
    calculate_risk_reward,
    calculate_stop_loss,
    calculate_take_profit,
    calculate_trend_score,
    calculate_volatility_regime,
    calculate_volume_score,
    detect_support_resistance,
    evaluate_price_attractiveness,
    evaluate_price_setup,
    validate_ohlcv,
)


def _ohlcv(closes, highs=None, lows=None, volumes=None):
    highs = highs if highs is not None else [close + 1.0 for close in closes]
    lows = lows if lows is not None else [close - 1.0 for close in closes]
    volumes = volumes if volumes is not None else [1000.0] * len(closes)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=pd.date_range("2026-01-01", periods=len(closes), freq="D"),
    )


def test_calculate_atr_matches_manual_true_range():
    data = _ohlcv(
        closes=[10.0, 12.0, 11.0],
        highs=[11.0, 13.0, 12.0],
        lows=[9.0, 10.0, 10.5],
    )

    result = calculate_atr(data, period=3)

    # TR: 2.0, max(3.0, 3.0, 0.0), max(1.5, 0.0, 1.5)
    assert result["atr"] == pytest.approx((2.0 + 3.0 + 1.5) / 3.0)
    assert result["calculation_basis"]["formula"].startswith("max(high-low")


def test_trend_score_identifies_up_down_and_mixed_trends():
    uptrend = _ohlcv([float(i) for i in range(10, 230)])
    downtrend = _ohlcv([float(i) for i in range(229, 9, -1)])
    mixed = _ohlcv(([100.0, 101.0, 99.0, 102.0, 98.0] * 44))

    assert calculate_trend_score(uptrend)["trend_label"] == "strong_uptrend"
    assert calculate_trend_score(uptrend)["trend_score"] == 1.0
    assert calculate_trend_score(downtrend)["trend_label"] == "strong_downtrend"
    assert calculate_trend_score(downtrend)["trend_score"] == 0.0
    assert calculate_trend_score(mixed)["trend_label"] == "mixed"


def test_volatility_regime_thresholds():
    low = _ohlcv([100.0] * 20, highs=[100.5] * 20, lows=[99.5] * 20)
    normal = _ohlcv([100.0] * 20, highs=[101.9] * 20, lows=[98.1] * 20)
    high = _ohlcv([100.0] * 20, highs=[103.9] * 20, lows=[96.1] * 20)
    extreme = _ohlcv([100.0] * 20, highs=[106.0] * 20, lows=[94.0] * 20)

    assert calculate_volatility_regime(low)["volatility_regime"] == "low"
    assert calculate_volatility_regime(normal)["volatility_regime"] == "normal"
    assert calculate_volatility_regime(high)["volatility_regime"] == "high"
    extreme_result = calculate_volatility_regime(extreme)
    assert extreme_result["volatility_regime"] == "extreme"
    assert "extreme_volatility" in extreme_result["risk_flags"]


def test_volume_score_missing_spike_and_weak_cases():
    missing_volume = _ohlcv([100.0, 101.0, 102.0]).drop(columns=["Volume"])
    spike = _ohlcv([100.0] * 22, volumes=[1000.0] * 21 + [2500.0])
    weak = _ohlcv([100.0] * 22, volumes=[1000.0] * 21 + [300.0])

    missing_result = calculate_volume_score(missing_volume)
    assert missing_result["volume_score"] is None
    assert "missing_volume" in missing_result["risk_flags"]

    spike_result = calculate_volume_score(spike)
    assert spike_result["volume_label"] == "volume_spike"
    assert "volume_spike" in spike_result["risk_flags"]

    weak_result = calculate_volume_score(weak)
    assert weak_result["volume_label"] == "weak_volume"
    assert "weak_volume" in weak_result["risk_flags"]


def test_support_resistance_excludes_latest_bar():
    data = _ohlcv(
        closes=[10.0, 11.0, 12.0, 13.0],
        highs=[12.0, 13.0, 14.0, 50.0],
        lows=[8.0, 9.0, 10.0, 1.0],
    )

    result = detect_support_resistance(data, lookback=3)

    assert result["support"] == 8.0
    assert result["resistance"] == 14.0
    assert result["calculation_basis"]["used_latest_bar"] is False


def test_stop_loss_must_be_below_entry_and_records_selected_method():
    valid = calculate_stop_loss(entry_price=100.0, atr=2.0, support=97.0)
    invalid = calculate_stop_loss(entry_price=100.0, atr=None, support=101.0)

    assert valid["stop_loss"] < 100.0
    assert valid["calculation_basis"]["selected_stop_method"] in {
        "atr_stop",
        "support_stop",
    }
    assert invalid["stop_loss"] is None
    assert "invalid_stop_loss" in invalid["risk_flags"]


def test_wide_stop_loss_is_flagged():
    result = calculate_stop_loss(entry_price=100.0, atr=20.0, support=None)

    assert result["stop_loss"] == 70.0
    assert "wide_stop_loss" in result["risk_flags"]


def test_take_profit_must_be_above_entry_and_resistance_cap_is_flagged():
    capped = calculate_take_profit(entry_price=100.0, stop_loss=95.0, resistance=106.0)
    invalid = calculate_take_profit(entry_price=100.0, stop_loss=100.0, resistance=110.0)

    assert capped["take_profit"] == 106.0
    assert "resistance_caps_target" in capped["risk_flags"]
    assert invalid["take_profit"] is None
    assert "invalid_take_profit" in invalid["risk_flags"]


def test_resistance_cap_lowers_risk_reward_ratio():
    uncapped = calculate_take_profit(entry_price=100.0, stop_loss=95.0, resistance=120.0)
    capped = calculate_take_profit(entry_price=100.0, stop_loss=95.0, resistance=106.0)

    uncapped_rr = calculate_risk_reward(100.0, 95.0, uncapped["take_profit"])
    capped_rr = calculate_risk_reward(100.0, 95.0, capped["take_profit"])

    assert uncapped_rr["risk_reward_ratio"] == pytest.approx(2.0)
    assert capped_rr["risk_reward_ratio"] == pytest.approx(1.2)
    assert capped_rr["risk_reward_ratio"] < uncapped_rr["risk_reward_ratio"]


def test_invalid_stop_safely_nulls_risk_reward_and_position_size():
    rr = calculate_risk_reward(entry_price=100.0, stop_loss=100.0, take_profit=110.0)
    size = calculate_position_size_pct(entry_price=100.0, stop_loss=100.0)

    assert rr["risk_reward_ratio"] is None
    assert "invalid_stop_loss" in rr["risk_flags"]
    assert size["position_size_pct"] is None
    assert "invalid_position_risk" in size["risk_flags"]


def test_position_size_uses_stop_distance_risk_budgeting_only():
    result = calculate_position_size_pct(
        entry_price=100.0,
        stop_loss=95.0,
        account_risk_pct=0.01,
        max_position_pct=0.15,
    )

    assert result["trade_risk_pct"] == pytest.approx(0.05)
    assert result["position_size_pct"] == pytest.approx(0.15)
    assert result["calculation_basis"]["formula"] == "account_risk_pct / trade_risk_pct"


def test_price_attractiveness_reports_risk_flags():
    data = _ohlcv(
        closes=[100.0] * 80 + [113.0],
        highs=[105.0] * 80 + [114.0],
        lows=[95.0] * 80 + [112.0],
        volumes=[1000.0] * 80 + [300.0],
    )

    result = evaluate_price_attractiveness(
        data,
        entry_price=103.0,
        stop_loss=100.0,
        take_profit=106.0,
    )

    assert "poor_risk_reward" in result["risk_flags"]
    assert "near_resistance" in result["risk_flags"]
    assert "weak_volume" in result["risk_flags"]
    assert result["price_attractiveness_score"] < 0.5


def test_validate_ohlcv_handles_nan_short_non_positive_and_high_below_low():
    data = pd.DataFrame(
        {
            "High": [10.0, 8.0, -1.0, 12.0],
            "Low": [9.0, 9.0, 1.0, 11.0],
            "Close": [9.5, 8.5, 1.0, None],
        }
    )

    result = validate_ohlcv(data)

    assert "rows_with_missing_price" in result["risk_flags"]
    assert "non_positive_price" in result["risk_flags"]
    assert "high_below_low" in result["risk_flags"]
    assert "insufficient_ohlcv_rows" in result["risk_flags"]
    assert len(result["ohlcv"]) == 1


def test_all_public_results_use_consistent_common_keys():
    data = _ohlcv([100.0] * 30, highs=[102.0] * 30, lows=[98.0] * 30)
    results = [
        validate_ohlcv(data),
        calculate_atr(data),
        calculate_trend_score(data),
        calculate_volatility_regime(data),
        calculate_volume_score(data),
        detect_support_resistance(data),
        calculate_stop_loss(100.0, 2.0, 95.0),
        calculate_take_profit(100.0, 95.0, 108.0),
        calculate_risk_reward(100.0, 95.0, 110.0),
        calculate_position_size_pct(100.0, 95.0),
        evaluate_price_attractiveness(data, 100.0, 95.0, 110.0),
        evaluate_price_setup(data),
    ]

    for result in results:
        assert "risk_flags" in result
        assert "calculation_basis" in result
        assert "warnings" not in result
        assert "flags" not in result
        assert "basis" not in result


def test_evaluate_price_setup_integrates_without_action_key():
    data = _ohlcv(
        closes=[float(90 + i * 0.2) for i in range(120)],
        highs=[float(91 + i * 0.2) for i in range(120)],
        lows=[float(89 + i * 0.2) for i in range(120)],
        volumes=[1000.0] * 119 + [1600.0],
    )

    result = evaluate_price_setup(data, support_resistance_lookback=60)

    assert "action" not in result
    assert result["entry_price"] == pytest.approx(data["Close"].iloc[-1])
    assert result["stop_loss"] is not None
    assert result["stop_loss"] < result["entry_price"]
    assert result["take_profit"] is not None
    assert result["take_profit"] > result["entry_price"]
    assert result["risk_reward_ratio"] is not None
    assert result["position_size_pct"] is not None
    assert "scores" in result
    assert "regimes" in result
