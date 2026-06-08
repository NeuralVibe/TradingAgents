import json

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import get_db
from backend.app.models import Decision
from backend.app.quant_engine import BacktestEngine
from backend.app.routers import backtest
from backend.app.validation_engine import POINT_IN_TIME_RISK_FLAGS


def _api_price_frame():
    dates = pd.date_range("2026-01-01", "2026-03-31", freq="D")
    steps = np.arange(len(dates))
    return pd.DataFrame(
        {
            "AAPL": 100.0 + steps * 0.35,
            "MSFT": 200.0 + steps * 0.15,
            "SPY": 400.0 + steps * 0.1,
        },
        index=dates,
    )


def _patch_api_prices(monkeypatch):
    prices = _api_price_frame()

    def fake_fetch_price_history(tickers, start_date, end_date):
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


def _structured_trade_signal(
    ticker,
    date,
    risk_reward,
    attractiveness,
    risk_flags=None,
):
    return json.dumps(
        {
            "trade_signal": {
                "ticker": ticker,
                "as_of_date": date,
                "action": "BUY",
                "confidence": 0.8,
                "expected_holding_days": 5,
                "risk_reward_ratio": risk_reward,
                "price_attractiveness_score": attractiveness,
                "volatility_regime": "normal",
                "risk_flags": risk_flags or [],
                "calculation_basis": {
                    "quant_price_setup": {
                        "selected_stop_method": "atr_stop",
                    }
                },
            }
        }
    )


def _seed_decisions(session):
    session.add_all(
        [
            Decision(
                ticker="AAPL",
                decision_date="2026-01-05",
                side="HOLD",
                confidence=0.1,
                horizon_days=1,
                price_target=None,
                raw_json=_structured_trade_signal(
                    "AAPL",
                    "2026-01-05",
                    risk_reward=1.6,
                    attractiveness=0.7,
                    risk_flags=["structured_flag"],
                ),
            ),
            Decision(
                ticker="AAPL",
                decision_date="2026-01-20",
                side="HOLD",
                confidence=0.1,
                horizon_days=1,
                price_target=None,
                raw_json=_structured_trade_signal(
                    "AAPL",
                    "2026-01-20",
                    risk_reward=0.8,
                    attractiveness=0.7,
                ),
            ),
            Decision(
                ticker="MSFT",
                decision_date="2026-01-25",
                side="HOLD",
                confidence=0.1,
                horizon_days=1,
                price_target=None,
                raw_json=_structured_trade_signal(
                    "MSFT",
                    "2026-01-25",
                    risk_reward=1.5,
                    attractiveness=0.1,
                    risk_flags=["near_resistance"],
                ),
            ),
        ]
    )
    session.commit()


@pytest.fixture()
def validation_api_client(monkeypatch):
    _patch_api_prices(monkeypatch)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Decision.__table__.create(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    seed_session = TestingSessionLocal()
    try:
        _seed_decisions(seed_session)
    finally:
        seed_session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(backtest.router)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def _base_payload(**overrides):
    payload = {
        "tickers": None,
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "initial_capital": 100000.0,
        "sizing_modes": ["fixed"],
        "slippage_values": [0.0],
        "min_risk_reward_values": [1.2],
        "min_price_attractiveness_values": [0.3],
    }
    payload.update(overrides)
    return payload


def test_walk_forward_endpoint_returns_validation_shape(validation_api_client):
    response = validation_api_client.post(
        "/performance/walk-forward",
        json=_base_payload(
            train_window_days=15,
            test_window_days=15,
            step_days=15,
            min_trades_per_window=0,
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert "windows" in data
    assert "summary" in data
    assert "risk_flag_counts" in data
    assert "calculation_basis" in data
    assert data["summary"]["total_windows"] == len(data["windows"])


def test_parameter_sweep_endpoint_prefers_structured_raw_json_and_filters(validation_api_client):
    response = validation_api_client.post(
        "/performance/parameter-sweep",
        json=_base_payload(tickers=["AAPL"], min_trades=0),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["best_parameters"] is not None
    assert data["best_summary"]["total_trades"] > 0
    assert data["calculation_basis"]["signal_count"] == 2
    assert data["risk_flag_counts"]["structured_flag"] == 1
    assert data["risk_flag_counts"]["filtered_low_risk_reward"] == 1

    by_flag = {row["flag"]: row for row in data["risk_flag_details"]}
    assert by_flag["structured_flag"]["affected_trade_count"] == 1
    assert by_flag["filtered_low_risk_reward"]["count"] == 1
    assert by_flag["filtered_low_risk_reward"]["affected_trade_count"] == 0


def test_validation_summary_endpoint_returns_aggregate_sections(validation_api_client):
    response = validation_api_client.post(
        "/performance/validation-summary",
        json=_base_payload(
            train_window_days=15,
            test_window_days=15,
            step_days=15,
            min_trades_per_window=0,
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert "base_summary" in data
    assert "summary" in data
    assert "risk_flag_details" in data
    assert "regime_breakdown" in data
    assert "ticker_breakdown" in data

    for flag in POINT_IN_TIME_RISK_FLAGS:
        assert flag in data["risk_flag_counts"]


def test_validation_api_applies_ticker_filter(validation_api_client):
    response = validation_api_client.post(
        "/performance/parameter-sweep",
        json=_base_payload(tickers=["MSFT"], min_trades=0),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["calculation_basis"]["signal_count"] == 1
    assert data["risk_flag_counts"]["filtered_low_price_attractiveness"] == 1
    tickers = {row["ticker"] for row in data["ticker_breakdown"]}
    assert tickers <= {"MSFT"}
