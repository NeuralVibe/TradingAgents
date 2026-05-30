from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class RunCreate(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g. AAPL, NVDA, TSLA)")
    trade_date: str = Field(..., description="Simulation date in YYYY-MM-DD format")
    llm_provider: str = Field("local", description="LLM provider: 'local' (LMStudio) or 'openai'")
    llm_model: str = Field("qwen3.6-27b-uncensored-heretic-v2-native-mtp-preserved", description="LLM model name")
    max_debate_rounds: int = Field(1, description="Max debate rounds")
    max_risk_discuss_rounds: int = Field(1, description="Max risk debate rounds")

class RunLog(BaseModel):
    timestamp: datetime
    step: str
    message: str
    level: str = "INFO"

class RunResponse(BaseModel):
    id: str
    ticker: str
    trade_date: str
    status: str
    progress: float
    current_step: str
    logs: str  # JSON array string or we can deserialize it
    result: Optional[str] = None  # JSON serialization of full_state
    decision: Optional[str] = None
    recommendation: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MarketDataPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

class MarketResponse(BaseModel):
    ticker: str
    data: List[MarketDataPoint]
    indicators: Optional[Dict[str, Any]] = None
