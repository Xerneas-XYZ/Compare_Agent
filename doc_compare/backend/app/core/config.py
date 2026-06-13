import os
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "production"
    SECRET_KEY: str = Field(default="change-me-in-production-secure-string-32", min_length=32)
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8501", "http://localhost:3000"]

    BASE_DIR: Path = Path("/tmp/doccompare").resolve()
    UPLOAD_DIR: Path = Field(default_factory=lambda: Path("/tmp/doccompare/uploads"))
    FAISS_INDEX_PATH: Path = Field(default_factory=lambda: Path("/tmp/doccompare/faiss"))
    SESSION_CACHE_DIR: Path = Field(default_factory=lambda: Path("/tmp/doccompare/sessions"))
    MAX_FILE_SIZE_MB: int = 50

    OPENAI_API_KEY: str = Field(default="")
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.0

    PII_MASK_TOKEN: str = "[REDACTED]"
    SPACY_MODEL_DEFAULT: str = "en_core_web_sm"

    class Config:
        env_file = ".env"

settings = Settings()
for path in [settings.UPLOAD_DIR, settings.FAISS_INDEX_PATH, settings.SESSION_CACHE_DIR]:
    path.mkdir(parents=True, exist_ok=True)