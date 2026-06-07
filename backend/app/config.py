"""Application configuration. Reads from .env file."""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All environment variables for the application."""

    # GitHub Models (AI explanations)
    github_models_pat: str = ""
    github_models_model: str = "openai/gpt-4.1"

    # Supabase (Phase 2+)
    supabase_url: str = "http://localhost:54321"
    supabase_service_key: str = "postgres"
    
    # CORS - Load from env: ALLOWED_ORIGINS=http://localhost:3000,https://codescope.vercel.app
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # Redis (Phase 2+)
    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379"

    # Ollama (Phase 4)
    ollama_cloud_url: str = "https://ollama.com/api"
    ollama_model: str = "llama3.2"

    # Logging
    log_level: str = "INFO"

    # Rate limiting
    rate_limit_per_hour: int = 20
    rate_limit_window_seconds: int = 3600

    # Concurrency
    max_concurrent_traces: int = 25

    class Config:
        env_file = ".env"
        extra = "allow"


# Global singleton instance
settings = Settings()
