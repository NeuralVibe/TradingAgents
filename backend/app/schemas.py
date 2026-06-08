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


class DecisionResponse(BaseModel):
    id: int
    run_id: Optional[str] = None
    ticker: str
    decision_date: str
    side: str
    confidence: float
    horizon_days: int
    price_target: Optional[float] = None
    realized_return: Optional[float] = None
    realized_alpha: Optional[float] = None
    reflection: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    tickers: Optional[List[str]] = Field(default=None, description="List of tickers to backtest. If empty/None, runs all available tickers.")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(100000.0, description="Initial capital in USD")
    sizing_mode: str = Field("confidence", description="Allocation sizing mode: 'fixed' or 'confidence'")
    slippage: float = Field(0.0005, description="Slippage and trading cost percentage (e.g. 0.0005 = 0.05%)")


class BacktestTrade(BaseModel):
    ticker: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    side: str
    confidence: float
    horizon_days: int
    exit_reason: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    raw_return: float
    alpha_return: Optional[float] = None
    profit: float
    size: float


class BacktestEquityPoint(BaseModel):
    date: str
    portfolio_value: float
    cash: float
    benchmark_value: float


class BacktestSummary(BaseModel):
    cumulative_return: float
    annualized_return: float
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    payoff_ratio: float
    turnover: float
    exposure: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    benchmark_return: float
    alpha: float
    beta: float


class BacktestResponse(BaseModel):
    summary: BacktestSummary
    equity_curve: List[BacktestEquityPoint]
    trades: List[BacktestTrade]


class ParameterSweepRequest(BaseModel):
    tickers: Optional[List[str]] = Field(default=None, description="List of tickers to validate. If empty/None, runs all available tickers.")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(100000.0, description="Initial capital in USD")
    sizing_modes: List[str] = Field(default_factory=lambda: ["fixed", "confidence"])
    slippage_values: List[float] = Field(default_factory=lambda: [0.0, 0.0005, 0.001])
    min_risk_reward_values: List[float] = Field(default_factory=lambda: [1.0, 1.2, 1.5])
    min_price_attractiveness_values: List[float] = Field(default_factory=lambda: [0.25, 0.35, 0.5])
    min_trades: int = Field(3, ge=0)


class WalkForwardRequest(BaseModel):
    tickers: Optional[List[str]] = Field(default=None, description="List of tickers to validate. If empty/None, runs all available tickers.")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(100000.0, description="Initial capital in USD")
    train_window_days: int = Field(252, ge=1)
    test_window_days: int = Field(63, ge=1)
    step_days: int = Field(63, ge=1)
    min_trades_per_window: int = Field(3, ge=0)
    sizing_modes: List[str] = Field(default_factory=lambda: ["fixed", "confidence"])
    slippage_values: List[float] = Field(default_factory=lambda: [0.0, 0.0005, 0.001])
    min_risk_reward_values: List[float] = Field(default_factory=lambda: [1.0, 1.2, 1.5])
    min_price_attractiveness_values: List[float] = Field(default_factory=lambda: [0.25, 0.35, 0.5])


class ValidationSummaryRequest(WalkForwardRequest):
    pass


class ParameterSweepResponse(BaseModel):
    best_parameters: Optional[Dict[str, Any]] = None
    best_summary: Optional[Dict[str, Any]] = None
    results: List[Dict[str, Any]]
    windows: List[Dict[str, Any]]
    risk_flag_counts: Dict[str, int]
    risk_flag_details: List[Dict[str, Any]]
    regime_breakdown: List[Dict[str, Any]]
    ticker_breakdown: List[Dict[str, Any]]
    period_breakdown: List[Dict[str, Any]]
    calculation_basis: Dict[str, Any]


class WalkForwardResponse(BaseModel):
    best_parameters: Optional[Dict[str, Any]] = None
    best_summary: Optional[Dict[str, Any]] = None
    summary: Dict[str, Any]
    results: List[Dict[str, Any]]
    windows: List[Dict[str, Any]]
    risk_flag_counts: Dict[str, int]
    risk_flag_details: List[Dict[str, Any]]
    regime_breakdown: List[Dict[str, Any]]
    ticker_breakdown: List[Dict[str, Any]]
    period_breakdown: List[Dict[str, Any]]
    calculation_basis: Dict[str, Any]


class ValidationSummaryResponse(BaseModel):
    base_summary: Dict[str, Any]
    best_parameters: Optional[Dict[str, Any]] = None
    best_summary: Optional[Dict[str, Any]] = None
    summary: Dict[str, Any]
    results: List[Dict[str, Any]]
    windows: List[Dict[str, Any]]
    risk_flag_counts: Dict[str, int]
    risk_flag_details: List[Dict[str, Any]]
    regime_breakdown: List[Dict[str, Any]]
    ticker_breakdown: List[Dict[str, Any]]
    period_breakdown: List[Dict[str, Any]]
    calculation_basis: Dict[str, Any]


class NewsItem(BaseModel):
    time: str
    title: str
    sentiment: str
    summary: str
    url: Optional[str] = None


class NewsFeedResponse(BaseModel):
    ticker: str
    news: List[NewsItem]


class NewsInterpretRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    news_title: str = Field(..., description="News title")
    news_summary: str = Field(..., description="News body or summary")
    provider: Optional[str] = Field("local", description="LLM provider")
    base_url: Optional[str] = Field(None, description="LLM endpoint URL")
    api_key: Optional[str] = Field(None, description="LLM Authentication API key")
    model_name: Optional[str] = Field(None, description="LLM model identifier")


class NewsInterpretResponse(BaseModel):
    interpretation: str



