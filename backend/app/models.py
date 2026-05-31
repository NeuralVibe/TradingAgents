import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, Integer
from .database import Base

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(String, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    trade_date = Column(String, nullable=False)
    status = Column(String, default="PENDING", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED
    progress = Column(Float, default=0.0, nullable=False)
    current_step = Column(String, default="대기 중", nullable=False) # e.g. "애널리스트 분석", "토론", "최종 판단"
    logs = Column(Text, default="[]")  # JSON array of logs
    result = Column(Text, nullable=True)  # JSON representation of final AgentState
    decision = Column(Text, nullable=True)  # Final decision text
    recommendation = Column(String, default="HOLD")  # BUY, SELL, HOLD
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(String, index=True, nullable=True)
    ticker = Column(String, index=True, nullable=False)
    decision_date = Column(String, index=True, nullable=False)
    side = Column(String, nullable=False)  # BUY, SELL, HOLD
    confidence = Column(Float, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    price_target = Column(Float, nullable=True)
    realized_return = Column(Float, nullable=True)
    realized_alpha = Column(Float, nullable=True)
    reflection = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

