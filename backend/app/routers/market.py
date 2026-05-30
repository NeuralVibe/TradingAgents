import datetime
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from ..schemas import MarketResponse, MarketDataPoint

router = APIRouter(prefix="/market", tags=["market"])

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SMA, EMA, RSI, and MACD indicators using pure pandas."""
    # Ensure sorted by date
    df = df.sort_index()
    
    # Moving Averages
    df["sma_50"] = df["Close"].rolling(window=min(50, len(df))).mean()
    df["sma_200"] = df["Close"].rolling(window=min(200, len(df))).mean()
    df["ema_10"] = df["Close"].ewm(span=min(10, len(df)), adjust=False).mean()
    
    # RSI (Relative Strength Index)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9) # Avoid zero division
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # MACD
    ema_12 = df["Close"].ewm(span=min(12, len(df)), adjust=False).mean()
    ema_26 = df["Close"].ewm(span=min(26, len(df)), adjust=False).mean()
    df["macd_line"] = ema_12 - ema_26
    df["macd_signal"] = df["macd_line"].ewm(span=min(9, len(df)), adjust=False).mean()
    df["macd_histogram"] = df["macd_line"] - df["macd_signal"]
    
    return df

@router.get("/{ticker}", response_model=MarketResponse)
async def get_market_data(
    ticker: str,
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD (default today)"),
    lookback_days: int = Query(180, description="Number of days of history to fetch")
):
    """Retrieve yfinance stock OHLCV data along with pre-calculated technical indicators (RSI, MACD, SMAs)."""
    try:
        ticker = ticker.upper()
        
        # Determine date range
        if end_date:
            try:
                end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="날짜 포맷이 올바르지 않습니다. YYYY-MM-DD 형식이어야 합니다.")
        else:
            end_dt = datetime.datetime.today()
            
        start_dt = end_dt - datetime.timedelta(days=lookback_days + 30) # Fetch slightly extra to stabilize indicators
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = (end_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d") # Include end date
        
        # Fetch stock data
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_str, end=end_str)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"종목 '{ticker}'의 데이터를 찾을 수 없거나 거래 정지 상태입니다.")
            
        # Clean and calculate indicators
        df = calculate_technical_indicators(df)
        
        # Filter back to exactly requested lookback timeframe
        df = df.iloc[-lookback_days:]
        
        # Prepare list of data points
        data_points = []
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            data_points.append(
                MarketDataPoint(
                    date=date_str,
                    open=round(float(row["Open"]), 2),
                    high=round(float(row["High"]), 2),
                    low=round(float(row["Low"]), 2),
                    close=round(float(row["Close"]), 2),
                    volume=int(row["Volume"])
                )
            )
            
        # Prepare indicators dictionary for front-end usage
        indicators = {
            "sma_50": {idx.strftime("%Y-%m-%d"): round(float(val), 2) for idx, val in df["sma_50"].items() if not pd.isna(val)},
            "sma_200": {idx.strftime("%Y-%m-%d"): round(float(val), 2) for idx, val in df["sma_200"].items() if not pd.isna(val)},
            "ema_10": {idx.strftime("%Y-%m-%d"): round(float(val), 2) for idx, val in df["ema_10"].items() if not pd.isna(val)},
            "rsi": {idx.strftime("%Y-%m-%d"): round(float(val), 2) for idx, val in df["rsi"].items() if not pd.isna(val)},
            "macd": {
                idx.strftime("%Y-%m-%d"): {
                    "line": round(float(row["macd_line"]), 4),
                    "signal": round(float(row["macd_signal"]), 4),
                    "histogram": round(float(row["macd_histogram"]), 4)
                }
                for idx, row in df.iterrows() if not pd.isna(row["macd_line"])
            }
        }
        
        return MarketResponse(
            ticker=ticker,
            data=data_points,
            indicators=indicators
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시장 데이터 로드 중 오류 발생: {str(e)}")
