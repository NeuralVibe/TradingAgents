"""Deterministic OHLCV-based price evaluation utilities.

This module intentionally avoids network calls, database access, LLM calls,
and backtest-engine coupling. It accepts already available OHLCV data and
returns auditable calculation dictionaries for later signal construction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, TypedDict

import pandas as pd


RiskFlags = List[str]
CalculationBasis = Dict[str, Any]


class ValidationResult(TypedDict):
    ohlcv: pd.DataFrame
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class AtrResult(TypedDict):
    atr: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class TrendScoreResult(TypedDict):
    trend_score: Optional[float]
    trend_label: str
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class VolatilityRegimeResult(TypedDict):
    volatility_regime: Optional[str]
    volatility_pct: Optional[float]
    atr: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class VolumeScoreResult(TypedDict):
    volume_score: Optional[float]
    volume_label: str
    volume_ratio: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class SupportResistanceResult(TypedDict):
    support: Optional[float]
    resistance: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class EntryZoneResult(TypedDict):
    entry_price: Optional[float]
    entry_zone_low: Optional[float]
    entry_zone_high: Optional[float]
    price_location: str
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class StopLossResult(TypedDict):
    stop_loss: Optional[float]
    trade_risk_pct: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class TakeProfitResult(TypedDict):
    take_profit: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class RiskRewardResult(TypedDict):
    risk_reward_ratio: Optional[float]
    risk: Optional[float]
    reward: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class PositionSizeResult(TypedDict):
    position_size_pct: Optional[float]
    trade_risk_pct: Optional[float]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class PriceAttractivenessResult(TypedDict):
    price_attractiveness_score: Optional[float]
    risk_reward_ratio: Optional[float]
    price_location: str
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


class PriceSetupResult(TypedDict):
    current_price: Optional[float]
    entry_price: Optional[float]
    entry_zone_low: Optional[float]
    entry_zone_high: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    risk_reward_ratio: Optional[float]
    position_size_pct: Optional[float]
    levels: Dict[str, Optional[float]]
    scores: Dict[str, Optional[float]]
    regimes: Dict[str, Optional[str]]
    risk_flags: RiskFlags
    calculation_basis: CalculationBasis


_COLUMN_ALIASES = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
}

_REQUIRED_PRICE_COLUMNS = ("high", "low", "close")


def _merge_risk_flags(*groups: Sequence[str]) -> RiskFlags:
    merged: RiskFlags = []
    for group in groups:
        for flag in group:
            if flag not in merged:
                merged.append(flag)
    return merged


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def validate_ohlcv(ohlcv: pd.DataFrame) -> ValidationResult:
    """Return a normalized OHLCV copy and data-quality risk flags."""
    risk_flags: RiskFlags = []
    calculation_basis: CalculationBasis = {
        "required_price_columns": list(_REQUIRED_PRICE_COLUMNS),
        "optional_columns": ["open", "volume"],
        "fill_policy": "none",
    }

    if ohlcv is None or ohlcv.empty:
        return {
            "ohlcv": pd.DataFrame(),
            "risk_flags": ["missing_ohlcv"],
            "calculation_basis": {
                **calculation_basis,
                "original_rows": 0,
                "cleaned_rows": 0,
            },
        }

    original_rows = len(ohlcv)
    renamed_columns = {
        column: _COLUMN_ALIASES[str(column).strip().lower()]
        for column in ohlcv.columns
        if str(column).strip().lower() in _COLUMN_ALIASES
    }
    normalized = ohlcv.rename(columns=renamed_columns).copy()
    usable_columns = [
        column
        for column in ["open", "high", "low", "close", "volume"]
        if column in normalized.columns
    ]
    normalized = normalized.loc[:, usable_columns]

    missing_required = [
        column for column in _REQUIRED_PRICE_COLUMNS if column not in normalized.columns
    ]
    if missing_required:
        risk_flags.append("missing_required_columns")
        return {
            "ohlcv": pd.DataFrame(),
            "risk_flags": risk_flags,
            "calculation_basis": {
                **calculation_basis,
                "original_rows": original_rows,
                "cleaned_rows": 0,
                "missing_required_columns": missing_required,
            },
        }

    for column in usable_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    invalid_mask = pd.Series(False, index=normalized.index)
    missing_price_mask = normalized[list(_REQUIRED_PRICE_COLUMNS)].isna().any(axis=1)
    if bool(missing_price_mask.any()):
        risk_flags.append("rows_with_missing_price")
        invalid_mask = invalid_mask | missing_price_mask

    non_positive_mask = (normalized[list(_REQUIRED_PRICE_COLUMNS)] <= 0).any(axis=1)
    if bool(non_positive_mask.any()):
        risk_flags.append("non_positive_price")
        invalid_mask = invalid_mask | non_positive_mask

    high_below_low_mask = normalized["high"] < normalized["low"]
    if bool(high_below_low_mask.any()):
        risk_flags.append("high_below_low")
        invalid_mask = invalid_mask | high_below_low_mask

    cleaned = normalized.loc[~invalid_mask].copy()
    if "volume" not in cleaned.columns:
        risk_flags.append("missing_volume")
    elif bool((cleaned["volume"].isna() | (cleaned["volume"] <= 0)).any()):
        risk_flags.append("invalid_volume")

    if len(cleaned) < 2:
        risk_flags.append("insufficient_ohlcv_rows")

    return {
        "ohlcv": cleaned,
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            **calculation_basis,
            "original_rows": original_rows,
            "cleaned_rows": len(cleaned),
            "dropped_rows": original_rows - len(cleaned),
            "columns": list(cleaned.columns),
        },
    }


def calculate_atr(ohlcv: pd.DataFrame, period: int = 14) -> AtrResult:
    """Calculate ATR from high, low, and previous close."""
    validation = validate_ohlcv(ohlcv)
    data = validation["ohlcv"]
    risk_flags = list(validation["risk_flags"])
    if data.empty:
        return {
            "atr": None,
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_atr"]),
            "calculation_basis": {
                "period": period,
                "validation": validation["calculation_basis"],
            },
        }

    period = max(1, int(period))
    prev_close = data["close"].shift(1)
    true_range = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - prev_close).abs(),
            (data["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    if true_range.empty or true_range.isna().all():
        return {
            "atr": None,
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_atr"]),
            "calculation_basis": {
                "period": period,
                "validation": validation["calculation_basis"],
            },
        }

    window_used = min(period, len(true_range))
    if len(true_range) < period:
        risk_flags.append("short_atr_window")
    atr = float(true_range.tail(window_used).mean())

    return {
        "atr": atr,
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            "period": period,
            "window_used": window_used,
            "formula": "max(high-low, abs(high-previous_close), abs(low-previous_close))",
            "latest_true_range": float(true_range.iloc[-1]),
            "validation": validation["calculation_basis"],
        },
    }


def calculate_trend_score(ohlcv: pd.DataFrame) -> TrendScoreResult:
    """Score trend quality from moving-average alignment."""
    validation = validate_ohlcv(ohlcv)
    data = validation["ohlcv"]
    risk_flags = list(validation["risk_flags"])
    if data.empty:
        return {
            "trend_score": None,
            "trend_label": "insufficient_data",
            "risk_flags": _merge_risk_flags(risk_flags, ["insufficient_trend_window"]),
            "calculation_basis": {"validation": validation["calculation_basis"]},
        }

    close = data["close"]
    latest_close = float(close.iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

    if sma50 is None:
        risk_flags.append("insufficient_trend_window")
        trend_score = 0.5
        trend_label = "insufficient_data"
    elif sma200 is None:
        risk_flags.append("partial_trend_window")
        if sma20 is not None and latest_close > sma20 > sma50:
            trend_score = 0.75
            trend_label = "uptrend"
        elif sma20 is not None and latest_close < sma20 < sma50:
            trend_score = 0.25
            trend_label = "downtrend"
        else:
            trend_score = 0.5
            trend_label = "mixed"
    elif sma20 is not None and latest_close > sma20 > sma50 > sma200:
        trend_score = 1.0
        trend_label = "strong_uptrend"
    elif latest_close > sma50 > sma200:
        trend_score = 0.75
        trend_label = "uptrend"
    elif sma20 is not None and latest_close < sma20 < sma50 < sma200:
        trend_score = 0.0
        trend_label = "strong_downtrend"
    elif latest_close < sma50 < sma200:
        trend_score = 0.25
        trend_label = "downtrend"
    else:
        trend_score = 0.5
        trend_label = "mixed"

    return {
        "trend_score": trend_score,
        "trend_label": trend_label,
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            "latest_close": latest_close,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "validation": validation["calculation_basis"],
        },
    }


def calculate_volatility_regime(
    ohlcv: pd.DataFrame,
    atr_period: int = 14,
) -> VolatilityRegimeResult:
    """Classify volatility from ATR as a percentage of latest close."""
    validation = validate_ohlcv(ohlcv)
    data = validation["ohlcv"]
    atr_result = calculate_atr(ohlcv, period=atr_period)
    risk_flags = _merge_risk_flags(validation["risk_flags"], atr_result["risk_flags"])

    if data.empty or atr_result["atr"] is None:
        return {
            "volatility_regime": None,
            "volatility_pct": None,
            "atr": atr_result["atr"],
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_volatility_regime"]),
            "calculation_basis": {
                "atr_period": atr_period,
                "atr": atr_result["calculation_basis"],
                "validation": validation["calculation_basis"],
            },
        }

    latest_close = float(data["close"].iloc[-1])
    volatility_pct = atr_result["atr"] / latest_close
    if volatility_pct < 0.015:
        regime = "low"
    elif volatility_pct < 0.04:
        regime = "normal"
    elif volatility_pct < 0.08:
        regime = "high"
    else:
        regime = "extreme"
        risk_flags.append("extreme_volatility")

    return {
        "volatility_regime": regime,
        "volatility_pct": float(volatility_pct),
        "atr": atr_result["atr"],
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            "latest_close": latest_close,
            "thresholds": {
                "low_lt": 0.015,
                "normal_lt": 0.04,
                "high_lt": 0.08,
            },
            "atr": atr_result["calculation_basis"],
            "validation": validation["calculation_basis"],
        },
    }


def calculate_volume_score(ohlcv: pd.DataFrame, lookback: int = 20) -> VolumeScoreResult:
    """Score latest volume relative to prior average volume."""
    validation = validate_ohlcv(ohlcv)
    data = validation["ohlcv"]
    risk_flags = list(validation["risk_flags"])
    if data.empty or "volume" not in data.columns:
        return {
            "volume_score": None,
            "volume_label": "missing_volume",
            "volume_ratio": None,
            "risk_flags": _merge_risk_flags(risk_flags, ["missing_volume"]),
            "calculation_basis": {
                "lookback": lookback,
                "validation": validation["calculation_basis"],
            },
        }

    volume = pd.to_numeric(data["volume"], errors="coerce")
    latest_volume = _optional_float(volume.iloc[-1])
    history = volume.iloc[:-1].dropna().tail(max(1, int(lookback)))
    if latest_volume is None or latest_volume <= 0 or history.empty:
        return {
            "volume_score": None,
            "volume_label": "invalid_volume",
            "volume_ratio": None,
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_volume"]),
            "calculation_basis": {
                "lookback": lookback,
                "latest_volume": latest_volume,
                "history_count": len(history),
                "validation": validation["calculation_basis"],
            },
        }

    average_volume = float(history.mean())
    if average_volume <= 0:
        return {
            "volume_score": None,
            "volume_label": "invalid_volume",
            "volume_ratio": None,
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_volume"]),
            "calculation_basis": {
                "lookback": lookback,
                "latest_volume": latest_volume,
                "average_volume": average_volume,
                "validation": validation["calculation_basis"],
            },
        }

    if len(history) < lookback:
        risk_flags.append("short_volume_window")

    volume_ratio = latest_volume / average_volume
    if volume_ratio >= 1.5:
        score = 1.0
        label = "volume_spike"
        risk_flags.append("volume_spike")
    elif volume_ratio >= 0.8:
        score = 0.7
        label = "normal"
    elif volume_ratio >= 0.5:
        score = 0.45
        label = "below_average"
        risk_flags.append("weak_volume")
    else:
        score = 0.2
        label = "weak_volume"
        risk_flags.append("weak_volume")

    return {
        "volume_score": score,
        "volume_label": label,
        "volume_ratio": float(volume_ratio),
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            "lookback": lookback,
            "latest_volume": latest_volume,
            "average_volume": average_volume,
            "history_count": len(history),
            "validation": validation["calculation_basis"],
        },
    }


def detect_support_resistance(
    ohlcv: pd.DataFrame,
    lookback: int = 60,
) -> SupportResistanceResult:
    """Detect simple support and resistance from prior bars only."""
    validation = validate_ohlcv(ohlcv)
    data = validation["ohlcv"]
    risk_flags = list(validation["risk_flags"])
    lookback = max(1, int(lookback))

    history = data.iloc[:-1].tail(lookback) if len(data) > 1 else pd.DataFrame()
    if history.empty:
        return {
            "support": None,
            "resistance": None,
            "risk_flags": _merge_risk_flags(
                risk_flags,
                ["insufficient_support_resistance_window"],
            ),
            "calculation_basis": {
                "lookback": lookback,
                "used_latest_bar": False,
                "validation": validation["calculation_basis"],
            },
        }

    support = float(history["low"].min())
    resistance = float(history["high"].max())
    return {
        "support": support,
        "resistance": resistance,
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            "lookback": lookback,
            "history_rows": len(history),
            "used_latest_bar": False,
            "support_method": "prior_low_min",
            "resistance_method": "prior_high_max",
            "validation": validation["calculation_basis"],
        },
    }


def calculate_entry_zone(
    ohlcv: pd.DataFrame,
    strategy: str = "pullback_or_breakout",
    atr_period: int = 14,
    atr_zone_multiple: float = 0.5,
    support_resistance_lookback: int = 60,
) -> EntryZoneResult:
    """Calculate a current-price entry candidate and nearby entry zone."""
    validation = validate_ohlcv(ohlcv)
    data = validation["ohlcv"]
    atr_result = calculate_atr(ohlcv, period=atr_period)
    sr_result = detect_support_resistance(ohlcv, lookback=support_resistance_lookback)
    risk_flags = _merge_risk_flags(
        validation["risk_flags"],
        atr_result["risk_flags"],
        sr_result["risk_flags"],
    )

    if data.empty:
        return {
            "entry_price": None,
            "entry_zone_low": None,
            "entry_zone_high": None,
            "price_location": "invalid",
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_entry_price"]),
            "calculation_basis": {
                "strategy": strategy,
                "validation": validation["calculation_basis"],
            },
        }

    entry_price = float(data["close"].iloc[-1])
    if entry_price <= 0:
        return {
            "entry_price": None,
            "entry_zone_low": None,
            "entry_zone_high": None,
            "price_location": "invalid",
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_entry_price"]),
            "calculation_basis": {
                "strategy": strategy,
                "latest_close": entry_price,
                "validation": validation["calculation_basis"],
            },
        }

    atr = atr_result["atr"]
    support = sr_result["support"]
    resistance = sr_result["resistance"]
    zone_width = atr * atr_zone_multiple if atr is not None and atr > 0 else entry_price * 0.01
    entry_zone_low = entry_price - zone_width
    if support is not None and support < entry_price:
        entry_zone_low = max(entry_zone_low, support)
    entry_zone_high = entry_price

    price_location = "neutral"
    if resistance is not None and entry_price >= resistance * 0.98:
        price_location = "near_resistance"
        risk_flags.append("near_resistance")
    elif support is not None and entry_price <= support * 1.02:
        price_location = "near_support"

    return {
        "entry_price": entry_price,
        "entry_zone_low": float(entry_zone_low),
        "entry_zone_high": float(entry_zone_high),
        "price_location": price_location,
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            "strategy": strategy,
            "latest_close": entry_price,
            "atr_zone_multiple": atr_zone_multiple,
            "zone_width": float(zone_width),
            "atr": atr_result["calculation_basis"],
            "support_resistance": sr_result["calculation_basis"],
            "validation": validation["calculation_basis"],
        },
    }


def calculate_stop_loss(
    entry_price: float,
    atr: Optional[float],
    support: Optional[float] = None,
    atr_multiple: float = 1.5,
    support_buffer_pct: float = 0.005,
    max_trade_risk_pct: float = 0.12,
) -> StopLossResult:
    """Calculate a long-only stop below entry from ATR/support candidates."""
    risk_flags: RiskFlags = []
    entry = _optional_float(entry_price)
    atr_value = _optional_float(atr)
    support_value = _optional_float(support)
    calculation_basis: CalculationBasis = {
        "atr_multiple": atr_multiple,
        "support_buffer_pct": support_buffer_pct,
        "max_trade_risk_pct": max_trade_risk_pct,
    }

    if entry is None or entry <= 0:
        return {
            "stop_loss": None,
            "trade_risk_pct": None,
            "risk_flags": ["invalid_entry_price", "invalid_stop_loss"],
            "calculation_basis": {
                **calculation_basis,
                "selected_stop_method": None,
            },
        }

    candidates: Dict[str, float] = {}
    if atr_value is not None and atr_value > 0:
        candidates["atr_stop"] = entry - atr_value * atr_multiple
    if support_value is not None and 0 < support_value < entry:
        candidates["support_stop"] = support_value * (1.0 - support_buffer_pct)

    valid_candidates = {
        method: price
        for method, price in candidates.items()
        if price > 0 and price < entry
    }
    calculation_basis.update(
        {
            "entry_price": entry,
            "atr": atr_value,
            "support": support_value,
            "stop_candidates": candidates,
        }
    )

    if not valid_candidates:
        return {
            "stop_loss": None,
            "trade_risk_pct": None,
            "risk_flags": ["invalid_stop_loss"],
            "calculation_basis": {
                **calculation_basis,
                "selected_stop_method": None,
            },
        }

    selected_stop_method, stop_loss = min(
        valid_candidates.items(),
        key=lambda item: item[1],
    )
    trade_risk_pct = (entry - stop_loss) / entry
    if stop_loss >= entry:
        risk_flags.append("invalid_stop_loss")
        stop_loss = None
        trade_risk_pct = None
    elif trade_risk_pct > max_trade_risk_pct:
        risk_flags.append("wide_stop_loss")

    return {
        "stop_loss": None if stop_loss is None else float(stop_loss),
        "trade_risk_pct": None if trade_risk_pct is None else float(trade_risk_pct),
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            **calculation_basis,
            "selected_stop_method": selected_stop_method,
            "trade_risk_pct": trade_risk_pct,
        },
    }


def calculate_take_profit(
    entry_price: float,
    stop_loss: Optional[float],
    resistance: Optional[float] = None,
    target_rr: float = 2.0,
) -> TakeProfitResult:
    """Calculate a long-only target above entry, optionally capped by resistance."""
    risk_flags: RiskFlags = []
    entry = _optional_float(entry_price)
    stop = _optional_float(stop_loss)
    resistance_value = _optional_float(resistance)
    calculation_basis: CalculationBasis = {
        "target_rr": target_rr,
        "entry_price": entry,
        "stop_loss": stop,
        "resistance": resistance_value,
    }

    if entry is None or entry <= 0:
        return {
            "take_profit": None,
            "risk_flags": ["invalid_entry_price", "invalid_take_profit"],
            "calculation_basis": {
                **calculation_basis,
                "selected_target_method": None,
            },
        }
    if stop is None or stop >= entry:
        return {
            "take_profit": None,
            "risk_flags": ["invalid_stop_loss", "invalid_take_profit"],
            "calculation_basis": {
                **calculation_basis,
                "selected_target_method": None,
            },
        }

    risk = entry - stop
    base_target = entry + risk * target_rr
    selected_target_method = "risk_reward_target"
    take_profit = base_target
    if resistance_value is not None and resistance_value > entry and resistance_value < base_target:
        take_profit = resistance_value
        selected_target_method = "resistance_cap"
        risk_flags.append("resistance_caps_target")

    if take_profit <= entry:
        return {
            "take_profit": None,
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_take_profit"]),
            "calculation_basis": {
                **calculation_basis,
                "risk": risk,
                "base_target": base_target,
                "selected_target_method": selected_target_method,
            },
        }

    return {
        "take_profit": float(take_profit),
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            **calculation_basis,
            "risk": risk,
            "base_target": base_target,
            "selected_target_method": selected_target_method,
        },
    }


def calculate_risk_reward(
    entry_price: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
) -> RiskRewardResult:
    """Calculate reward divided by risk for a long-only setup."""
    entry = _optional_float(entry_price)
    stop = _optional_float(stop_loss)
    target = _optional_float(take_profit)
    risk = None
    reward = None
    risk_flags: RiskFlags = []

    if entry is None or entry <= 0:
        risk_flags.append("invalid_entry_price")
    if stop is None or entry is None or stop >= entry:
        risk_flags.append("invalid_stop_loss")
    if target is None or entry is None or target <= entry:
        risk_flags.append("invalid_take_profit")

    if not risk_flags:
        risk = entry - stop
        reward = target - entry
        if risk <= 0 or reward <= 0:
            risk_flags.append("invalid_risk_reward")

    if risk_flags:
        return {
            "risk_reward_ratio": None,
            "risk": risk,
            "reward": reward,
            "risk_flags": _merge_risk_flags(risk_flags, ["invalid_risk_reward"]),
            "calculation_basis": {
                "entry_price": entry,
                "stop_loss": stop,
                "take_profit": target,
                "formula": "reward / risk",
                "risk": risk,
                "reward": reward,
            },
        }

    assert risk is not None
    assert reward is not None
    return {
        "risk_reward_ratio": float(reward / risk),
        "risk": float(risk),
        "reward": float(reward),
        "risk_flags": [],
        "calculation_basis": {
            "entry_price": entry,
            "stop_loss": stop,
            "take_profit": target,
            "formula": "reward / risk",
            "risk": risk,
            "reward": reward,
        },
    }


def calculate_position_size_pct(
    entry_price: float,
    stop_loss: Optional[float],
    account_risk_pct: float = 0.01,
    max_position_pct: float = 0.15,
    max_trade_risk_pct: float = 0.12,
) -> PositionSizeResult:
    """Calculate position size from account risk and stop distance only."""
    entry = _optional_float(entry_price)
    stop = _optional_float(stop_loss)
    calculation_basis: CalculationBasis = {
        "entry_price": entry,
        "stop_loss": stop,
        "account_risk_pct": account_risk_pct,
        "max_position_pct": max_position_pct,
        "max_trade_risk_pct": max_trade_risk_pct,
        "formula": "account_risk_pct / trade_risk_pct",
    }

    if entry is None or entry <= 0 or stop is None or stop >= entry:
        return {
            "position_size_pct": None,
            "trade_risk_pct": None,
            "risk_flags": ["invalid_position_risk"],
            "calculation_basis": calculation_basis,
        }

    trade_risk_pct = (entry - stop) / entry
    if trade_risk_pct <= 0:
        return {
            "position_size_pct": None,
            "trade_risk_pct": None,
            "risk_flags": ["invalid_position_risk"],
            "calculation_basis": {
                **calculation_basis,
                "trade_risk_pct": trade_risk_pct,
            },
        }

    raw_position_pct = account_risk_pct / trade_risk_pct
    position_size_pct = min(raw_position_pct, max_position_pct)
    risk_flags: RiskFlags = []
    if trade_risk_pct > max_trade_risk_pct:
        risk_flags.append("wide_stop_loss")

    return {
        "position_size_pct": float(position_size_pct),
        "trade_risk_pct": float(trade_risk_pct),
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            **calculation_basis,
            "trade_risk_pct": trade_risk_pct,
            "raw_position_pct": raw_position_pct,
        },
    }


def evaluate_price_attractiveness(
    ohlcv: pd.DataFrame,
    entry_price: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    min_acceptable_rr: float = 1.2,
) -> PriceAttractivenessResult:
    """Score price setup quality without producing a trading action."""
    trend = calculate_trend_score(ohlcv)
    volatility = calculate_volatility_regime(ohlcv)
    volume = calculate_volume_score(ohlcv)
    sr = detect_support_resistance(ohlcv)
    rr = calculate_risk_reward(entry_price, stop_loss, take_profit)

    risk_flags = _merge_risk_flags(
        trend["risk_flags"],
        volatility["risk_flags"],
        volume["risk_flags"],
        sr["risk_flags"],
        rr["risk_flags"],
    )
    score = 0.5

    if trend["trend_score"] is not None:
        score += (trend["trend_score"] - 0.5) * 0.3

    volatility_regime = volatility["volatility_regime"]
    if volatility_regime == "extreme":
        score -= 0.25
        risk_flags.append("extreme_volatility")
    elif volatility_regime == "high":
        score -= 0.1
    elif volatility_regime == "low":
        score += 0.05

    if volume["volume_score"] is not None:
        score += (volume["volume_score"] - 0.5) * 0.2
    elif "missing_volume" in volume["risk_flags"]:
        score -= 0.05

    risk_reward_ratio = rr["risk_reward_ratio"]
    if risk_reward_ratio is None:
        score -= 0.25
    elif risk_reward_ratio < min_acceptable_rr:
        score -= 0.3
        risk_flags.append("poor_risk_reward")
    elif risk_reward_ratio >= 2.0:
        score += 0.2
    elif risk_reward_ratio >= 1.5:
        score += 0.1

    entry = _optional_float(entry_price)
    support = sr["support"]
    resistance = sr["resistance"]
    price_location = "neutral"
    if entry is not None and resistance is not None and entry >= resistance * 0.98:
        price_location = "near_resistance"
        score -= 0.2
        risk_flags.append("near_resistance")
    elif entry is not None and support is not None and entry <= support * 1.02:
        price_location = "near_support"
        score += 0.05

    return {
        "price_attractiveness_score": float(_clamp(score)),
        "risk_reward_ratio": risk_reward_ratio,
        "price_location": price_location,
        "risk_flags": _merge_risk_flags(risk_flags),
        "calculation_basis": {
            "min_acceptable_rr": min_acceptable_rr,
            "trend": trend["calculation_basis"],
            "volatility": volatility["calculation_basis"],
            "volume": volume["calculation_basis"],
            "support_resistance": sr["calculation_basis"],
            "risk_reward": rr["calculation_basis"],
        },
    }


def evaluate_price_setup(
    ohlcv: pd.DataFrame,
    atr_period: int = 14,
    support_resistance_lookback: int = 60,
    target_rr: float = 2.0,
    account_risk_pct: float = 0.01,
    max_position_pct: float = 0.15,
) -> PriceSetupResult:
    """Calculate price setup levels and scores without issuing an action."""
    validation = validate_ohlcv(ohlcv)
    data = validation["ohlcv"]
    atr = calculate_atr(ohlcv, period=atr_period)
    trend = calculate_trend_score(ohlcv)
    volatility = calculate_volatility_regime(ohlcv, atr_period=atr_period)
    volume = calculate_volume_score(ohlcv)
    sr = detect_support_resistance(ohlcv, lookback=support_resistance_lookback)
    entry = calculate_entry_zone(
        ohlcv,
        atr_period=atr_period,
        support_resistance_lookback=support_resistance_lookback,
    )
    stop = calculate_stop_loss(
        entry["entry_price"],
        atr["atr"],
        support=sr["support"],
    )
    target = calculate_take_profit(
        entry["entry_price"],
        stop["stop_loss"],
        resistance=sr["resistance"],
        target_rr=target_rr,
    )
    rr = calculate_risk_reward(
        entry["entry_price"],
        stop["stop_loss"],
        target["take_profit"],
    )
    position_size = calculate_position_size_pct(
        entry["entry_price"],
        stop["stop_loss"],
        account_risk_pct=account_risk_pct,
        max_position_pct=max_position_pct,
    )
    attractiveness = evaluate_price_attractiveness(
        ohlcv,
        entry["entry_price"],
        stop["stop_loss"],
        target["take_profit"],
    )

    current_price = float(data["close"].iloc[-1]) if not data.empty else None
    risk_flags = _merge_risk_flags(
        validation["risk_flags"],
        atr["risk_flags"],
        trend["risk_flags"],
        volatility["risk_flags"],
        volume["risk_flags"],
        sr["risk_flags"],
        entry["risk_flags"],
        stop["risk_flags"],
        target["risk_flags"],
        rr["risk_flags"],
        position_size["risk_flags"],
        attractiveness["risk_flags"],
    )

    return {
        "current_price": current_price,
        "entry_price": entry["entry_price"],
        "entry_zone_low": entry["entry_zone_low"],
        "entry_zone_high": entry["entry_zone_high"],
        "stop_loss": stop["stop_loss"],
        "take_profit": target["take_profit"],
        "risk_reward_ratio": rr["risk_reward_ratio"],
        "position_size_pct": position_size["position_size_pct"],
        "levels": {
            "support": sr["support"],
            "resistance": sr["resistance"],
            "stop_loss": stop["stop_loss"],
            "take_profit": target["take_profit"],
        },
        "scores": {
            "trend_score": trend["trend_score"],
            "volume_score": volume["volume_score"],
            "price_attractiveness_score": attractiveness["price_attractiveness_score"],
        },
        "regimes": {
            "trend_label": trend["trend_label"],
            "volatility_regime": volatility["volatility_regime"],
        },
        "risk_flags": risk_flags,
        "calculation_basis": {
            "validation": validation["calculation_basis"],
            "atr": atr["calculation_basis"],
            "trend": trend["calculation_basis"],
            "volatility": volatility["calculation_basis"],
            "volume": volume["calculation_basis"],
            "support_resistance": sr["calculation_basis"],
            "entry_zone": entry["calculation_basis"],
            "stop_loss": stop["calculation_basis"],
            "take_profit": target["calculation_basis"],
            "risk_reward": rr["calculation_basis"],
            "position_size": position_size["calculation_basis"],
            "price_attractiveness": attractiveness["calculation_basis"],
        },
    }
