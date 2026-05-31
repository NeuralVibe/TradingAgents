import io
import logging
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from starlette.responses import StreamingResponse

from ..database import get_db
from ..models import Decision
from ..schemas import (
    DecisionResponse, 
    BacktestRequest, 
    BacktestResponse, 
    BacktestSummary,
    BacktestEquityPoint,
    BacktestTrade
)
from ..quant_engine import BacktestEngine
from ..sync_helper import sync_markdown_log_to_db, update_outcomes_for_pending_decisions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["performance"])


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest(payload: BacktestRequest, db: Session = Depends(get_db)):
    """Run a chronological vector portfolio backtest based on historical agent decisions stored in the database."""
    # Build query filter
    query = db.query(Decision)
    
    if payload.tickers and len(payload.tickers) > 0:
        tickers_upper = [t.upper() for t in payload.tickers]
        query = query.filter(Decision.ticker.in_(tickers_upper))
        
    query = query.filter(
        Decision.decision_date >= payload.start_date,
        Decision.decision_date <= payload.end_date
    )
    
    # Sort chronologically
    decisions = query.order_by(Decision.decision_date.asc()).all()
    
    # Map to standard signal dictionaries
    signals = []
    for d in decisions:
        signals.append({
            "ticker": d.ticker,
            "date": d.decision_date,
            "side": d.side,
            "confidence": d.confidence,
            "horizon_days": d.horizon_days,
            "price_target": d.price_target
        })
        
    # Execute backtest simulation
    result = BacktestEngine.run_portfolio_backtest(
        signals=signals,
        start_date=payload.start_date,
        end_date=payload.end_date,
        initial_capital=payload.initial_capital,
        sizing_mode=payload.sizing_mode,
        slippage=payload.slippage
    )
    
    # Convert result dictionaries to schemas
    eq_curve = [BacktestEquityPoint(**eq) for eq in result["equity_curve"]]
    trades_list = [BacktestTrade(**tr) for tr in result["trades"]]
    summary_data = BacktestSummary(**result["summary"])
    
    return BacktestResponse(
        summary=summary_data,
        equity_curve=eq_curve,
        trades=trades_list
    )


@router.post("/sync")
def sync_data(db: Session = Depends(get_db)):
    """Trigger synchronization between Markdown memory logs and the SQLite decisions table, downloading recent outcomes."""
    # 1. Sync legacy markdown
    sync_res = sync_markdown_log_to_db(db)
    # 2. Update price outcomes for pending
    outcome_res = update_outcomes_for_pending_decisions(db)
    
    return {
        "markdown_sync": sync_res,
        "outcomes_resolved": outcome_res["resolved_count"],
        "status": "success"
    }


@router.get("/summary")
def get_performance_summary(db: Session = Depends(get_db)):
    """Get the overall performance statistics of all realized agent decisions."""
    # First, run a lightweight outcome check to auto-update completed decisions
    try:
        update_outcomes_for_pending_decisions(db)
    except Exception as e:
        logger.warning(f"Lightweight outcome check failed: {str(e)}")

    # Retrieve all decisions with outcomes
    decisions = db.query(Decision).filter(Decision.realized_return != None).all()
    
    if not decisions:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "avg_alpha": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_tickers": 0
        }
        
    winning = [d for d in decisions if d.realized_return > 0]
    total_trades = len(decisions)
    win_rate = len(winning) / total_trades if total_trades > 0 else 0.0
    
    avg_return = sum([d.realized_return for d in decisions]) / total_trades
    avg_alpha = sum([d.realized_alpha for d in decisions if d.realized_alpha is not None]) / total_trades
    
    tickers = list(set([d.ticker for d in decisions]))
    
    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 4),
        "avg_return": round(avg_return, 4),
        "avg_alpha": round(avg_alpha, 4),
        "winning_trades": len(winning),
        "losing_trades": total_trades - len(winning),
        "total_tickers": len(tickers)
    }


@router.get("/by-ticker")
def get_performance_by_ticker(db: Session = Depends(get_db)):
    """Get the performance summary aggregated by ticker."""
    decisions = db.query(Decision).filter(Decision.realized_return != None).all()
    
    if not decisions:
        return []
        
    by_ticker = {}
    for d in decisions:
        by_ticker.setdefault(d.ticker, []).append(d)
        
    results = []
    for ticker, decs in by_ticker.items():
        winning = [d for d in decs if d.realized_return > 0]
        total = len(decs)
        win_rate = len(winning) / total if total > 0 else 0.0
        cum_ret = 1.0
        for d in decs:
            cum_ret *= (1.0 + d.realized_return)
        cum_ret = cum_ret - 1.0
        
        results.append({
            "ticker": ticker,
            "total_trades": total,
            "win_rate": round(win_rate, 4),
            "avg_return": round(sum([d.realized_return for d in decs]) / total, 4),
            "cumulative_return": round(cum_ret, 4),
            "winning_trades": len(winning),
            "losing_trades": total - len(winning)
        })
        
    # Sort by cumulative return descending
    results.sort(key=lambda x: x["cumulative_return"], reverse=True)
    return results


@router.get("/decisions", response_model=List[DecisionResponse])
def list_stored_decisions(
    ticker: Optional[str] = None,
    side: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve stored decisions from the database with optional filtering and pagination."""
    query = db.query(Decision)
    
    if ticker:
        query = query.filter(Decision.ticker == ticker.upper())
    if side:
        query = query.filter(Decision.side == side.upper())
        
    decisions = query.order_by(Decision.decision_date.desc()).offset(offset).limit(limit).all()
    return decisions


@router.get("/decisions/export")
def export_decisions(format: str = Query("csv", regex="^(csv|parquet)$"), db: Session = Depends(get_db)):
    """Export all stored decisions as a downloadable CSV or Parquet stream file."""
    decisions = db.query(Decision).all()
    
    if not decisions:
        raise HTTPException(status_code=404, detail="Export할 데이터가 존재하지 않습니다.")
        
    # Map to list of dicts
    data = []
    for d in decisions:
        data.append({
            "id": d.id,
            "run_id": d.run_id,
            "ticker": d.ticker,
            "decision_date": d.decision_date,
            "side": d.side,
            "confidence": d.confidence,
            "horizon_days": d.horizon_days,
            "price_target": d.price_target,
            "realized_return": d.realized_return,
            "realized_alpha": d.realized_alpha,
            "reflection": d.reflection,
            "created_at": d.created_at
        })
        
    df = pd.DataFrame(data)
    
    if format == "parquet":
        try:
            import pyarrow
            # Export to parquet in-memory
            output = io.BytesIO()
            df.to_parquet(output, index=False)
            output.seek(0)
            return StreamingResponse(
                output, 
                media_type="application/octet-stream",
                headers={"Content-Disposition": "attachment; filename=trading_decisions.parquet"}
            )
        except ImportError:
            raise HTTPException(
                status_code=400, 
                detail="시스템에 'pyarrow' 패키지가 설치되어 있지 않아 Parquet 내보내기를 지원하지 않습니다. CSV 형식을 이용해 주세요."
            )
    else: # csv
        output = io.StringIO()
        df.to_csv(output, index=False)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")), 
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=trading_decisions.csv"}
        )
