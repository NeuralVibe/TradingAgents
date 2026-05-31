import re
import logging
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class SignalExtractor:
    """Helper to extract standardized signals from prose reports or PortfolioDecision objects."""

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
        side = cls.parse_recommendation(decision_text)
        confidence = cls.extract_confidence(decision_text, side)
        horizon_days = cls.extract_horizon_days(decision_text)
        price_target = cls.extract_price_target(decision_text)
        
        return {
            "ticker": ticker.upper(),
            "date": date,
            "side": side,
            "confidence": confidence,
            "horizon_days": horizon_days,
            "price_target": price_target
        }


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
                
            # Fill missing prices safely
            df = df.ffill().bfill()
            return df
        except Exception as e:
            logger.error(f"Error downloading prices for backtest: {str(e)}")
            return pd.DataFrame()

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
            
        # Build date list index within bounds
        sd_dt = pd.to_datetime(start_date)
        ed_dt = pd.to_datetime(end_date)
        trading_dates = prices_df.loc[sd_dt:ed_dt].index
        
        if len(trading_dates) == 0:
            return cls._empty_backtest_result(start_date, end_date, initial_capital)
            
        # Group signals by date for O(1) retrieval during daily loop
        signals_by_date = {}
        for s in signals:
            try:
                sig_date = pd.to_datetime(s["date"]).strftime("%Y-%m-%d")
                signals_by_date.setdefault(sig_date, []).append(s)
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
                # Reached exit date if trading days count >= horizon_days
                pos["days_held"] += 1
                if pos["days_held"] >= pos["horizon_days"] or i == len(trading_dates) - 1:
                    # Close position
                    ticker = pos["ticker"]
                    exit_price = float(prices_df.loc[dt, ticker])
                    
                    # Deduct slippage on sell
                    final_exit_price = exit_price * (1.0 - slippage)
                    exit_value = pos["shares"] * final_exit_price
                    cash += exit_value
                    
                    # Record trade
                    raw_return = (final_exit_price - pos["entry_price"]) / pos["entry_price"]
                    # Calculate benchmark return during the trade
                    bench_start_price = float(prices_df.loc[pos["entry_date"], benchmark])
                    bench_end_price = float(prices_df.loc[dt, benchmark])
                    bench_return = (bench_end_price - bench_start_price) / bench_start_price
                    alpha_return = raw_return - bench_return
                    
                    profit = exit_value - pos["entry_size"]
                    
                    completed_trades.append({
                        "ticker": ticker,
                        "entry_date": pos["entry_date"],
                        "entry_price": round(pos["entry_price"], 2),
                        "exit_date": dt_str,
                        "exit_price": round(exit_price, 2),
                        "side": pos["side"],
                        "confidence": pos["confidence"],
                        "horizon_days": pos["horizon_days"],
                        "raw_return": round(raw_return, 4),
                        "alpha_return": round(alpha_return, 4),
                        "profit": round(profit, 2),
                        "size": round(pos["entry_size"], 2)
                    })
                    exited_positions.append(pos)
                else:
                    active_positions.append(pos)
                    
            open_positions = active_positions
            
            # Re-valuation after exits
            positions_value = sum([p["shares"] * float(prices_df.loc[dt, p["ticker"]]) for p in open_positions])
            portfolio_value = cash + positions_value
            
            # 3. Enter new positions from signals on this date
            day_signals = signals_by_date.get(dt_str, [])
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
                    if sizing_mode == "fixed":
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
        
        # Max Drawdown (MDD)
        df_eq["peak"] = df_eq["portfolio_value"].cummax()
        df_eq["drawdown"] = (df_eq["portfolio_value"] - df_eq["peak"]) / df_eq["peak"]
        max_drawdown = float(df_eq["drawdown"].min())
        
        # Win Rate & Profit Factor
        winning_trades = [t for t in trades if t["profit"] > 0]
        losing_trades = [t for t in trades if t["profit"] <= 0]
        
        total_trades = len(trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        gross_profits = sum([t["profit"] for t in winning_trades])
        gross_losses = abs(sum([t["profit"] for t in losing_trades]))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits if gross_profits > 0 else 1.0)
        
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
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
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
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 1.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "benchmark_return": 0.0,
            "alpha": 0.0,
            "beta": 1.0
        }
