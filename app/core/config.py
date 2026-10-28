"""Application Configuration Module using Pydantic Settings.
Conservative defaults for CPU-only local execution on 8 GB RAM machines.
"""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application Information
    APP_NAME: str = "Agentic AI Workflow Automation Platform"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server Binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "default-development-secret-key-change-in-production-32-chars"
    API_KEY_HEADER: str = "X-API-Key"
    ADMIN_API_KEY: str = "admin-secret-key-12345"

    # Persistence
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"
    CHECKPOINTER_DB_PATH: str = "./data/checkpoints.db"

    # LLM Settings (Ollama / Local runtime)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:3b-instruct"
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_FALLBACK_MOCK: bool = True  # Automatically use deterministic planner when Ollama is offline

    # Policy & Resource Bounds
    MAX_PLAN_STEPS: int = 8
    MAX_STEP_RETRIES: int = 2
    MAX_REPLANS: int = 2
    DEFAULT_TASK_TIMEOUT_SECONDS: float = 300.0
    TOOL_TIMEOUT_SECONDS: float = 15.0
    APPROVAL_TIMEOUT_SECONDS: float = 1800.0  # 30 minutes before pending approval expires

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    def ensure_directories(self) -> None:
        """Ensure necessary data and log directories exist."""
        Path("./data").mkdir(parents=True, exist_ok=True)
        Path("./data/fixtures").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
