import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config import settings
from .database import engine, Base
from .routers import runs, market
from .services import simulation_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize database tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Successfully created database tables.")
except Exception as e:
    logger.exception("Error creating database tables:")

# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background queue worker
    worker_task = asyncio.create_task(simulation_service.start_worker())
    logger.info("Simulation queue background worker started successfully.")
    
    yield
    
    # Shutdown: Cancel worker task
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        logger.info("Simulation queue background worker stopped.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(runs.router, prefix=settings.API_V1_STR)
app.include_router(market.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "NeuralVibe TradingAgents 고도화 API 서비스에 오신 것을 환영합니다.",
        "version": "1.0.0",
        "language": "Korean (한국어)",
        "docs_url": "/docs"
    }
