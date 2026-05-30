import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "NeuralVibe TradingAgents Platform API"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = "sqlite:///./trading_platform.db"
    
    # Local LLM Default
    LOCAL_LLM_URL: str = "http://localhost:8000/api/v1/chat"
    LOCAL_LLM_MODEL: str = "qwen3.6-27b-uncensored-heretic-v2-native-mtp-preserved"
    
    # Concurrency Settings
    MAX_CONCURRENT_RUNS: int = 1
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    class Config:
        case_sensitive = True

settings = Settings()
