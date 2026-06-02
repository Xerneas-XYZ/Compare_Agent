"""
Central config — all knobs in one place.
Uses pydantic-settings; override via environment variables or .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str = Field(default="change-me-in-prod", min_length=16)
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8501", "http://localhost:3000"]

    # ── Storage ──────────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "/tmp/doccompare/uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt", ".csv", ".json", ".docx", ".xlsx", ".pptx"]

    # ── LLM ──────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"          # cheaper default; override with gpt-4o for prod
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.0            # deterministic for compliance analysis
    CHUNK_SIZE: int = 800                   # token-optimised chunk size
    CHUNK_OVERLAP: int = 80

    # ── Embedding ────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "text-embedding-3-small"   # cheapest OpenAI embedding
    FAISS_INDEX_PATH: str = "/tmp/doccompare/faiss"

    # ── Tracing ──────────────────────────────────────────────────────────────
    LANGSMITH_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "doc-compare-agent"

    # ── PII ──────────────────────────────────────────────────────────────────
    PII_MASK_TOKEN: str = "[REDACTED]"
    SPACY_MODEL: str = "en_core_web_sm"     # download separately per language

    # ── Compliance ───────────────────────────────────────────────────────────
    SUPPORTED_LANGUAGES: List[str] = ["en", "es", "hi", "zh", "ru", "de"]
    SUPPORTED_COUNTRIES: List[str] = ["usa", "uk", "india", "china", "russia", "germany"]
    SUPPORTED_INDUSTRIES: List[str] = ["banking", "insurance", "healthcare"]
    SUPPORTED_ROLES: List[str] = ["compliance_officer", "general_user", "legal_consultant"]

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Ensure dirs exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)