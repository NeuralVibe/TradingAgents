import asyncio
import uuid
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..database import get_db
from ..models import SimulationRun
from ..schemas import RunCreate, RunResponse
from ..services import simulation_service, subscribers

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/runs", tags=["runs"])

@router.post("", response_model=RunResponse)
async def create_run(
    payload: RunCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """Start a new multi-agent trading simulation run."""
    run_id = str(uuid.uuid4())
    
    # Extract optional config overrides
    config_override = {
        "llm_provider": payload.llm_provider,
        "deep_think_llm": payload.llm_model,
        "quick_think_llm": payload.llm_model,
        "max_debate_rounds": payload.max_debate_rounds,
        "max_risk_discuss_rounds": payload.max_risk_discuss_rounds,
    }
    
    # Create the run record and push to execution queue
    run = await simulation_service.add_run(
        run_id=run_id,
        ticker=payload.ticker.upper(),
        trade_date=payload.trade_date,
        config_override=config_override,
        db=db
    )
    
    return run

def sanitize_run_progress(run: SimulationRun, db: Session = None) -> SimulationRun:
    if not run:
        return run
    
    original_progress = run.progress
    if run.status == "COMPLETED":
        run.progress = 100.0
    else:
        run.progress = min(99.0, max(0.0, run.progress))
        
    if run.progress != original_progress and db:
        try:
            db.commit()
        except Exception as e:
            logger.error(f"동적 진행률 보정 커밋 실패: {str(e)}")
            
    return run

@router.get("", response_model=list[RunResponse])
async def list_runs(db: Session = Depends(get_db)):
    """List all simulation runs."""
    runs = db.query(SimulationRun).order_by(SimulationRun.created_at.desc()).all()
    for r in runs:
        sanitize_run_progress(r, db)
    return runs

@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, db: Session = Depends(get_db)):
    """Get the details of a single simulation run."""
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="실행 정보를 찾을 수 없습니다.")
    return sanitize_run_progress(run, db)

@router.delete("/{run_id}")
async def delete_or_cancel_run(run_id: str, db: Session = Depends(get_db)):
    """Delete a simulation run or cancel it if PENDING or RUNNING."""
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="실행 정보를 찾을 수 없습니다.")
        
    if run.status == "PENDING":
        run.status = "CANCELLED"
        run.current_step = "작업 대기 취소됨"
        db.commit()
        return {"message": "대기 중인 작업을 성공적으로 취소했습니다.", "status": "CANCELLED"}
        
    elif run.status == "RUNNING":
        run.status = "CANCELLED"
        run.current_step = "작업 취소 요청됨"
        db.commit()
        return {"message": "진행 중인 작업에 대해 취소를 요청했습니다.", "status": "CANCELLED"}
        
    else:
        db.delete(run)
        db.commit()
        return {"message": "분석 실행 기록을 데이터베이스에서 완전히 삭제했습니다.", "status": "DELETED"}

@router.get("/{run_id}/stream")
async def stream_run_progress(run_id: str):
    """Server-Sent Events (SSE) endpoint for real-time progress updates of a specific run."""
    
    async def event_generator():
        # Create a private queue for this client
        queue = asyncio.Queue()
        subscribers.append(queue)
        
        try:
            # Yield initial connect event
            yield {
                "event": "connected",
                "data": json.dumps({"message": f"Connected to run {run_id} SSE feed."})
            }
            
            while True:
                # Wait for any broadcast event
                payload = await queue.get()
                yield payload
                queue.task_done()
                
        except asyncio.CancelledError:
            # Handle client disconnect
            if queue in subscribers:
                subscribers.remove(queue)
            logger.info(f"SSE client disconnected from run {run_id}")
            
    return EventSourceResponse(event_generator())
