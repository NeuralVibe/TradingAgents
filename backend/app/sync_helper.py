import logging
import datetime
import json
import yfinance as yf
from sqlalchemy.orm import Session
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.default_config import DEFAULT_CONFIG
from .models import Decision
from .quant_engine import SignalExtractor

logger = logging.getLogger(__name__)

def parse_percent(val_str: str) -> float:
    """Parse percentage string like '+5.2%' or '-1.0%' to float 0.052 or -0.01."""
    if not val_str:
        return 0.0
    try:
        cleaned = val_str.replace('%', '').strip()
        return float(cleaned) / 100.0
    except ValueError:
        return 0.0

def parse_days(val_str: str) -> int:
    """Parse holding days string like '5d' or '5' to integer 5."""
    if not val_str:
        return 5
    try:
        cleaned = val_str.replace('d', '').strip()
        return int(cleaned)
    except ValueError:
        return 5

def sync_markdown_log_to_db(db: Session) -> dict:
    """Sync all Markdown memory log entries into the SQLite decisions table."""
    try:
        # Initialize standard TradingMemoryLog
        mem_log = TradingMemoryLog(DEFAULT_CONFIG)
        entries = mem_log.load_entries()
        
        if not entries:
            logger.info("No legacy markdown memory log entries found.")
            return {"status": "success", "synced_count": 0, "updated_count": 0}
            
        synced_count = 0
        updated_count = 0
        
        for entry in entries:
            ticker = entry["ticker"].upper()
            date = entry["date"]
            
            # Extract standard values
            side = SignalExtractor.parse_recommendation(entry["decision"])
            confidence = SignalExtractor.extract_confidence(entry["decision"], side)
            horizon_days = SignalExtractor.extract_horizon_days(entry["decision"])
            price_target = SignalExtractor.extract_price_target(entry["decision"])
            
            # Outcomes
            realized_return = None
            realized_alpha = None
            
            if not entry["pending"]:
                realized_return = parse_percent(entry["raw"])
                realized_alpha = parse_percent(entry["alpha"])
                horizon_days = parse_days(entry["holding"])
                
            # Check if already exists in DB
            db_entry = db.query(Decision).filter(
                Decision.ticker == ticker,
                Decision.decision_date == date
            ).first()
            
            if db_entry:
                # If existing is pending but log has outcome, update it
                if db_entry.realized_return is None and realized_return is not None:
                    db_entry.realized_return = realized_return
                    db_entry.realized_alpha = realized_alpha
                    db_entry.horizon_days = horizon_days
                    db_entry.reflection = entry.get("reflection")
                    db_entry.raw_json = json.dumps(entry.get("decision"))
                    db.commit()
                    updated_count += 1
            else:
                # Create a new decision
                new_dec = Decision(
                    ticker=ticker,
                    decision_date=date,
                    side=side,
                    confidence=confidence,
                    horizon_days=horizon_days,
                    price_target=price_target,
                    realized_return=realized_return,
                    realized_alpha=realized_alpha,
                    reflection=entry.get("reflection"),
                    raw_json=json.dumps(entry.get("decision"))
                )
                db.add(new_dec)
                db.commit()
                synced_count += 1
                
        logger.info(f"Markdown sync complete: {synced_count} inserted, {updated_count} updated.")
        return {
            "status": "success", 
            "synced_count": synced_count, 
            "updated_count": updated_count,
            "total_entries": len(entries)
        }
    except Exception as e:
        logger.error(f"Error syncing markdown memory log: {str(e)}")
        return {"status": "error", "message": str(e)}


def update_outcomes_for_pending_decisions(db: Session) -> dict:
    """Check for pending SQLite decisions, download outcomes from yfinance, and update DB."""
    try:
        pending_decisions = db.query(Decision).filter(Decision.realized_return == None).all()
        if not pending_decisions:
            return {"status": "success", "resolved_count": 0}
            
        resolved_count = 0
        benchmark = "SPY"
        
        for dec in pending_decisions:
            ticker = dec.ticker
            trade_date = dec.decision_date
            holding_days = dec.horizon_days
            
            try:
                start_dt = datetime.datetime.strptime(trade_date, "%Y-%m-%d")
                end_dt = start_dt + datetime.timedelta(days=holding_days + 14) # Safe window for weekends
                
                # Fetch stock and benchmark prices
                stock_history = yf.Ticker(ticker).history(start=trade_date, end=end_dt.strftime("%Y-%m-%d"))
                bench_history = yf.Ticker(benchmark).history(start=trade_date, end=end_dt.strftime("%Y-%m-%d"))
                
                if len(stock_history) < 2 or len(bench_history) < 2:
                    continue # Not enough trading data yet
                    
                actual_days = min(holding_days, len(stock_history) - 1, len(bench_history) - 1)
                
                # Calculate returns
                p_start = float(stock_history["Close"].iloc[0])
                p_end = float(stock_history["Close"].iloc[actual_days])
                raw_ret = (p_end - p_start) / p_start
                
                b_start = float(bench_history["Close"].iloc[0])
                b_end = float(bench_history["Close"].iloc[actual_days])
                bench_ret = (b_end - b_start) / b_start
                
                alpha_ret = raw_ret - bench_ret
                
                # Update DB record
                dec.realized_return = round(raw_ret, 5)
                dec.realized_alpha = round(alpha_ret, 5)
                dec.horizon_days = int(actual_days)
                dec.reflection = f"Reflected on {datetime.date.today().isoformat()}: Completed holding period of {actual_days} days."
                
                db.commit()
                resolved_count += 1
                logger.info(f"Resolved pending decision outcome for {ticker} on {trade_date}")
            except Exception as item_err:
                logger.warning(f"Failed to fetch outcomes for {ticker} on {trade_date}: {str(item_err)}")
                
        return {"status": "success", "resolved_count": resolved_count}
    except Exception as e:
        logger.error(f"Error updating outcomes: {str(e)}")
        return {"status": "error", "message": str(e)}
