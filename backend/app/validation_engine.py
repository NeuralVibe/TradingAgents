from __future__ import annotations

from collections import Counter, defaultdict
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .quant_engine import BacktestEngine, SignalExtractor


BUY_LIKE_SIDES = {"BUY", "STRONG BUY", "OVERWEIGHT"}
POINT_IN_TIME_RISK_FLAGS = [
    "fundamentals_not_point_in_time",
    "social_data_current_only",
    "news_timestamp_missing",
    "llm_parametric_lookahead_risk",
    "quant_price_setup_unavailable",
]


class ValidationEngine:
    """Validation utilities layered on top of the existing backtest engine."""

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return None if pd.isna(parsed) else parsed

    @staticmethod
    def _date(value: Any) -> Optional[pd.Timestamp]:
        try:
            return pd.to_datetime(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _date_str(value: pd.Timestamp) -> str:
        return value.strftime("%Y-%m-%d")

    @classmethod
    def _normalize_side(cls, value: Any) -> str:
        return SignalExtractor._normalize_side(value)

    @classmethod
    def _signals_in_range(
        cls,
        signals: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        selected: List[Dict[str, Any]] = []
        for signal in signals:
            signal_date = cls._date(signal.get("date"))
            if signal_date is not None and start <= signal_date <= end:
                selected.append(signal)
        return selected

    @staticmethod
    def build_parameter_grid(
        sizing_modes: List[str],
        slippage_values: List[float],
        min_risk_reward_values: List[float],
        min_price_attractiveness_values: List[float],
    ) -> List[Dict[str, Any]]:
        sizing_modes = sizing_modes or ["fixed", "confidence"]
        slippage_values = slippage_values or [0.0005]
        min_risk_reward_values = min_risk_reward_values or [1.2]
        min_price_attractiveness_values = min_price_attractiveness_values or [0.35]

        return [
            {
                "sizing_mode": sizing_mode,
                "slippage": float(slippage),
                "min_risk_reward": float(min_risk_reward),
                "min_price_attractiveness": float(min_price_attractiveness),
            }
            for sizing_mode, slippage, min_risk_reward, min_price_attractiveness in product(
                sizing_modes,
                slippage_values,
                min_risk_reward_values,
                min_price_attractiveness_values,
            )
        ]

    @classmethod
    def filter_signals(
        cls,
        signals: List[Dict[str, Any]],
        min_risk_reward: Optional[float] = None,
        min_price_attractiveness: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Filter buy-like signals by quant setup thresholds and keep exit signals."""
        filtered: List[Dict[str, Any]] = []
        filter_events: List[Dict[str, Any]] = []

        for signal in signals:
            side = cls._normalize_side(signal.get("side"))
            if side not in BUY_LIKE_SIDES:
                filtered.append(signal)
                continue

            risk_reward = cls._to_float(signal.get("risk_reward_ratio"))
            attractiveness = cls._to_float(signal.get("price_attractiveness_score"))
            reasons: List[str] = []

            if min_risk_reward is not None:
                if risk_reward is None:
                    reasons.append("quant_price_setup_unavailable")
                elif risk_reward < min_risk_reward:
                    reasons.append("filtered_low_risk_reward")

            if min_price_attractiveness is not None:
                if attractiveness is None:
                    if "quant_price_setup_unavailable" not in reasons:
                        reasons.append("quant_price_setup_unavailable")
                elif attractiveness < min_price_attractiveness:
                    reasons.append("filtered_low_price_attractiveness")

            if reasons:
                for reason in reasons:
                    filter_events.append(
                        {
                            "flag": reason,
                            "ticker": signal.get("ticker"),
                            "date": signal.get("date"),
                        }
                    )
                continue

            filtered.append(signal)

        return filtered, filter_events

    @classmethod
    def run_backtest_with_parameters(
        cls,
        signals: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        initial_capital: float,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        filtered_signals, filter_events = cls.filter_signals(
            signals=signals,
            min_risk_reward=cls._to_float(parameters.get("min_risk_reward")),
            min_price_attractiveness=cls._to_float(parameters.get("min_price_attractiveness")),
        )
        backtest = BacktestEngine.run_portfolio_backtest(
            signals=filtered_signals,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            sizing_mode=str(parameters.get("sizing_mode") or "confidence"),
            slippage=max(0.0, float(parameters.get("slippage") or 0.0)),
        )
        return {
            "backtest": backtest,
            "filtered_signal_count": len(signals) - len(filtered_signals),
            "kept_signal_count": len(filtered_signals),
            "filter_events": filter_events,
        }

    @classmethod
    def _score_summary(cls, summary: Dict[str, Any]) -> float:
        sharpe = cls._to_float(summary.get("sharpe_ratio")) or 0.0
        max_drawdown = cls._to_float(summary.get("max_drawdown")) or 0.0
        return round(sharpe - abs(max_drawdown) * 2.0, 4)

    @classmethod
    def run_parameter_sweep(
        cls,
        signals: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        sizing_modes: Optional[List[str]] = None,
        slippage_values: Optional[List[float]] = None,
        min_risk_reward_values: Optional[List[float]] = None,
        min_price_attractiveness_values: Optional[List[float]] = None,
        min_trades: int = 3,
    ) -> Dict[str, Any]:
        parameter_grid = cls.build_parameter_grid(
            sizing_modes=sizing_modes or ["fixed", "confidence"],
            slippage_values=slippage_values or [0.0, 0.0005, 0.001],
            min_risk_reward_values=min_risk_reward_values or [1.0, 1.2, 1.5],
            min_price_attractiveness_values=min_price_attractiveness_values or [0.25, 0.35, 0.5],
        )

        rows: List[Dict[str, Any]] = []
        best_row: Optional[Dict[str, Any]] = None
        best_backtest: Optional[Dict[str, Any]] = None
        best_filter_events: List[Dict[str, Any]] = []

        for parameters in parameter_grid:
            run = cls.run_backtest_with_parameters(
                signals=signals,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                parameters=parameters,
            )
            summary = run["backtest"]["summary"]
            trade_count = int(summary.get("total_trades", 0))
            risk_flags = [
                event["flag"]
                for event in run["filter_events"]
                if event.get("flag")
            ]
            if trade_count < min_trades:
                risk_flags.append("insufficient_trade_count")

            score = cls._score_summary(summary)
            if trade_count < min_trades:
                score = round(score - 1.0, 4)

            row = {
                "parameters": parameters,
                "score": score,
                "summary": summary,
                "trade_count": trade_count,
                "filtered_signal_count": run["filtered_signal_count"],
                "kept_signal_count": run["kept_signal_count"],
                "risk_flags": sorted(set(risk_flags)),
                "risk_flag_counts": dict(Counter(risk_flags)),
            }
            rows.append(row)

            if best_row is None or row["score"] > best_row["score"]:
                best_row = row
                best_backtest = run["backtest"]
                best_filter_events = run["filter_events"]

        rows.sort(key=lambda item: item["score"], reverse=True)
        best_trades = best_backtest["trades"] if best_backtest else []

        return {
            "best_parameters": best_row["parameters"] if best_row else None,
            "best_summary": best_row["summary"] if best_row else None,
            "results": rows,
            "windows": [],
            "risk_flag_counts": cls.risk_flag_counts(signals, best_filter_events),
            "risk_flag_details": cls.risk_flag_details(signals, best_filter_events, best_trades),
            "regime_breakdown": cls.regime_breakdown(signals, best_trades),
            "ticker_breakdown": cls.ticker_breakdown(signals, best_trades),
            "period_breakdown": cls.period_breakdown(best_trades),
            "calculation_basis": cls.calculation_basis_summary(signals)
            | {
                "parameter_grid_size": len(parameter_grid),
                "score_formula": "sharpe_ratio - abs(max_drawdown) * 2",
                "insufficient_trade_penalty": -1.0,
                "min_trades": min_trades,
            },
        }

    @classmethod
    def generate_walk_forward_windows(
        cls,
        start_date: str,
        end_date: str,
        train_window_days: int = 252,
        test_window_days: int = 63,
        step_days: int = 63,
    ) -> List[Dict[str, Any]]:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        train_days = max(1, int(train_window_days))
        test_days = max(1, int(test_window_days))
        step = max(1, int(step_days))

        windows: List[Dict[str, Any]] = []
        train_start = start
        index = 0
        while train_start <= end:
            train_end = train_start + pd.Timedelta(days=train_days - 1)
            test_start = train_end + pd.Timedelta(days=1)
            test_end = test_start + pd.Timedelta(days=test_days - 1)
            if test_start > end:
                break

            windows.append(
                {
                    "window_index": index,
                    "train_start": cls._date_str(train_start),
                    "train_end": cls._date_str(min(train_end, end)),
                    "test_start": cls._date_str(test_start),
                    "test_end": cls._date_str(min(test_end, end)),
                }
            )
            train_start = train_start + pd.Timedelta(days=step)
            index += 1

        return windows

    @classmethod
    def run_walk_forward_validation(
        cls,
        signals: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        train_window_days: int = 252,
        test_window_days: int = 63,
        step_days: int = 63,
        min_trades_per_window: int = 3,
        sizing_modes: Optional[List[str]] = None,
        slippage_values: Optional[List[float]] = None,
        min_risk_reward_values: Optional[List[float]] = None,
        min_price_attractiveness_values: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        windows = cls.generate_walk_forward_windows(
            start_date=start_date,
            end_date=end_date,
            train_window_days=train_window_days,
            test_window_days=test_window_days,
            step_days=step_days,
        )
        evaluated_windows: List[Dict[str, Any]] = []
        all_filter_events: List[Dict[str, Any]] = []
        all_test_trades: List[Dict[str, Any]] = []

        for window in windows:
            train_signals = cls._signals_in_range(signals, window["train_start"], window["train_end"])
            test_signals = cls._signals_in_range(signals, window["test_start"], window["test_end"])
            train_sweep = cls.run_parameter_sweep(
                signals=train_signals,
                start_date=window["train_start"],
                end_date=window["train_end"],
                initial_capital=initial_capital,
                sizing_modes=sizing_modes,
                slippage_values=slippage_values,
                min_risk_reward_values=min_risk_reward_values,
                min_price_attractiveness_values=min_price_attractiveness_values,
                min_trades=min_trades_per_window,
            )
            selected_parameters = train_sweep.get("best_parameters") or {
                "sizing_mode": "confidence",
                "slippage": 0.0005,
                "min_risk_reward": 1.2,
                "min_price_attractiveness": 0.35,
            }
            test_run = cls.run_backtest_with_parameters(
                signals=test_signals,
                start_date=window["test_start"],
                end_date=window["test_end"],
                initial_capital=initial_capital,
                parameters=selected_parameters,
            )
            test_summary = test_run["backtest"]["summary"]
            test_trade_count = int(test_summary.get("total_trades", 0))
            risk_flags = [
                event["flag"]
                for event in test_run["filter_events"]
                if event.get("flag")
            ]
            if test_trade_count < min_trades_per_window:
                risk_flags.append("insufficient_trade_count")

            all_filter_events.extend(test_run["filter_events"])
            all_test_trades.extend(test_run["backtest"]["trades"])
            evaluated_windows.append(
                {
                    **window,
                    "selected_parameters": selected_parameters,
                    "train_summary": train_sweep.get("best_summary") or BacktestEngine._empty_summary(),
                    "test_summary": test_summary,
                    "train_signal_count": len(train_signals),
                    "test_signal_count": len(test_signals),
                    "test_trade_count": test_trade_count,
                    "risk_flags": sorted(set(risk_flags)),
                    "risk_flag_counts": dict(Counter(risk_flags)),
                }
            )

        summary = cls.walk_forward_summary(evaluated_windows, min_trades_per_window)
        return {
            "best_parameters": cls.most_common_parameters(evaluated_windows),
            "best_summary": None,
            "summary": summary,
            "results": [],
            "windows": evaluated_windows,
            "risk_flag_counts": cls.risk_flag_counts(signals, all_filter_events),
            "risk_flag_details": cls.risk_flag_details(signals, all_filter_events, all_test_trades),
            "regime_breakdown": cls.regime_breakdown(signals, all_test_trades),
            "ticker_breakdown": cls.ticker_breakdown(signals, all_test_trades),
            "period_breakdown": cls.period_breakdown(all_test_trades),
            "calculation_basis": cls.calculation_basis_summary(signals)
            | {
                "train_window_days": train_window_days,
                "test_window_days": test_window_days,
                "step_days": step_days,
                "min_trades_per_window": min_trades_per_window,
                "score_formula": "sharpe_ratio - abs(max_drawdown) * 2",
            },
        }

    @classmethod
    def walk_forward_summary(
        cls,
        windows: List[Dict[str, Any]],
        min_trades_per_window: int,
    ) -> Dict[str, Any]:
        if not windows:
            return {
                "total_windows": 0,
                "average_test_return": 0.0,
                "average_test_sharpe": 0.0,
                "average_test_mdd": 0.0,
                "stability_score": 0.0,
                "insufficient_window_count": 0,
            }

        returns = [
            cls._to_float(window["test_summary"].get("cumulative_return")) or 0.0
            for window in windows
        ]
        sharpes = [
            cls._to_float(window["test_summary"].get("sharpe_ratio")) or 0.0
            for window in windows
        ]
        drawdowns = [
            cls._to_float(window["test_summary"].get("max_drawdown")) or 0.0
            for window in windows
        ]
        insufficient = sum(
            1
            for window in windows
            if int(window.get("test_trade_count", 0)) < min_trades_per_window
        )
        positive_ratio = sum(1 for value in returns if value > 0) / len(returns)
        return_std = float(pd.Series(returns).std()) if len(returns) > 1 else 0.0
        stability_score = max(0.0, min(1.0, positive_ratio - min(0.5, return_std)))

        return {
            "total_windows": len(windows),
            "average_test_return": round(float(pd.Series(returns).mean()), 4),
            "average_test_sharpe": round(float(pd.Series(sharpes).mean()), 4),
            "average_test_mdd": round(float(pd.Series(drawdowns).mean()), 4),
            "stability_score": round(stability_score, 4),
            "insufficient_window_count": insufficient,
        }

    @staticmethod
    def most_common_parameters(windows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not windows:
            return None
        encoded = Counter(
            tuple(sorted((window.get("selected_parameters") or {}).items()))
            for window in windows
        )
        if not encoded:
            return None
        return dict(encoded.most_common(1)[0][0])

    @classmethod
    def build_validation_summary(
        cls,
        signals: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        train_window_days: int = 252,
        test_window_days: int = 63,
        step_days: int = 63,
        min_trades_per_window: int = 3,
        sizing_modes: Optional[List[str]] = None,
        slippage_values: Optional[List[float]] = None,
        min_risk_reward_values: Optional[List[float]] = None,
        min_price_attractiveness_values: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        base_backtest = BacktestEngine.run_portfolio_backtest(
            signals=signals,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            sizing_mode="confidence",
            slippage=0.0005,
        )
        sweep = cls.run_parameter_sweep(
            signals=signals,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            sizing_modes=sizing_modes,
            slippage_values=slippage_values,
            min_risk_reward_values=min_risk_reward_values,
            min_price_attractiveness_values=min_price_attractiveness_values,
            min_trades=min_trades_per_window,
        )
        walk_forward = cls.run_walk_forward_validation(
            signals=signals,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            train_window_days=train_window_days,
            test_window_days=test_window_days,
            step_days=step_days,
            min_trades_per_window=min_trades_per_window,
            sizing_modes=sizing_modes,
            slippage_values=slippage_values,
            min_risk_reward_values=min_risk_reward_values,
            min_price_attractiveness_values=min_price_attractiveness_values,
        )

        risk_flag_details = cls.risk_flag_details(signals, trades=base_backtest["trades"])
        return {
            "base_summary": base_backtest["summary"],
            "best_parameters": sweep.get("best_parameters"),
            "best_summary": sweep.get("best_summary"),
            "summary": walk_forward.get("summary"),
            "results": sweep.get("results", []),
            "windows": walk_forward.get("windows", []),
            "risk_flag_counts": cls.risk_flag_counts(signals),
            "risk_flag_details": risk_flag_details,
            "regime_breakdown": sweep.get("regime_breakdown", []),
            "ticker_breakdown": sweep.get("ticker_breakdown", []),
            "period_breakdown": sweep.get("period_breakdown", []),
            "calculation_basis": cls.calculation_basis_summary(signals)
            | {
                "validation_summary_sources": [
                    "base_backtest",
                    "parameter_sweep",
                    "walk_forward",
                ],
            },
        }

    @classmethod
    def risk_flag_counts(
        cls,
        signals: List[Dict[str, Any]],
        extra_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, int]:
        counts = Counter()
        for signal in signals:
            for flag in signal.get("risk_flags") or []:
                counts[str(flag)] += 1
        for event in extra_events or []:
            flag = event.get("flag")
            if flag:
                counts[str(flag)] += 1
        for flag in POINT_IN_TIME_RISK_FLAGS:
            counts.setdefault(flag, 0)
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    @classmethod
    def risk_flag_details(
        cls,
        signals: List[Dict[str, Any]],
        extra_events: Optional[List[Dict[str, Any]]] = None,
        trades: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        details: Dict[str, Dict[str, Any]] = {}

        def ensure(flag: str) -> Dict[str, Any]:
            if flag not in details:
                details[flag] = {
                    "flag": flag,
                    "count": 0,
                    "affected_trade_count": 0,
                    "affected_ticker_count": 0,
                    "example_ticker": None,
                    "example_date": None,
                    "_tickers": set(),
                }
            return details[flag]

        for signal in signals:
            ticker = signal.get("ticker")
            date = signal.get("date")
            for flag in signal.get("risk_flags") or []:
                row = ensure(str(flag))
                row["count"] += 1
                if ticker:
                    row["_tickers"].add(str(ticker))
                if row["example_ticker"] is None:
                    row["example_ticker"] = ticker
                    row["example_date"] = date

        for event in extra_events or []:
            flag = event.get("flag")
            if not flag:
                continue
            row = ensure(str(flag))
            row["count"] += 1
            ticker = event.get("ticker")
            if ticker:
                row["_tickers"].add(str(ticker))
            if row["example_ticker"] is None:
                row["example_ticker"] = ticker
                row["example_date"] = event.get("date")

        for trade in trades or []:
            trade_flags = trade.get("signal_risk_flags") or []
            if isinstance(trade_flags, str):
                trade_flags = [trade_flags]
            ticker = trade.get("ticker")
            for flag in trade_flags:
                row = ensure(str(flag))
                row["affected_trade_count"] += 1
                if ticker:
                    row["_tickers"].add(str(ticker))
                if row["example_ticker"] is None:
                    row["example_ticker"] = ticker
                    row["example_date"] = trade.get("signal_date") or trade.get("entry_date")

        for flag in POINT_IN_TIME_RISK_FLAGS:
            ensure(flag)

        rows: List[Dict[str, Any]] = []
        for row in details.values():
            tickers = row.pop("_tickers")
            row["affected_ticker_count"] = len(tickers)
            rows.append(row)
        rows.sort(key=lambda item: (-item["count"], item["flag"]))
        return rows

    @classmethod
    def calculation_basis_summary(cls, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        key_counts = Counter()
        quant_basis_key_counts = Counter()
        for signal in signals:
            basis = signal.get("calculation_basis")
            if not isinstance(basis, dict):
                continue
            for key, value in basis.items():
                key_counts[str(key)] += 1
                if key == "quant_price_setup" and isinstance(value, dict):
                    for nested_key in value:
                        quant_basis_key_counts[str(nested_key)] += 1
        return {
            "signal_count": len(signals),
            "basis_key_counts": dict(key_counts),
            "quant_basis_key_counts": dict(quant_basis_key_counts),
            "point_in_time_flags_tracked": POINT_IN_TIME_RISK_FLAGS,
        }

    @classmethod
    def ticker_breakdown(
        cls,
        signals: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        signal_counts = Counter(str(signal.get("ticker")) for signal in signals if signal.get("ticker"))
        by_ticker: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            by_ticker[str(trade.get("ticker"))].append(trade)

        tickers = set(signal_counts) | set(by_ticker)
        rows: List[Dict[str, Any]] = []
        for ticker in tickers:
            ticker_trades = by_ticker.get(ticker, [])
            returns = [cls._to_float(trade.get("raw_return")) or 0.0 for trade in ticker_trades]
            cumulative_return = 1.0
            for value in returns:
                cumulative_return *= 1.0 + value
            wins = sum(1 for value in returns if value > 0)
            rows.append(
                {
                    "ticker": ticker,
                    "signal_count": signal_counts.get(ticker, 0),
                    "trade_count": len(ticker_trades),
                    "win_rate": round(wins / len(returns), 4) if returns else 0.0,
                    "average_return": round(float(pd.Series(returns).mean()), 4) if returns else 0.0,
                    "cumulative_return": round(cumulative_return - 1.0, 4) if returns else 0.0,
                    "profit": round(sum(cls._to_float(trade.get("profit")) or 0.0 for trade in ticker_trades), 2),
                }
            )
        rows.sort(key=lambda item: item["cumulative_return"], reverse=True)
        return rows

    @classmethod
    def _signal_regime_for_trade(
        cls,
        signals_by_ticker: Dict[str, List[Dict[str, Any]]],
        trade: Dict[str, Any],
    ) -> str:
        ticker = str(trade.get("ticker"))
        entry_date = cls._date(trade.get("entry_date"))
        if entry_date is None:
            return "unknown"
        for signal in reversed(signals_by_ticker.get(ticker, [])):
            signal_date = cls._date(signal.get("date"))
            if signal_date is not None and signal_date <= entry_date:
                return str(signal.get("volatility_regime") or "unknown")
        return "unknown"

    @classmethod
    def regime_breakdown(
        cls,
        signals: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        signals_by_ticker: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        signal_counts = Counter()
        rr_by_regime: Dict[str, List[float]] = defaultdict(list)
        for signal in signals:
            ticker = signal.get("ticker")
            if ticker:
                signals_by_ticker[str(ticker)].append(signal)
            regime = str(signal.get("volatility_regime") or "unknown")
            signal_counts[regime] += 1
            risk_reward = cls._to_float(signal.get("risk_reward_ratio"))
            if risk_reward is not None:
                rr_by_regime[regime].append(risk_reward)
        for ticker_signals in signals_by_ticker.values():
            ticker_signals.sort(key=lambda item: str(item.get("date") or ""))

        trades_by_regime: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            regime = cls._signal_regime_for_trade(signals_by_ticker, trade)
            trades_by_regime[regime].append(trade)

        regimes = set(signal_counts) | set(trades_by_regime)
        rows: List[Dict[str, Any]] = []
        for regime in regimes:
            regime_trades = trades_by_regime.get(regime, [])
            returns = [cls._to_float(trade.get("raw_return")) or 0.0 for trade in regime_trades]
            wins = sum(1 for value in returns if value > 0)
            rr_values = rr_by_regime.get(regime, [])
            rows.append(
                {
                    "regime": regime,
                    "signal_count": signal_counts.get(regime, 0),
                    "trade_count": len(regime_trades),
                    "win_rate": round(wins / len(returns), 4) if returns else 0.0,
                    "average_return": round(float(pd.Series(returns).mean()), 4) if returns else 0.0,
                    "average_risk_reward": round(float(pd.Series(rr_values).mean()), 4) if rr_values else 0.0,
                }
            )
        rows.sort(key=lambda item: item["trade_count"], reverse=True)
        return rows

    @classmethod
    def period_breakdown(cls, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_period: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            exit_date = cls._date(trade.get("exit_date"))
            if exit_date is None:
                continue
            by_period[exit_date.strftime("%Y-%m")].append(trade)

        rows: List[Dict[str, Any]] = []
        for period, period_trades in by_period.items():
            returns = [cls._to_float(trade.get("raw_return")) or 0.0 for trade in period_trades]
            cumulative_return = 1.0
            for value in returns:
                cumulative_return *= 1.0 + value
            rows.append(
                {
                    "period": period,
                    "trade_count": len(period_trades),
                    "average_return": round(float(pd.Series(returns).mean()), 4) if returns else 0.0,
                    "cumulative_return": round(cumulative_return - 1.0, 4) if returns else 0.0,
                    "profit": round(sum(cls._to_float(trade.get("profit")) or 0.0 for trade in period_trades), 2),
                }
            )
        rows.sort(key=lambda item: item["period"])
        return rows
