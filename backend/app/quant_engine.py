import json
import re
import logging
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ParsedTradeSignal(BaseModel):
    """Backtest-ready structured signal with prose parsing kept as fallback."""

    ticker: str
    date: str
    side: str = "HOLD"
    confidence: float = 0.5
    horizon_days: int = 5
    price_target: Optional[float] = None
    current_price: Optional[float] = None
    entry_price: Optional[float] = None
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    position_size_pct: Optional[float] = None
    signal_quality_score: Optional[float] = None
    trend_score: Optional[float] = None
    volatility_score: Optional[float] = None
    volume_score: Optional[float] = None
    price_attractiveness_score: Optional[float] = None
    data_quality_score: Optional[float] = None
    market_regime: Optional[str] = None
    volatility_regime: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    calculation_basis: Dict[str, Any] = Field(default_factory=dict)
    source: str = "free_text"


class SignalExtractor:
    """Helper to extract standardized signals from prose reports or PortfolioDecision objects."""

    VALID_SIDES = {
        "STRONG BUY",
        "BUY",
        "OVERWEIGHT",
        "HOLD",
        "WAIT",
        "WAIT_FOR_PULLBACK",
        "UNDERWEIGHT",
        "SELL",
    }

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(parsed):
            return None
        return parsed

    @staticmethod
    def _coerce_int(value: Any, default: int = 5) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(1, parsed)

    @staticmethod
    def _coerce_str_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]
        return [str(value)]

    @staticmethod
    def _coerce_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @classmethod
    def _normalize_side(cls, value: Any, default: str = "HOLD") -> str:
        if value is None:
            return default
        side = str(value).strip().replace("-", "_").upper()
        side = re.sub(r"\s+", " ", side)
        if side in cls.VALID_SIDES:
            return side
        spaced_side = side.replace("_", " ")
        if spaced_side in cls.VALID_SIDES:
            return spaced_side
        if spaced_side == "WAIT FOR PULLBACK":
            return "WAIT_FOR_PULLBACK"
        return default

    @staticmethod
    def _structured_payload(value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        payload = value
        if hasattr(value, "model_dump"):
            try:
                payload = value.model_dump(mode="json")
            except TypeError:
                payload = value.model_dump()
        if isinstance(value, str):
            try:
                payload = json.loads(value)
            except (TypeError, ValueError):
                return None
        if not isinstance(payload, dict):
            return None
        for key in ("trade_signal", "parsed_trade_signal", "signal"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested
        if any(k in payload for k in ("action", "side", "rating", "entry_price", "stop_loss", "take_profit")):
            return payload
        return None

    @classmethod
    def parse_structured_signal(
        cls,
        ticker: str,
        date: str,
        payload: Any,
        fallback_text: str = "",
        fallback_side: str = "HOLD",
        fallback_confidence: float = 0.5,
        fallback_horizon_days: int = 5,
        fallback_price_target: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Normalize a structured TradeSignal-like payload for backtesting."""
        data = cls._structured_payload(payload)
        if data is None:
            return None

        side = cls._normalize_side(
            data.get("side") or data.get("action") or data.get("rating"),
            default=fallback_side,
        )
        confidence = cls._coerce_float(data.get("confidence"))
        if confidence is None:
            confidence = fallback_confidence
        confidence = min(1.0, max(0.0, confidence))

        horizon_value = data.get("horizon_days") or data.get("expected_holding_days")
        if horizon_value is None and data.get("time_horizon"):
            horizon_value = cls.extract_horizon_days(str(data.get("time_horizon")))
        horizon_days = cls._coerce_int(horizon_value, default=fallback_horizon_days)
        take_profit = cls._coerce_float(data.get("take_profit"))
        price_target = cls._coerce_float(data.get("price_target"))
        if price_target is None:
            price_target = take_profit if take_profit is not None else cls._coerce_float(fallback_price_target)

        signal = ParsedTradeSignal(
            ticker=str(data.get("ticker") or ticker).upper(),
            date=str(data.get("date") or data.get("as_of_date") or date),
            side=side,
            confidence=confidence,
            horizon_days=horizon_days,
            price_target=price_target,
            current_price=cls._coerce_float(data.get("current_price")),
            entry_price=cls._coerce_float(data.get("entry_price")),
            entry_zone_low=cls._coerce_float(data.get("entry_zone_low")),
            entry_zone_high=cls._coerce_float(data.get("entry_zone_high")),
            stop_loss=cls._coerce_float(data.get("stop_loss")),
            take_profit=take_profit,
            trailing_stop_pct=cls._coerce_float(data.get("trailing_stop_pct")),
            risk_reward_ratio=cls._coerce_float(data.get("risk_reward_ratio")),
            position_size_pct=cls._coerce_float(data.get("position_size_pct")),
            signal_quality_score=cls._coerce_float(data.get("signal_quality_score")),
            trend_score=cls._coerce_float(data.get("trend_score")),
            volatility_score=cls._coerce_float(data.get("volatility_score")),
            volume_score=cls._coerce_float(data.get("volume_score")),
            price_attractiveness_score=cls._coerce_float(data.get("price_attractiveness_score")),
            data_quality_score=cls._coerce_float(data.get("data_quality_score")),
            market_regime=str(data.get("market_regime")) if data.get("market_regime") is not None else None,
            volatility_regime=str(data.get("volatility_regime")) if data.get("volatility_regime") is not None else None,
            evidence=cls._coerce_str_list(data.get("evidence")),
            risk_flags=cls._coerce_str_list(data.get("risk_flags")),
            calculation_basis=cls._coerce_dict(data.get("calculation_basis")),
            source="structured",
        )
        return signal.model_dump()

    @classmethod
    def parse_stored_decision_to_signal(
        cls,
        ticker: str,
        date: str,
        side: str,
        confidence: float,
        horizon_days: int,
        price_target: Optional[float],
        raw_json: Any = None,
    ) -> Dict[str, Any]:
        """Build a signal from DB columns, preferring structured raw_json when available."""
        fallback_confidence = cls._coerce_float(confidence)
        if fallback_confidence is None:
            fallback_confidence = 0.5
        fallback = ParsedTradeSignal(
            ticker=ticker.upper(),
            date=date,
            side=cls._normalize_side(side),
            confidence=min(1.0, max(0.0, fallback_confidence)),
            horizon_days=cls._coerce_int(horizon_days),
            price_target=cls._coerce_float(price_target),
            source="db_columns",
        ).model_dump()
        structured = cls.parse_structured_signal(
            ticker=ticker,
            date=date,
            payload=raw_json,
            fallback_side=fallback["side"],
            fallback_confidence=fallback["confidence"],
            fallback_horizon_days=fallback["horizon_days"],
            fallback_price_target=fallback["price_target"],
        )
        return structured or fallback

    @staticmethod
    def parse_recommendation(decision_text: str) -> str:
        """Parse final decision text to extract BUY, STRONG BUY, OVERWEIGHT, SELL, UNDERWEIGHT, or HOLD."""
        if not decision_text:
            return "HOLD"
        
        text_upper = decision_text.upper()
        
        # 1. STRONG BUY / 강력 매수
        if "STRONG BUY" in text_upper or "강력 매수" in text_upper or "강력매수" in text_upper:
            return "STRONG BUY"
            
        # 2. OVERWEIGHT / 비중 확대 / 매수 대기
        elif "OVERWEIGHT" in text_upper or "비중확대" in text_upper or "비중 확대" in text_upper or "매수 대기" in text_upper or "매수대기" in text_upper:
            return "OVERWEIGHT"
            
        # 3. UNDERWEIGHT / 비중 축소
        elif "UNDERWEIGHT" in text_upper or "비중축소" in text_upper or "비중 축소" in text_upper:
            return "UNDERWEIGHT"
            
        # 4. SELL / 매도
        elif "SELL" in text_upper or "매도" in text_upper or "추천: 매도" in text_upper or "청산" in text_upper:
            return "SELL"
            
        # 5. BUY / 매수 / 추천: 매수 (OVERWEIGHT/STRONG BUY가 아닌 일반 매수)
        elif "BUY" in text_upper or "매수" in text_upper or "추천: 매수" in text_upper or "매입" in text_upper or "구매" in text_upper:
            return "BUY"
            
        return "HOLD"

    @staticmethod
    def extract_confidence(decision_text: str, side: str) -> float:
        """Extract or infer confidence score (0.0 to 1.0) from decision text."""
        if not decision_text:
            return 0.5
        
        # Regex search for confidence patterns
        confidence_match = re.search(
            r"(?:confidence|신뢰도|확신도|확신)\s*:\s*(\d+(?:\.\d+)?)%?", 
            decision_text, 
            re.IGNORECASE
        )
        if confidence_match:
            try:
                val = float(confidence_match.group(1))
                if val > 1.0:
                    val = val / 100.0
                return min(1.0, max(0.0, val))
            except ValueError:
                pass
                
        # Fallback values if not explicitly found
        text_upper = decision_text.upper()
        if "BUY" in text_upper or "매수" in text_upper:
            if "STRONG" in text_upper or "강력" in text_upper:
                return 0.90
            return 0.80
        elif "SELL" in text_upper or "매도" in text_upper:
            if "STRONG" in text_upper or "강력" in text_upper:
                return 0.90
            return 0.80
        elif "OVERWEIGHT" in text_upper or "UNDERWEIGHT" in text_upper:
            return 0.65
        
        return 0.50

    @staticmethod
    def extract_horizon_days(decision_text: str) -> int:
        """Extract holding horizon period in trading days (default 5)."""
        if not decision_text:
            return 5
            
        # Check for typical patterns in decision text
        horizon_match = re.search(
            r"(?:time horizon|horizon|기간|투자 기간)\s*:\s*(.*?)(?:\n|\Z)", 
            decision_text, 
            re.IGNORECASE
        )
        target_str = horizon_match.group(1) if horizon_match else decision_text
        
        # Parse patterns like "5 days", "1 week", "3 months", "30일"
        days_match = re.search(r"(\d+)\s*(?:day|일)", target_str, re.IGNORECASE)
        if days_match:
            return int(days_match.group(1))
            
        weeks_match = re.search(r"(\d+)\s*(?:week|주)", target_str, re.IGNORECASE)
        if weeks_match:
            return int(weeks_match.group(1)) * 5
            
        months_match = re.search(r"(\d+)\s*(?:month|달|개월)", target_str, re.IGNORECASE)
        if months_match:
            return int(months_match.group(1)) * 21
            
        return 5 # Default fallback

    @staticmethod
    def extract_price_target(decision_text: str) -> Optional[float]:
        """Extract price target from the decision text if present."""
        if not decision_text:
            return None
        target_match = re.search(
            r"(?:price target|target|목표가|목표 가격)[*\s]*:\s*(?:\$)?\s*([0-9,]+(?:\.[0-9]+)?)",
            decision_text,
            re.IGNORECASE
        )
        if target_match:
            try:
                cleaned = target_match.group(1).replace(",", "")
                return float(cleaned)
            except ValueError:
                pass
        return None

    @classmethod
    def parse_decision_to_signal(cls, ticker: str, date: str, decision_text: str) -> Dict[str, Any]:
        """Parse a raw decision text into standard signal dictionary."""
        if isinstance(decision_text, str):
            text = decision_text
        else:
            try:
                text = json.dumps(decision_text, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                text = str(decision_text)

        structured = cls.parse_structured_signal(
            ticker=ticker,
            date=date,
            payload=decision_text,
            fallback_text=text,
        )
        if structured is not None:
            return structured

        side = cls.parse_recommendation(text)
        confidence = cls.extract_confidence(text, side)
        horizon_days = cls.extract_horizon_days(text)
        price_target = cls.extract_price_target(text)
        
        return ParsedTradeSignal(
            ticker=ticker.upper(),
            date=date,
            side=side,
            confidence=confidence,
            horizon_days=horizon_days,
            price_target=price_target,
            source="free_text",
        ).model_dump()

    @staticmethod
    def _merge_unique(*groups: Any) -> List[str]:
        merged: List[str] = []
        for group in groups:
            if not group:
                continue
            if isinstance(group, str):
                group = [group]
            for item in group:
                value = str(item)
                if value not in merged:
                    merged.append(value)
        return merged

    @classmethod
    def enrich_with_price_setup(
        cls,
        signal: Dict[str, Any],
        price_setup: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Overlay deterministic OHLCV price setup fields onto an AI signal."""
        enriched = dict(signal)
        scores = price_setup.get("scores") or {}
        regimes = price_setup.get("regimes") or {}
        calculation_basis = cls._coerce_dict(enriched.get("calculation_basis"))

        enriched.update(
            {
                "current_price": price_setup.get("current_price"),
                "entry_price": price_setup.get("entry_price"),
                "entry_zone_low": price_setup.get("entry_zone_low"),
                "entry_zone_high": price_setup.get("entry_zone_high"),
                "stop_loss": price_setup.get("stop_loss"),
                "take_profit": price_setup.get("take_profit"),
                "price_target": price_setup.get("take_profit") or enriched.get("price_target"),
                "risk_reward_ratio": price_setup.get("risk_reward_ratio"),
                "position_size_pct": price_setup.get("position_size_pct"),
                "trend_score": scores.get("trend_score"),
                "volume_score": scores.get("volume_score"),
                "price_attractiveness_score": scores.get("price_attractiveness_score"),
                "volatility_regime": regimes.get("volatility_regime"),
            }
        )

        data_quality_flags = [
            flag
            for flag in price_setup.get("risk_flags", [])
            if flag.startswith("missing_")
            or flag.startswith("invalid_")
            or flag.startswith("insufficient_")
            or flag in {"rows_with_missing_price", "non_positive_price", "high_below_low"}
        ]
        if "missing_ohlcv" in data_quality_flags or "missing_required_columns" in data_quality_flags:
            data_quality_score = 0.0
        else:
            data_quality_score = max(0.0, 1.0 - 0.15 * len(data_quality_flags))
        enriched["data_quality_score"] = data_quality_score

        enriched["risk_flags"] = cls._merge_unique(
            enriched.get("risk_flags"),
            price_setup.get("risk_flags"),
        )
        enriched["calculation_basis"] = {
            **calculation_basis,
            "quant_price_setup": price_setup.get("calculation_basis", {}),
            "deterministic_price_fields": [
                "entry_price",
                "stop_loss",
                "take_profit",
                "risk_reward_ratio",
                "position_size_pct",
            ],
        }
        return enriched

    @classmethod
    def apply_signal_gate(
        cls,
        signal: Dict[str, Any],
        min_risk_reward: float = 1.2,
        min_data_quality_score: float = 0.7,
        min_price_attractiveness_score: float = 0.35,
        min_volume_score: float = 0.3,
    ) -> Dict[str, Any]:
        """Apply deterministic risk gates without relying on LLM price claims."""
        gated = dict(signal)
        original_side = cls._normalize_side(gated.get("side"))
        buy_like = {"STRONG BUY", "BUY", "OVERWEIGHT"}
        risk_flags = cls._merge_unique(gated.get("risk_flags"))
        calculation_basis = cls._coerce_dict(gated.get("calculation_basis"))
        gate_reasons: List[str] = []
        gated_side = original_side

        if original_side in buy_like:
            data_quality = cls._coerce_float(gated.get("data_quality_score"))
            risk_reward = cls._coerce_float(gated.get("risk_reward_ratio"))
            price_score = cls._coerce_float(gated.get("price_attractiveness_score"))
            volume_score = cls._coerce_float(gated.get("volume_score"))
            volatility_regime = gated.get("volatility_regime")
            stop_loss = cls._coerce_float(gated.get("stop_loss"))
            take_profit = cls._coerce_float(gated.get("take_profit"))

            if data_quality is not None and data_quality < min_data_quality_score:
                gated_side = "HOLD"
                gate_reasons.append("signal_gate_data_quality_failed")
            elif (
                stop_loss is None
                or take_profit is None
                or "invalid_stop_loss" in risk_flags
                or "invalid_take_profit" in risk_flags
            ):
                gated_side = "HOLD"
                gate_reasons.append("signal_gate_missing_valid_levels")
            elif risk_reward is None:
                gated_side = "HOLD"
                gate_reasons.append("signal_gate_missing_risk_reward")
            elif risk_reward < min_risk_reward:
                gated_side = "WAIT"
                gate_reasons.append("signal_gate_poor_risk_reward")
            elif "near_resistance" in risk_flags or (
                price_score is not None and price_score < min_price_attractiveness_score
            ):
                gated_side = "WAIT_FOR_PULLBACK"
                gate_reasons.append("signal_gate_price_unattractive")
            elif volatility_regime == "extreme":
                gated_side = "WAIT"
                gate_reasons.append("signal_gate_extreme_volatility")
            elif volume_score is not None and volume_score < min_volume_score:
                gated_side = "WAIT"
                gate_reasons.append("signal_gate_weak_volume")
        else:
            gate_reasons.append("signal_gate_not_buy_candidate")

        gated["side"] = gated_side
        gated["risk_flags"] = cls._merge_unique(risk_flags, gate_reasons)
        gated["calculation_basis"] = {
            **calculation_basis,
            "signal_gate": {
                "original_side": original_side,
                "gated_side": gated_side,
                "min_risk_reward": min_risk_reward,
                "min_data_quality_score": min_data_quality_score,
                "min_price_attractiveness_score": min_price_attractiveness_score,
                "min_volume_score": min_volume_score,
                "reasons": gate_reasons,
            },
        }
        return gated


class BacktestEngine:
    """Quantitative backtesting engine using vectorized pandas operations."""

    @staticmethod
    def fetch_price_history(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Download closing price data for all tickers and benchmark in date range."""
        if not tickers:
            return pd.DataFrame()
            
        # Buffer dates to ensure full coverage
        start_dt = (datetime.datetime.strptime(start_date, "%Y-%m-%d") - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
        end_dt = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=10)).strftime("%Y-%m-%d")
        
        try:
            # Download close prices
            data = yf.download(tickers, start=start_dt, end=end_dt, auto_adjust=True, progress=False)
            if data.empty:
                return pd.DataFrame()
                
            # Keep only closing price
            if isinstance(data.columns, pd.MultiIndex):
                df = data["Close"]
            else:
                df = pd.DataFrame({tickers[0]: data["Close"]})
                
            # Forward-fill only. Backfilling would leak future prices into
            # earlier dates and can create invalid pre-listing trades.
            df = df.ffill()
            return df
        except Exception as e:
            logger.error(f"Error downloading prices for backtest: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def fetch_ohlc_history(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Download OHLC price data for stop-loss and take-profit simulation."""
        if not tickers:
            return pd.DataFrame()

        start_dt = (datetime.datetime.strptime(start_date, "%Y-%m-%d") - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
        end_dt = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=10)).strftime("%Y-%m-%d")
        fields = ["Open", "High", "Low", "Close"]

        try:
            data = yf.download(tickers, start=start_dt, end=end_dt, auto_adjust=True, progress=False)
            if data.empty:
                return pd.DataFrame()

            if isinstance(data.columns, pd.MultiIndex):
                available_fields = [f for f in fields if f in data.columns.get_level_values(0)]
                return data[available_fields].ffill() if available_fields else pd.DataFrame()

            ticker = tickers[0]
            frames = {
                field: pd.DataFrame({ticker: data[field]})
                for field in fields
                if field in data.columns
            }
            if not frames:
                return pd.DataFrame()
            ohlc = pd.concat(frames, axis=1)
            return ohlc.ffill()
        except Exception as e:
            logger.error(f"Error downloading OHLC prices for backtest: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(parsed):
            return None
        return parsed

    @staticmethod
    def _get_ohlc_value(ohlc_df: pd.DataFrame, dt: pd.Timestamp, ticker: str, field: str) -> Optional[float]:
        if ohlc_df is None or ohlc_df.empty:
            return None
        try:
            if isinstance(ohlc_df.columns, pd.MultiIndex):
                if (field, ticker) in ohlc_df.columns:
                    value = ohlc_df.loc[dt, (field, ticker)]
                elif (ticker, field) in ohlc_df.columns:
                    value = ohlc_df.loc[dt, (ticker, field)]
                else:
                    return None
            elif field in ohlc_df.columns:
                value = ohlc_df.loc[dt, field]
            else:
                return None
            value = float(value)
            return None if pd.isna(value) else value
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _close_position_trade(
        pos: Dict[str, Any],
        dt: pd.Timestamp,
        dt_str: str,
        exit_price: float,
        exit_reason: str,
        prices_df: pd.DataFrame,
        benchmark: str,
        slippage: float,
    ) -> Tuple[float, Dict[str, Any]]:
        """Close a long position and return cash proceeds plus a trade record."""
        final_exit_price = exit_price * (1.0 - slippage)
        exit_value = pos["shares"] * final_exit_price
        raw_return = (final_exit_price - pos["entry_price"]) / pos["entry_price"]

        bench_start_price = float(prices_df.loc[pos["entry_date"], benchmark])
        bench_end_price = float(prices_df.loc[dt, benchmark])
        bench_return = (bench_end_price - bench_start_price) / bench_start_price
        alpha_return = raw_return - bench_return
        profit = exit_value - pos["entry_size"]

        trade = {
            "ticker": pos["ticker"],
            "entry_date": pos["entry_date"],
            "entry_price": round(pos["entry_price"], 2),
            "exit_date": dt_str,
            "exit_price": round(exit_price, 2),
            "side": pos["side"],
            "confidence": pos["confidence"],
            "horizon_days": pos["horizon_days"],
            "exit_reason": exit_reason,
            "stop_loss": pos.get("stop_loss"),
            "take_profit": pos.get("take_profit"),
            "trailing_stop_pct": pos.get("trailing_stop_pct"),
            "signal_date": pos.get("signal_date"),
            "signal_risk_flags": pos.get("signal_risk_flags", []),
            "signal_calculation_basis": pos.get("signal_calculation_basis", {}),
            "raw_return": round(raw_return, 4),
            "alpha_return": round(alpha_return, 4),
            "profit": round(profit, 2),
            "size": round(pos["entry_size"], 2),
        }
        return exit_value, trade

    @classmethod
    def run_portfolio_backtest(
        cls, 
        signals: List[Dict[str, Any]], 
        start_date: str, 
        end_date: str, 
        initial_capital: float = 100000.0, 
        sizing_mode: str = "confidence",
        slippage: float = 0.0005
    ) -> Dict[str, Any]:
        """Run a chronological multi-ticker portfolio backtest.
        
        Schedules signals, tracks open positions, manages cash, 
        and calculates equity curve and detailed trade performance.
        """
        if not signals:
            return cls._empty_backtest_result(start_date, end_date, initial_capital)

        # Get list of unique tickers in signals
        tickers = list(set([s["ticker"] for s in signals]))
        benchmark = "SPY"
        all_tickers = tickers + [benchmark]
        
        # Download prices
        prices_df = cls.fetch_price_history(all_tickers, start_date, end_date)
        if prices_df.empty or benchmark not in prices_df.columns:
            return cls._empty_backtest_result(start_date, end_date, initial_capital)
        needs_ohlc = any(
            s.get("stop_loss") is not None
            or s.get("take_profit") is not None
            or s.get("trailing_stop_pct") is not None
            for s in signals
        )
        ohlc_df = cls.fetch_ohlc_history(all_tickers, start_date, end_date) if needs_ohlc else pd.DataFrame()
            
        # Build date list index within bounds
        sd_dt = pd.to_datetime(start_date)
        ed_dt = pd.to_datetime(end_date)
        trading_dates = prices_df.loc[sd_dt:ed_dt].index
        
        if len(trading_dates) == 0:
            return cls._empty_backtest_result(start_date, end_date, initial_capital)
            
        # Schedule each signal for the first available trading date after
        # its decision date. Same-day execution would look ahead.
        signals_by_entry_date = {}
        for s in signals:
            try:
                sig_dt = pd.to_datetime(s["date"])
                entry_idx = trading_dates.searchsorted(sig_dt, side="right")
                if entry_idx >= len(trading_dates):
                    continue
                entry_date = trading_dates[entry_idx].strftime("%Y-%m-%d")
                signals_by_entry_date.setdefault(entry_date, []).append(s)
            except Exception:
                continue

        # Simulation states
        cash = initial_capital
        open_positions = []  # List of dicts representing open positions
        completed_trades = []
        equity_curve = []
        
        # Trading calendar loop
        for i, dt in enumerate(trading_dates):
            dt_str = dt.strftime("%Y-%m-%d")
            
            # 1. Update valuation of existing open positions
            positions_value = 0.0
            for pos in open_positions:
                ticker = pos["ticker"]
                current_price = float(prices_df.loc[dt, ticker])
                pos["current_value"] = pos["shares"] * current_price
                positions_value += pos["current_value"]

            portfolio_value = cash + positions_value
            
            # 2. Check for position exits (horizon reached)
            exited_positions = []
            active_positions = []
            for pos in open_positions:
                pos["days_held"] += 1
                ticker = pos["ticker"]
                exit_price = None
                exit_reason = None

                low = cls._get_ohlc_value(ohlc_df, dt, ticker, "Low")
                high = cls._get_ohlc_value(ohlc_df, dt, ticker, "High")
                stop_loss = pos.get("stop_loss")
                take_profit = pos.get("take_profit")
                trailing_stop_pct = pos.get("trailing_stop_pct")
                trailing_stop_price = pos.get("trailing_stop_price")

                effective_stop = stop_loss
                stop_reason = "stop_loss"
                if trailing_stop_pct is not None and trailing_stop_pct > 0 and trailing_stop_price is not None:
                    if effective_stop is None or trailing_stop_price > effective_stop:
                        effective_stop = trailing_stop_price
                        stop_reason = "trailing_stop"

                # Conservative rule: if both are hit in one daily bar, stop-loss wins.
                if effective_stop is not None and low is not None and low <= effective_stop:
                    exit_price = effective_stop
                    exit_reason = stop_reason
                elif take_profit is not None and high is not None and high >= take_profit:
                    exit_price = take_profit
                    exit_reason = "take_profit"
                elif pos["days_held"] >= pos["horizon_days"] or i == len(trading_dates) - 1:
                    exit_price = float(prices_df.loc[dt, ticker])
                    exit_reason = "horizon" if pos["days_held"] >= pos["horizon_days"] else "end_of_backtest"

                if exit_reason is not None:
                    # Close position
                    exit_value, trade_record = cls._close_position_trade(
                        pos=pos,
                        dt=dt,
                        dt_str=dt_str,
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                        prices_df=prices_df,
                        benchmark=benchmark,
                        slippage=slippage,
                    )
                    cash += exit_value
                    completed_trades.append(trade_record)
                    exited_positions.append(pos)
                else:
                    if trailing_stop_pct is not None and trailing_stop_pct > 0:
                        high_for_trail = high if high is not None else float(prices_df.loc[dt, ticker])
                        highest_price = max(pos.get("highest_price", pos["entry_price"]), high_for_trail)
                        pos["highest_price"] = highest_price
                        new_trailing_stop = highest_price * (1.0 - trailing_stop_pct)
                        current_trailing_stop = pos.get("trailing_stop_price")
                        pos["trailing_stop_price"] = (
                            new_trailing_stop
                            if current_trailing_stop is None
                            else max(current_trailing_stop, new_trailing_stop)
                        )
                    active_positions.append(pos)
                    
            open_positions = active_positions
            
            # Re-valuation after exits
            positions_value = sum([p["shares"] * float(prices_df.loc[dt, p["ticker"]]) for p in open_positions])
            portfolio_value = cash + positions_value
            
            # 3. Enter new positions scheduled for this trading date
            day_signals = signals_by_entry_date.get(dt_str, [])
            exit_sides = {"SELL", "UNDERWEIGHT"}
            if day_signals and open_positions:
                exit_tickers = {
                    s["ticker"]
                    for s in day_signals
                    if s.get("side") in exit_sides and s.get("ticker") in prices_df.columns
                }
                if exit_tickers:
                    active_positions = []
                    for pos in open_positions:
                        if pos["ticker"] in exit_tickers:
                            exit_price = float(prices_df.loc[dt, pos["ticker"]])
                            if pd.isna(exit_price) or exit_price <= 0:
                                active_positions.append(pos)
                                continue
                            exit_value, trade_record = cls._close_position_trade(
                                pos=pos,
                                dt=dt,
                                dt_str=dt_str,
                                exit_price=exit_price,
                                exit_reason="sell_signal",
                                prices_df=prices_df,
                                benchmark=benchmark,
                                slippage=slippage,
                            )
                            cash += exit_value
                            completed_trades.append(trade_record)
                        else:
                            active_positions.append(pos)
                    open_positions = active_positions
                    positions_value = sum([p["shares"] * float(prices_df.loc[dt, p["ticker"]]) for p in open_positions])
                    portfolio_value = cash + positions_value

            # Filter only BUY signals (SELL indicates exiting/holding short, but we primarily support long-only for now)
            valid_signals = [s for s in day_signals if s["side"] in ("BUY", "STRONG BUY", "OVERWEIGHT") and s["ticker"] in prices_df.columns]
            
            if valid_signals and cash > 0:
                # Sizing model:
                # fixed -> allocate 10% of portfolio equity per trade
                # confidence -> scale allocation between 5% and 15% based on confidence (e.g. 15% * confidence)
                for sig in valid_signals:
                    ticker = sig["ticker"]
                    # Prevent buying a ticker if we already hold it
                    if any(p["ticker"] == ticker for p in open_positions):
                        continue
                        
                    entry_price = float(prices_df.loc[dt, ticker])
                    if pd.isna(entry_price) or entry_price <= 0:
                        continue
                        
                    # Calculate position size
                    signal_position_pct = cls._optional_float(sig.get("position_size_pct"))
                    if signal_position_pct is not None and signal_position_pct > 0:
                        size_fraction = min(signal_position_pct, 0.95)
                    elif sizing_mode == "fixed":
                        size_fraction = 0.10
                    else: # confidence
                        size_fraction = 0.15 * sig["confidence"]
                        
                    position_size = portfolio_value * size_fraction
                    
                    # Limit size to available cash
                    position_size = min(position_size, cash * 0.95) # Keep a tiny cash buffer
                    
                    if position_size > 100.0: # Minimum trade threshold
                        # Add slippage to buy
                        final_entry_price = entry_price * (1.0 + slippage)
                        shares = position_size / final_entry_price
                        
                        cash -= position_size
                        
                        open_positions.append({
                            "ticker": ticker,
                            "entry_date": dt_str,
                            "entry_price": final_entry_price,
                            "side": sig["side"],
                            "confidence": sig["confidence"],
                            "horizon_days": sig["horizon_days"],
                            "stop_loss": cls._optional_float(sig.get("stop_loss")),
                            "take_profit": cls._optional_float(sig.get("take_profit")),
                            "trailing_stop_pct": cls._optional_float(sig.get("trailing_stop_pct")),
                            "signal_date": sig.get("date"),
                            "signal_risk_flags": list(sig.get("risk_flags") or []),
                            "signal_calculation_basis": sig.get("calculation_basis") if isinstance(sig.get("calculation_basis"), dict) else {},
                            "trailing_stop_price": (
                                final_entry_price * (1.0 - cls._optional_float(sig.get("trailing_stop_pct")))
                                if cls._optional_float(sig.get("trailing_stop_pct")) is not None
                                and cls._optional_float(sig.get("trailing_stop_pct")) > 0
                                else None
                            ),
                            "highest_price": final_entry_price,
                            "shares": shares,
                            "entry_size": position_size,
                            "days_held": 0
                        })
            
            # Recalculate final valuation of the day
            positions_value = sum([p["shares"] * float(prices_df.loc[dt, p["ticker"]]) for p in open_positions])
            portfolio_value = cash + positions_value
            
            # Track equity curve against benchmark
            bench_close = float(prices_df.loc[dt, benchmark])
            equity_curve.append({
                "date": dt_str,
                "portfolio_value": round(portfolio_value, 2),
                "cash": round(cash, 2),
                "benchmark_value": bench_close
            })

        # Calculate final metrics from equity curve and completed trades
        summary = cls._calculate_backtest_summary(equity_curve, completed_trades, prices_df, benchmark, trading_dates)
        
        return {
            "summary": summary,
            "equity_curve": equity_curve,
            "trades": completed_trades
        }

    @classmethod
    def _calculate_backtest_summary(
        cls, 
        equity_curve: List[Dict[str, Any]], 
        trades: List[Dict[str, Any]], 
        prices_df: pd.DataFrame,
        benchmark: str,
        trading_dates: pd.DatetimeIndex
    ) -> Dict[str, Any]:
        """Compute standard quant metrics from the portfolio simulation results."""
        if not equity_curve:
            return cls._empty_summary()
            
        df_eq = pd.DataFrame(equity_curve)
        
        # Portfolio Returns
        initial_val = df_eq["portfolio_value"].iloc[0]
        final_val = df_eq["portfolio_value"].iloc[-1]
        cumulative_return = (final_val - initial_val) / initial_val
        
        # Annualized return
        n_days = len(df_eq)
        annualized_return = (1.0 + cumulative_return) ** (252.0 / n_days) - 1.0 if n_days > 0 else 0.0
        
        # Benchmark Returns
        bench_initial = df_eq["benchmark_value"].iloc[0]
        bench_final = df_eq["benchmark_value"].iloc[-1]
        benchmark_return = (bench_final - bench_initial) / bench_initial
        
        # Daily Returns for Sharpe & Beta
        df_eq["port_daily_ret"] = df_eq["portfolio_value"].pct_change().fillna(0.0)
        df_eq["bench_daily_ret"] = df_eq["benchmark_value"].pct_change().fillna(0.0)
        
        # Volatility
        volatility = df_eq["port_daily_ret"].std() * np.sqrt(252)
        
        # Sharpe Ratio (annualized, zero risk-free rate assumption)
        mean_ret = df_eq["port_daily_ret"].mean()
        std_ret = df_eq["port_daily_ret"].std()
        sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0
        downside_ret = df_eq.loc[df_eq["port_daily_ret"] < 0, "port_daily_ret"]
        downside_std = downside_ret.std()
        sortino_ratio = (mean_ret / downside_std) * np.sqrt(252) if downside_std and downside_std > 0 else 0.0
        
        # Max Drawdown (MDD)
        df_eq["peak"] = df_eq["portfolio_value"].cummax()
        df_eq["drawdown"] = (df_eq["portfolio_value"] - df_eq["peak"]) / df_eq["peak"]
        max_drawdown = float(df_eq["drawdown"].min())
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown < 0 else 0.0
        
        # Win Rate & Profit Factor
        winning_trades = [t for t in trades if t["profit"] > 0]
        losing_trades = [t for t in trades if t["profit"] <= 0]
        
        total_trades = len(trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        gross_profits = sum([t["profit"] for t in winning_trades])
        gross_losses = abs(sum([t["profit"] for t in losing_trades]))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits if gross_profits > 0 else 1.0)
        average_win = gross_profits / len(winning_trades) if winning_trades else 0.0
        average_loss = -gross_losses / len(losing_trades) if losing_trades else 0.0
        payoff_ratio = average_win / abs(average_loss) if average_loss < 0 else (average_win if average_win > 0 else 0.0)
        average_equity = float(df_eq["portfolio_value"].mean()) if not df_eq.empty else 0.0
        traded_notional = sum(float(t.get("size", 0.0)) for t in trades)
        turnover = (traded_notional * 2.0 / average_equity) if average_equity > 0 else 0.0
        exposure = float((1.0 - (df_eq["cash"] / df_eq["portfolio_value"]).clip(lower=0.0, upper=1.0)).mean())
        
        # Alpha & Beta vs Benchmark (using simple covariance math)
        port_ret = df_eq["port_daily_ret"].values
        bench_ret = df_eq["bench_daily_ret"].values
        
        cov_matrix = np.cov(port_ret, bench_ret)
        if cov_matrix.shape == (2, 2) and cov_matrix[1, 1] > 0:
            beta = cov_matrix[0, 1] / cov_matrix[1, 1]
            alpha = mean_ret * 252 - (beta * bench_ret.mean() * 252) # Annualized Alpha
        else:
            beta = 1.0
            alpha = cumulative_return - benchmark_return
            
        return {
            "cumulative_return": round(cumulative_return, 4),
            "annualized_return": round(annualized_return, 4),
            "cagr": round(annualized_return, 4),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "average_win": round(average_win, 2),
            "average_loss": round(average_loss, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "turnover": round(turnover, 4),
            "exposure": round(exposure, 4),
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "benchmark_return": round(benchmark_return, 4),
            "alpha": round(alpha, 4),
            "beta": round(beta, 2)
        }

    @staticmethod
    def _empty_backtest_result(start_date: str, end_date: str, initial_capital: float) -> Dict[str, Any]:
        return {
            "summary": BacktestEngine._empty_summary(),
            "equity_curve": [
                {
                    "date": start_date,
                    "portfolio_value": initial_capital,
                    "cash": initial_capital,
                    "benchmark_value": 1.0
                },
                {
                    "date": end_date,
                    "portfolio_value": initial_capital,
                    "cash": initial_capital,
                    "benchmark_value": 1.0
                }
            ],
            "trades": []
        }

    @staticmethod
    def _empty_summary() -> Dict[str, Any]:
        return {
            "cumulative_return": 0.0,
            "annualized_return": 0.0,
            "cagr": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 1.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "payoff_ratio": 0.0,
            "turnover": 0.0,
            "exposure": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "benchmark_return": 0.0,
            "alpha": 0.0,
            "beta": 1.0
        }
