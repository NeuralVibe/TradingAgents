import datetime
import asyncio
import pandas as pd
import yfinance as yf
import requests
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from ..schemas import MarketResponse, MarketDataPoint, NewsFeedResponse, NewsItem, NewsInterpretRequest, NewsInterpretResponse
from ..config import settings
from tradingagents.llm_clients import create_llm_client
from langchain_core.messages import SystemMessage, HumanMessage

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
        df = await asyncio.to_thread(stock.history, start=start_str, end=end_str)
        
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


# 1. Human-friendly relative time formatter
def parse_relative_time(pub_date_str: Optional[str]) -> str:
    if not pub_date_str:
        return "알 수 없음"
    try:
        # Expecting format: 2026-05-31T11:44:34Z -> datetime
        date_str = pub_date_str.replace("Z", "+00:00")
        pub_time = datetime.datetime.fromisoformat(date_str)
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - pub_time
        
        seconds = diff.total_seconds()
        if seconds < 0:
            return "방금 전"
        if seconds < 60:
            return "방금 전"
        minutes = seconds / 60
        if minutes < 60:
            return f"{int(minutes)}분 전"
        hours = minutes / 60
        if hours < 24:
            return f"{int(hours)}시간 전"
        days = hours / 24
        return f"{int(days)}일 전"
    except Exception:
        if "T" in pub_date_str:
            return pub_date_str.split("T")[0]
        return pub_date_str

# 2. yfinance Live news fetching and pre-processing
@router.get("/{ticker}/news", response_model=NewsFeedResponse)
async def get_news_feed(ticker: str):
    """Retrieve real-time news feed for the selected stock ticker by pulling from yfinance API.
    Returns exactly one informative error item on empty results or connection errors to adhere to the Anti-Hallucination Protocol.
    """
    ticker_upper = ticker.upper()
    try:
        stock = yf.Ticker(ticker_upper)
        yf_news = await asyncio.to_thread(lambda: stock.news)
        
        if not yf_news:
            return NewsFeedResponse(
                ticker=ticker_upper,
                news=[
                    NewsItem(
                        time="방금 전",
                        title="실시간 뉴스를 불러올 수 없습니다",
                        sentiment="NEUTRAL",
                        summary="현재 이 종목에 대해 등록된 Yahoo Finance 실시간 뉴스가 존재하지 않습니다.",
                        url=""
                    )
                ]
            )
            
        combined_news = []
        for item in yf_news:
            content = item.get("content", {})
            if not content:
                continue
                
            title = content.get("title", "")
            summary = content.get("summary") or content.get("description") or ""
            pub_date = content.get("pubDate")
            
            # parse url safely
            url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl")
            url = ""
            if isinstance(url_obj, dict):
                url = url_obj.get("url", "")
            elif isinstance(url_obj, str):
                url = url_obj
                
            # Formatting human relative time
            time_str = parse_relative_time(pub_date)
            
            # Pure rule-based sentiment classifier
            text_to_analyze = (title + " " + summary).lower()
            bullish_keywords = ["up", "gain", "rise", "surge", "bull", "growth", "positive", "buy", "higher", "profit", "beat", "upgrade", "soar", "rally", "success"]
            bearish_keywords = ["down", "fall", "drop", "plunge", "bear", "negative", "sell", "lower", "loss", "miss", "downgrade", "decline", "slump", "deficit", "warn"]
            
            bull_count = sum(1 for w in bullish_keywords if w in text_to_analyze)
            bear_count = sum(1 for w in bearish_keywords if w in text_to_analyze)
            
            if bull_count > bear_count:
                sentiment = "BULLISH"
            elif bear_count > bull_count:
                sentiment = "BEARISH"
            else:
                sentiment = "NEUTRAL"
                
            combined_news.append(
                NewsItem(
                    time=time_str,
                    title=title,
                    sentiment=sentiment,
                    summary=summary,
                    url=url or ""
                )
            )
            
        if not combined_news:
            return NewsFeedResponse(
                ticker=ticker_upper,
                news=[
                    NewsItem(
                        time="방금 전",
                        title="실시간 뉴스를 불러올 수 없습니다",
                        sentiment="NEUTRAL",
                        summary="현재 분석 가능한 Yahoo Finance 실시간 뉴스가 존재하지 않습니다.",
                        url=""
                    )
                ]
            )
            
        return NewsFeedResponse(ticker=ticker_upper, news=combined_news[:8])
        
    except Exception as e:
        # Strictly return a single informative error block per Anti-Hallucination Protocol
        return NewsFeedResponse(
            ticker=ticker_upper,
            news=[
                NewsItem(
                    time="방금 전",
                    title="실시간 뉴스를 불러올 수 없습니다",
                    sentiment="NEUTRAL",
                    summary="Yahoo Finance API 연결 지연 중입니다. 잠시 후 다시 시도해 주세요.",
                    url=""
                )
            ]
        )

# 3. News Router for AI News Interpretation
news_router = APIRouter(prefix="/news", tags=["news"])

@news_router.post("/interpret", response_model=NewsInterpretResponse)
async def interpret_news(payload: NewsInterpretRequest):
    """Call dynamic LLM to analyze the impact of the selected news story on the given stock."""
    ticker = payload.ticker.upper()
    title = payload.news_title
    summary = payload.news_summary
    
    # Extract LLM configurations from payload, fallback to environment/default settings if omitted
    provider = payload.provider or "local"
    model_name = payload.model_name or settings.LOCAL_LLM_MODEL
    base_url = payload.base_url or settings.LOCAL_LLM_URL
    api_key = payload.api_key or "lm-studio"
    
    prompt = (
        f"주어진 뉴스가 {ticker}의 주가 및 향후 전망에 미칠 영향을 분석하고, "
        f"호재/악재 여부를 판별하여 3~4줄의 마크다운 형식으로 명확히 해설해라.\n\n"
        f"뉴스 제목: {title}\n"
        f"뉴스 요약: {summary}\n"
    )
    
    try:
        # Symmetrical dynamic initialization identical to backtest simulation nodes
        client = create_llm_client(
            provider=provider,
            model=model_name,
            base_url=base_url,
            api_key=api_key
        )
        llm = client.get_llm()
        
        # Invoke via LangChain message protocols
        messages = [
            SystemMessage(content="당신은 세계적인 헤지펀드의 수석 AI 금융 분석가입니다. 마크다운 형식을 지켜 친절하고 정교하게 한국어로 설명하십시오."),
            HumanMessage(content=prompt)
        ]
        
        response = await asyncio.to_thread(llm.invoke, messages)
        content = response.content
        if content:
            return NewsInterpretResponse(interpretation=content.strip())
            
        raise HTTPException(status_code=500, detail="LLM 응답 실패")
        
    except Exception as e:
        # Avoid mock/hallucinated predictions. Advise connection offline per Anti-Hallucination Protocol.
        fallback_interpretation = (
            f"### ⚠️ [AI 분석 지연 안내] {ticker} 분석 보고서\n\n"
            f"- **오류 내용**: 현재 AI 분석 모델 엔진(LLM)과의 연결이 끊겼거나 응답이 지연되고 있습니다.\n"
            f"- **안내 가이드**: 백엔드 로컬 LLM 서버(LMStudio) 작동 상태를 점검해 주십시오. 연결이 복구되면 즉시 정상적인 AI 해설을 받아보실 수 있습니다."
        )
        return NewsInterpretResponse(interpretation=fallback_interpretation)


