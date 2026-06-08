import json
from datetime import datetime

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import settings
from backend.app.database import Base, get_db
from backend.app.models import Decision, SimulationRun
from backend.app.quant_engine import BacktestEngine
from backend.app.routers import backtest, market, runs
from backend.app.routers.market import news_router


def _structured_trade_signal(
    ticker: str = "AAPL",
    as_of_date: str = "2026-01-05",
    side: str = "BUY",
    risk_reward: float = 1.8,
    attractiveness: float = 0.7,
    risk_flags: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "decision_text": "**Rating**: Hold",
            "trade_signal": {
                "ticker": ticker,
                "as_of_date": as_of_date,
                "action": side,
                "confidence": 0.82,
                "expected_holding_days": 3,
                "stop_loss": 95.0,
                "take_profit": 112.0,
                "risk_reward_ratio": risk_reward,
                "price_attractiveness_score": attractiveness,
                "volatility_regime": "normal",
                "risk_flags": risk_flags or ["api_contract_flag"],
                "calculation_basis": {
                    "quant_price_setup": {
                        "selected_stop_method": "atr_stop",
                    }
                },
            },
        }
    )


def _price_history() -> pd.DataFrame:
    dates = pd.to_datetime(
        [
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
            "2026-01-08",
            "2026-01-09",
            "2026-01-12",
        ]
    )
    return pd.DataFrame(
        {
            "AAPL": [100.0, 101.0, 104.0, 107.0, 109.0, 111.0],
            "MSFT": [200.0, 201.0, 202.0, 203.0, 204.0, 205.0],
            "SPY": [400.0, 401.0, 402.0, 403.0, 404.0, 405.0],
        },
        index=dates,
    )


def _market_history() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=45, freq="D")
    close = pd.Series(range(100, 145), dtype="float")
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": [1_000_000 + i * 1000 for i in range(len(dates))],
        },
        index=dates,
    )


class _FakeTicker:
    def __init__(self, ticker: str):
        self.ticker = ticker

    def history(self, *args, **kwargs):
        return _market_history()

    @property
    def news(self):
        return [
            {
                "content": {
                    "title": "AAPL shares rise after earnings beat",
                    "summary": "Revenue growth and profit beat expectations.",
                    "pubDate": "2026-01-10T12:00:00Z",
                    "canonicalUrl": {"url": "https://example.test/aapl"},
                }
            }
        ]


class _FakeLLM:
    def invoke(self, messages):
        class _Response:
            content = "Mock interpretation: earnings news is constructive but price risk remains."

        return _Response()


class _FakeLLMClient:
    def get_llm(self):
        return _FakeLLM()


@pytest.fixture()
def api_contract_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def fake_fetch_price_history(tickers, start_date, end_date):
        prices = _price_history()
        columns = [ticker for ticker in tickers if ticker in prices.columns]
        return prices.loc[pd.to_datetime(start_date) : pd.to_datetime(end_date), columns]

    monkeypatch.setattr(
        BacktestEngine,
        "fetch_price_history",
        staticmethod(fake_fetch_price_history),
    )
    monkeypatch.setattr(
        BacktestEngine,
        "fetch_ohlc_history",
        staticmethod(lambda tickers, start_date, end_date: pd.DataFrame()),
    )
    monkeypatch.setattr(
        backtest,
        "update_outcomes_for_pending_decisions",
        lambda db: {"status": "success", "resolved_count": 0},
    )
    monkeypatch.setattr(
        backtest,
        "sync_markdown_log_to_db",
        lambda db: {"status": "success", "synced_count": 0, "updated_count": 0},
    )
    monkeypatch.setattr(market.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(market, "create_llm_client", lambda **kwargs: _FakeLLMClient())

    seed_session = TestingSessionLocal()
    try:
        seed_session.add_all(
            [
                Decision(
                    ticker="AAPL",
                    decision_date="2026-01-05",
                    side="HOLD",
                    confidence=0.1,
                    horizon_days=1,
                    price_target=None,
                    realized_return=0.04,
                    realized_alpha=0.01,
                    raw_json=_structured_trade_signal(),
                ),
                Decision(
                    ticker="MSFT",
                    decision_date="2026-01-05",
                    side="BUY",
                    confidence=0.7,
                    horizon_days=3,
                    price_target=210.0,
                    realized_return=-0.02,
                    realized_alpha=None,
                    raw_json=None,
                ),
                SimulationRun(
                    id="run-pending",
                    ticker="AAPL",
                    trade_date="2026-01-05",
                    status="PENDING",
                    progress=12.0,
                    current_step="queued",
                    logs="[]",
                    recommendation="HOLD",
                    created_at=datetime(2026, 1, 5, 9, 0, 0),
                    updated_at=datetime(2026, 1, 5, 9, 0, 0),
                ),
                SimulationRun(
                    id="run-complete",
                    ticker="MSFT",
                    trade_date="2026-01-05",
                    status="COMPLETED",
                    progress=86.0,
                    current_step="done",
                    logs="[]",
                    recommendation="BUY",
                    created_at=datetime(2026, 1, 5, 10, 0, 0),
                    updated_at=datetime(2026, 1, 5, 10, 0, 0),
                ),
            ]
        )
        seed_session.commit()
    finally:
        seed_session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(runs.router, prefix=settings.API_V1_STR)
    app.include_router(market.router, prefix=settings.API_V1_STR)
    app.include_router(news_router, prefix=settings.API_V1_STR)
    app.include_router(backtest.router, prefix=settings.API_V1_STR)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_public_api_prefix_exposes_core_router_contracts(api_contract_client):
    assert api_contract_client.get("/api/runs").status_code == 200
    assert api_contract_client.get("/api/performance/decisions").status_code == 200
    assert api_contract_client.get("/api/performance/summary").status_code == 200
    assert api_contract_client.get("/api/market/AAPL", params={"lookback_days": 10}).status_code == 200


def test_backtest_api_uses_structured_signal_without_exposing_internal_metadata(api_contract_client):
    response = api_contract_client.post(
        "/api/performance/backtest",
        json={
            "tickers": ["AAPL"],
            "start_date": "2026-01-05",
            "end_date": "2026-01-12",
            "initial_capital": 100000.0,
            "sizing_mode": "fixed",
            "slippage": 0.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_trades"] == 1
    trade = payload["trades"][0]
    assert trade["ticker"] == "AAPL"
    assert trade["entry_date"] == "2026-01-06"
    assert trade["side"] == "BUY"
    assert trade["stop_loss"] == 95.0
    assert trade["take_profit"] == 112.0
    assert "signal_risk_flags" not in trade
    assert "signal_calculation_basis" not in trade


def test_validation_summary_api_works_through_main_prefix_with_mocked_dependencies(api_contract_client):
    response = api_contract_client.post(
        "/api/performance/validation-summary",
        json={
            "tickers": ["AAPL"],
            "start_date": "2026-01-05",
            "end_date": "2026-01-12",
            "initial_capital": 100000.0,
            "train_window_days": 2,
            "test_window_days": 2,
            "step_days": 2,
            "min_trades_per_window": 0,
            "sizing_modes": ["fixed"],
            "slippage_values": [0.0],
            "min_risk_reward_values": [1.0],
            "min_price_attractiveness_values": [0.2],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["calculation_basis"]["signal_count"] == 1
    assert payload["risk_flag_counts"]["api_contract_flag"] == 1
    assert "base_summary" in payload
    assert "summary" in payload


def test_legacy_performance_endpoints_use_isolated_database(api_contract_client):
    summary = api_contract_client.get("/api/performance/summary").json()

    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["avg_alpha"] == 0.01

    by_ticker = api_contract_client.get("/api/performance/by-ticker").json()
    assert {row["ticker"] for row in by_ticker} == {"AAPL", "MSFT"}

    decisions = api_contract_client.get(
        "/api/performance/decisions",
        params={"ticker": "aapl", "limit": 10},
    ).json()
    assert len(decisions) == 1
    assert decisions[0]["ticker"] == "AAPL"


def test_runs_api_lists_gets_cancels_and_deletes_without_worker(api_contract_client):
    listed = api_contract_client.get("/api/runs").json()
    completed = next(row for row in listed if row["id"] == "run-complete")
    assert completed["progress"] == 100.0

    fetched = api_contract_client.get("/api/runs/run-pending")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "PENDING"

    cancelled = api_contract_client.delete("/api/runs/run-pending")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    deleted = api_contract_client.delete("/api/runs/run-complete")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "DELETED"
    assert api_contract_client.get("/api/runs/run-complete").status_code == 404


def test_create_run_api_uses_service_boundary_without_starting_background_worker(
    api_contract_client,
    monkeypatch,
):
    async def fake_add_run(run_id, ticker, trade_date, config_override, db):
        run = SimulationRun(
            id=run_id,
            ticker=ticker,
            trade_date=trade_date,
            status="PENDING",
            progress=0.0,
            current_step="queued",
            logs="[]",
            recommendation="HOLD",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr(runs.simulation_service, "add_run", fake_add_run)

    response = api_contract_client.post(
        "/api/runs",
        json={
            "ticker": "nvda",
            "trade_date": "2026-01-06",
            "llm_provider": "local",
            "llm_model": "mock-model",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "NVDA"
    assert payload["status"] == "PENDING"


def test_market_and_news_endpoints_run_with_mocked_external_dependencies(api_contract_client):
    market_response = api_contract_client.get(
        "/api/market/AAPL",
        params={"end_date": "2026-02-14", "lookback_days": 10},
    )
    assert market_response.status_code == 200
    market_payload = market_response.json()
    assert market_payload["ticker"] == "AAPL"
    assert len(market_payload["data"]) == 10
    assert {"sma_50", "sma_200", "ema_10", "rsi", "macd"} <= set(market_payload["indicators"])

    news_response = api_contract_client.get("/api/market/AAPL/news")
    assert news_response.status_code == 200
    news_payload = news_response.json()
    assert news_payload["ticker"] == "AAPL"
    assert news_payload["news"][0]["sentiment"] == "BULLISH"


def test_news_interpret_endpoint_uses_mocked_llm_client(api_contract_client):
    response = api_contract_client.post(
        "/api/news/interpret",
        json={
            "ticker": "AAPL",
            "news_title": "AAPL earnings beat expectations",
            "news_summary": "Revenue growth was stronger than expected.",
            "provider": "local",
            "base_url": "http://localhost:1234",
            "api_key": "test-key",
            "model_name": "mock-model",
        },
    )

    assert response.status_code == 200
    assert "Mock interpretation" in response.json()["interpretation"]
