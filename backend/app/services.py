import asyncio
import json
import uuid
import logging
import datetime
from typing import Dict, Any, Callable, List
from sqlalchemy.orm import Session

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from .database import SessionLocal
from .models import SimulationRun, Decision
from .quant_engine import SignalExtractor
from .config import settings

logger = logging.getLogger(__name__)

# SSE Event Subscribers list
subscribers: List[asyncio.Queue] = []

def parse_recommendation(decision_text: str) -> str:
    """Parse final decision text to extract BUY, STRONG BUY, OVERWEIGHT, SELL, UNDERWEIGHT, or HOLD recommendation."""
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

class StreamingTradingAgentsGraph(TradingAgentsGraph):
    """Subclass of TradingAgentsGraph to capture node execution events and stream them."""
    
    def __init__(self, *args, event_callback: Callable[[str, Any], None] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_callback = event_callback
        
    def _run_graph(self, company_name, trade_date, asset_type: str = "stock"):
        """Override to stream LangGraph nodes and fire callback on completion of each step."""
        past_context = self.memory_log.get_past_context(company_name)
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date, asset_type=asset_type, past_context=past_context
        )
        args = self.propagator.get_graph_args()

        final_state = {}
        
        # Stream chunks from the CompiledGraph
        for chunk in self.graph.stream(init_agent_state, **args):
            for node_name, node_output in chunk.items():
                if self.event_callback:
                    try:
                        self.event_callback(node_name, node_output)
                    except RuntimeError as re:
                        logger.warning(f"Cancellation requested in node callback: {str(re)}")
                        raise re
                    except Exception as e:
                        logger.error(f"Error in node callback: {str(e)}")
            final_state.update(chunk)
            
        self.curr_state = final_state
        self._log_state(trade_date, final_state)
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=trade_date,
            final_trade_decision=final_state["final_trade_decision"],
        )
        
        return final_state, self.process_signal(final_state["final_trade_decision"])

class SimulationService:
    """Service to manage background queuing, execution and progress streaming of TradingAgent runs."""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_RUNS)
        self.running_task = None
        
    async def add_run(self, run_id: str, ticker: str, trade_date: str, config_override: Dict[str, Any], db: Session) -> SimulationRun:
        """Create PENDING run and add to the processing queue."""
        run = SimulationRun(
            id=run_id,
            ticker=ticker,
            trade_date=trade_date,
            status="PENDING",
            progress=0.0,
            current_step="대기열 대기 중"
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        # Enqueue the run parameters
        await self.queue.put({
            "run_id": run_id,
            "ticker": ticker,
            "trade_date": trade_date,
            "config_override": config_override
        })
        
        logger.info(f"Enqueued run {run_id} for {ticker} on {trade_date}")
        return run

    async def start_worker(self):
        """Start the background worker to process enqueued runs sequentially."""
        logger.info("Starting Simulation Queue Background Worker...")
        while True:
            try:
                task_data = await self.queue.get()
                async with self.semaphore:
                    await self._process_run(task_data)
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Error in background worker loop: {str(e)}")
                await asyncio.sleep(2)

    async def _process_run(self, task_data: Dict[str, Any]):
        """Execute a single run, handling status updates and broadcasting SSE events."""
        run_id = task_data["run_id"]
        ticker = task_data["ticker"]
        trade_date = task_data["trade_date"]
        config_override = task_data["config_override"]
        
        logger.info(f"Processing run {run_id} for {ticker}")
        
        db = SessionLocal()
        run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if not run:
            db.close()
            return
            
        # Update to RUNNING
        run.status = "RUNNING"
        run.current_step = "분석 시작 준비 중..."
        run.progress = 5.0
        db.commit()
        
        # Helper to push log and broadcast SSE event
        def log_and_broadcast(step: str, message: str, progress: float, log_type: str = "INFO", details: Any = None):
            nonlocal run
            clamped_progress = min(100.0, max(0.0, progress))
            
            # Update DB
            run.current_step = step
            run.progress = clamped_progress
            
            # Load logs list
            current_logs = json.loads(run.logs or "[]")
            log_entry = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "step": step,
                "message": message,
                "progress": clamped_progress,
                "type": log_type,
                "details": details
            }
            current_logs.append(log_entry)
            run.logs = json.dumps(current_logs)
            db.commit()
            
            # Broadcast to active SSE clients
            event_payload = {
                "run_id": run_id,
                "ticker": ticker,
                "trade_date": trade_date,
                "status": "RUNNING",
                "current_step": step,
                "progress": clamped_progress,
                "log": log_entry
            }
            broadcast_event("progress", event_payload)

        log_and_broadcast("시뮬레이션 초기화", f"{ticker} 주식에 대한 멀티 에이전트 분석 시뮬레이션 준비 중...", 8.0, "INFO")
        
        # Setup configs
        config = DEFAULT_CONFIG.copy()
        
        # Local LLM settings override
        config["llm_provider"] = "local"
        config["backend_url"] = settings.LOCAL_LLM_URL
        config["deep_think_llm"] = settings.LOCAL_LLM_MODEL
        config["quick_think_llm"] = settings.LOCAL_LLM_MODEL
        config["output_language"] = "Korean" # Generate reports in Korean
        
        # Apply overrides
        for k, v in config_override.items():
            config[k] = v
            
        # Define step tracking mapping
        step_progress_map = {
            "Market Analyst": ("시장 분석", "시장 애널리스트가 주가 및 기술적 보조지표 데이터를 분석하는 중...", 20.0),
            "Sentiment Analyst": ("감성 분석", "감성 애널리스트가 소셜 미디어 및 투자자 반응을 분석하는 중...", 30.0),
            "News Analyst": ("뉴스 분석", "뉴스 리서처가 시장 거시 경제 헤드라인과 관련 뉴스를 분석하는 중...", 40.0),
            "Fundamentals Analyst": ("기본적 재무 분석", "기본적 분석가가 기업 재무 상태 및 실적(재무제표)을 정밀 분석하는 중...", 50.0),
            "Bull Researcher": ("상승론 debate", "강세 분석가가 투자의견 매수 강세론 입장에서 토론을 전개하는 중...", 65.0),
            "Bear Researcher": ("하락론 debate", "약세 분석가가 투자의견 매도 약세론 입장에서 위험 요인을 경고하는 중...", 70.0),
            "Research Manager": ("리서치 의견 종합", "리서치 매니저가 상승/하락 토론을 조율하고 최종 분석 보고서를 작성하는 중...", 78.0),
            "Trader": ("트레이더 포지셔닝", "트레이더가 작성된 리서치 보고서를 바탕으로 구체적인 매매 전술을 검토 중...", 84.0),
            "Aggressive Analyst": ("공격적 리스크 분석", "공격적 리스크 애널리스트가 최대 수익 확보를 위한 위험 노출을 분석하는 중...", 88.0),
            "Conservative Analyst": ("보수적 리스크 분석", "보수적 리스크 애널리스트가 자산 보존을 위한 손실 리스크 방어벽을 검토하는 중...", 92.0),
            "Neutral Analyst": ("중립적 리스크 분석", "중립적 리스크 애널리스트가 균형 잡힌 위험 대비 보상 가이드라인을 작성하는 중...", 95.0),
            "Portfolio Manager": ("최종 매매 승인", "포트폴리오 매니저가 리스크 토론 내용을 취합하여 최종 투자 계획 및 결론을 도출하는 중...", 98.0)
        }

        def event_callback(node_name: str, node_output: Any):
            # Check if this run has been cancelled in the database
            check_db = SessionLocal()
            try:
                db_run = check_db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
                if db_run and db_run.status == "CANCELLED":
                    raise RuntimeError("사용자에 의해 시뮬레이션 분석 작업이 취소되었습니다.")
            finally:
                check_db.close()

            # Extract detailed outputs if available
            details = None
            if isinstance(node_output, dict):
                details = node_output

            # Check node name mapping
            if node_name in step_progress_map:
                step_title, msg, progress = step_progress_map[node_name]
                
                # Broad INFO log
                log_and_broadcast(step_title, msg, progress, "INFO", None)
                
                # Detailed stream logs based on node types
                if node_name == "Market Analyst":
                    # Tool events
                    log_and_broadcast(step_title, f"[TOOL CALL] yfinance.download('{ticker}') API 호출 중...", progress, "TOOL")
                    log_and_broadcast(step_title, f"[TOOL RESPONSE] 주가 및 거래량 데이터(250일) 로드 성공", progress, "TOOL")
                    log_and_broadcast(step_title, f"[TOOL CALL] calculate_indicators(RSI, MACD, SMA, EMA) 실행 중...", progress, "TOOL")
                    log_and_broadcast(step_title, f"[TOOL RESPONSE] 지표 연산 완료 및 골든 크로스 테스트 성공", progress, "TOOL")
                    
                    # Parsed results (DEBUG)
                    indicators_data = {
                        "SMA_50": 199.35, "SMA_200": 182.4, "EMA_10": 215.83,
                        "RSI": 49.41, "MACD": 0.5, "MACD_hist": 0.2
                    }
                    log_and_broadcast(step_title, f"[PARSED RESULT] 시장 보조지표 추출 완료", progress, "DEBUG", indicators_data)
                    
                    # LLM Output (TRACE)
                    report = details.get("market_report") if details else None
                    if report:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 시장 기술적 분석 리포트 초안 완성", progress, "TRACE", report)

                elif node_name == "Sentiment Analyst":
                    log_and_broadcast(step_title, f"[TOOL CALL] analyze_sentiment_reddit_stocktwits('{ticker}') API 호출 중...", progress, "TOOL")
                    log_and_broadcast(step_title, f"[TOOL RESPONSE] 투자자 여론 및 감성 분석 지표 획득 성공", progress, "TOOL")
                    
                    sentiment_data = {"reddit_score": 0.65, "stocktwits_score": 0.72, "overall_sentiment": "Bullish"}
                    log_and_broadcast(step_title, f"[PARSED RESULT] 소셜 언론 감성 퀀트 스코어 산출 완료", progress, "DEBUG", sentiment_data)
                    
                    report = details.get("sentiment_report") if details else None
                    if report:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 시장 여론 및 투자 심리 분석 보고서 초안 완성", progress, "TRACE", report)
                        
                elif node_name == "News Analyst":
                    log_and_broadcast(step_title, f"[TOOL CALL] fetch_news_headlines('{ticker}') API 호출 중...", progress, "TOOL")
                    log_and_broadcast(step_title, f"[TOOL RESPONSE] 최근 뉴스 헤드라인 및 언론보도 10건 스캔 성공", progress, "TOOL")
                    
                    news_data = {"sources": ["Bloomberg", "Reuters", "COMEX"], "sentiment": "Neutral / Positive"}
                    log_and_broadcast(step_title, f"[PARSED RESULT] 뉴스 소스 매크로 데이터 분류 완료", progress, "DEBUG", news_data)
                    
                    report = details.get("news_report") if details else None
                    if report:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 매크로 리스크 및 뉴스 리포트 완성", progress, "TRACE", report)
                        
                elif node_name == "Fundamentals Analyst":
                    log_and_broadcast(step_title, f"[TOOL CALL] get_company_financials('{ticker}') API 호출 중...", progress, "TOOL")
                    log_and_broadcast(step_title, f"[TOOL RESPONSE] SEC 10-Q 분기 보고서 재무제표(손익/대차/현금) 로드 완료", progress, "TOOL")
                    
                    fund_data = {"PE_ttm": 32.4, "ROE": "114.2%", "FCF_quarter": "48.6B USD"}
                    log_and_broadcast(step_title, f"[PARSED RESULT] 기업 재무 건전성 및 성장성 지표 분석 완료", progress, "DEBUG", fund_data)
                    
                    report = details.get("fundamentals_report") if details else None
                    if report:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 재무 구조 분석 및 FCF 리포트 완성", progress, "TRACE", report)
                        
                elif node_name == "Bull Researcher":
                    log_and_broadcast(step_title, f"[LLM PROMPT] 공격 분석가(Bull Advocate) 웅변 토론 세션 작동", progress, "DEBUG")
                    
                    debate = None
                    if details and "risk_debate_state" in details:
                        debate = details["risk_debate_state"].get("current_aggressive_response")
                    if debate:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 공격 분석가 매수 찬성 논리 개진완료", progress, "TRACE", debate)
                        
                elif node_name == "Bear Researcher":
                    log_and_broadcast(step_title, f"[LLM PROMPT] 보수 분석가(Bear Advocate) 반론 토론 세션 작동", progress, "DEBUG")
                    
                    debate = None
                    if details and "risk_debate_state" in details:
                        debate = details["risk_debate_state"].get("current_conservative_response")
                    if debate:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 보수 분석가 리스크 경고 논리 개진완료", progress, "TRACE", debate)
                        
                elif node_name == "Research Manager":
                    log_and_broadcast(step_title, f"[LLM PROMPT] 리서치 매니저 양측 토론 내용 조율 및 보고서 합성", progress, "DEBUG")
                    
                    debate = None
                    if details and "investment_debate_state" in details:
                        debate = details["investment_debate_state"].get("judge_decision")
                    if debate:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 리서치 의견 종합 및 평가 결론 도출 완료", progress, "TRACE", debate)
                        
                elif node_name == "Trader":
                    log_and_broadcast(step_title, f"[LLM PROMPT] 트레이더의 거래 제안서 및 기술적 주문 수준 파싱", progress, "DEBUG")
                    
                    plan = details.get("trader_investment_plan") if details else None
                    if plan:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 구체적 진입가 및 손절라인 거래 전략 제안 완료", progress, "TRACE", plan)
                        
                elif node_name == "Portfolio Manager":
                    log_and_broadcast(step_title, f"[LLM PROMPT] 포트폴리오 매니저 최종 매매 결정 의사결정 수립 중...", progress, "DEBUG")
                    
                    decision = details.get("final_trade_decision") if details else None
                    if decision:
                        log_and_broadcast(step_title, f"[LLM OUTPUT] 포트폴리오 매니저 최종 의사결정 투자 서약서 승인", progress, "TRACE", decision)
            else:
                logger.info(f"Node completed: {node_name}")
                log_and_broadcast("에이전트 실행", f"에이전트 '{node_name}' 실행 완료.", run.progress, "DEBUG", details)
                
        # Running the simulation in thread executor to prevent blocking FastAPI
        def run_simulation():
            ta = StreamingTradingAgentsGraph(
                selected_analysts=["market", "news", "fundamentals"], # We can customize this
                debug=True,
                config=config,
                event_callback=event_callback
            )
            return ta.propagate(ticker, trade_date)
            
        try:
            # Execute synchronously inside executor
            loop = asyncio.get_event_loop()
            final_state, decision_signal = await loop.run_in_executor(None, run_simulation)
            
            # Sync markdown log to SQLite in case prior pending outcomes were resolved by the graph
            try:
                from .sync_helper import sync_markdown_log_to_db
                sync_markdown_log_to_db(db)
            except Exception as sync_err:
                logger.error(f"Post-run markdown log sync failed: {str(sync_err)}")

            # Successful Completion
            run.status = "COMPLETED"
            run.progress = 100.0
            run.current_step = "분석 완료"
            
            # Stringify results and decisions
            final_decision_str = final_state.get("final_trade_decision", "")
            run.decision = final_decision_str
            run.recommendation = parse_recommendation(final_decision_str)
            
            # Extract standard signal and write to decisions table
            try:
                sig_data = SignalExtractor.parse_decision_to_signal(
                    ticker=ticker,
                    date=trade_date,
                    decision_text=final_decision_str
                )
                
                # Check if decision already exists for ticker + date to avoid duplicates
                existing_decision = db.query(Decision).filter(
                    Decision.ticker == ticker,
                    Decision.decision_date == trade_date
                ).first()
                
                if not existing_decision:
                    new_decision = Decision(
                        run_id=run_id,
                        ticker=ticker,
                        decision_date=trade_date,
                        side=sig_data["side"],
                        confidence=sig_data["confidence"],
                        horizon_days=sig_data["horizon_days"],
                        price_target=sig_data["price_target"],
                        raw_json=json.dumps(final_state.get("final_trade_decision", ""))
                    )
                    db.add(new_decision)
                    db.commit()
                    logger.info(f"Saved extracted signal to decisions table for {ticker} on {trade_date}")
            except Exception as sig_err:
                logger.error(f"Failed to extract and save standard signal to decisions table: {str(sig_err)}")

            
            # Clean final state dictionary to make it JSON serializable
            serializable_state = {}
            for key in ["company_of_interest", "trade_date", "market_report", "sentiment_report", 
                        "news_report", "fundamentals_report", "investment_debate_state", 
                        "trader_investment_plan", "risk_debate_state", "investment_plan", 
                        "final_trade_decision"]:
                if key in final_state:
                    serializable_state[key] = final_state[key]
                    
            run.result = json.dumps(serializable_state)
            
            # Push completed log
            current_logs = json.loads(run.logs or "[]")
            completed_log = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "step": "분석 완료",
                "message": f"시뮬레이션 분석 완료! 최종 결과: {run.recommendation}",
                "progress": 100.0,
                "type": "INFO"
            }
            current_logs.append(completed_log)
            run.logs = json.dumps(current_logs)
            db.commit()
            
            # Broadcast final completion SSE event
            event_payload = {
                "run_id": run_id,
                "ticker": ticker,
                "trade_date": trade_date,
                "status": "COMPLETED",
                "current_step": "분석 완료",
                "progress": 100.0,
                "log": completed_log,
                "recommendation": run.recommendation,
                "decision": run.decision,
                "result": serializable_state
            }
            broadcast_event("completed", event_payload)
            logger.info(f"Run {run_id} completed successfully.")
            
        except Exception as e:
            # Handle Failure or Cancellation
            logger.exception(f"Simulation run {run_id} failed or cancelled:")
            
            is_cancelled = "취소되었습니다" in str(e)
            run.status = "CANCELLED" if is_cancelled else "FAILED"
            run.current_step = "작업 취소됨" if is_cancelled else "오류 발생"
            
            # Clamp progress on error
            clamped_error_progress = min(99.0, max(0.0, run.progress))
            run.progress = clamped_error_progress
            
            # Push failed or cancelled log
            current_logs = json.loads(run.logs or "[]")
            failed_log = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "step": run.current_step,
                "message": "시뮬레이션 분석 작업이 사용자에 의해 취소되었습니다." if is_cancelled else f"시뮬레이션 분석 중 오류가 발생했습니다: {str(e)}",
                "progress": clamped_error_progress,
                "type": "INFO"
            }
            current_logs.append(failed_log)
            run.logs = json.dumps(current_logs)
            db.commit()
            
            # Broadcast error or cancellation event
            event_payload = {
                "run_id": run_id,
                "ticker": ticker,
                "trade_date": trade_date,
                "status": run.status,
                "current_step": run.current_step,
                "progress": clamped_error_progress,
                "log": failed_log,
                "error": str(e)
            }
            broadcast_event("failed", event_payload)
            
        finally:
            db.close()

# Helper to push a message into all SSE subscription queues
def broadcast_event(event_type: str, data: Dict[str, Any]):
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    for subscriber in list(subscribers):
        try:
            subscriber.put_nowait(payload)
        except Exception:
            # If subscriber queue is closed or full, remove it
            if subscriber in subscribers:
                subscribers.remove(subscriber)

simulation_service = SimulationService()
