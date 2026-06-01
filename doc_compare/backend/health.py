"""Health check router"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health", summary="Liveness probe")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready", summary="Readiness probe")
def ready():
    checks = {}
    try:
        import faiss
        checks["faiss"] = "ok"
    except ImportError:
        checks["faiss"] = "missing"
    try:
        import pdfplumber
        checks["pdfplumber"] = "ok"
    except ImportError:
        checks["pdfplumber"] = "missing"
    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}