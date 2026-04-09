"""Application configuration using Pydantic BaseSettings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "SRE Triage Agent"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    debug: bool = False

    # --- LLM: Gemini (primary – fast/cheap tasks) ---
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"

    # --- LLM: Claude (complex analysis) ---
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/incidents.db"

    # --- Observability ---
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_service_name: str = "sre-triage-agent"

    # --- Integrations ---
    discord_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "sre-agent@example.com"

    # --- File uploads ---
    upload_dir: str = "uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_mime_types: list[str] = [
        "image/png",
        "image/jpeg",
        "text/plain",
        "application/octet-stream",
    ]

    # --- Security ---
    enable_prompt_injection_detection: bool = True
    rate_limit_per_minute: int = 30

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
