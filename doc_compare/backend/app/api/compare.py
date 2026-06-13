import uuid
import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.parsers.document_parser import parse_document
from app.pii.masker import full_mask
from app.diff.engine import compute_diff
from app.rag.pipeline import get_pipeline
from app.guardrails.checks import validate_input, sanitize_llm_output, check_response_grounding
from app.core.config import settings
from app.core.compliance_registry import get_agencies

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_PATH = Path(settings.UPLOAD_DIR).resolve()
print(f"this is the upload_path {UPLOAD_PATH}")
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

# --- PRODUCTION READY PERSISTENCE WRAPPERS ---
# NOTE: Replace the bodies of these helpers with Redis/DB queries in prod.
_sessions_mock_db: dict = {}

def save_session(session_id: str, data: dict):
    # TODO: Use Redis: redis_client.setex(f"session:{session_id}", 86400, json.dumps(data))
    _sessions_mock_db[session_id] = data

def load_session(session_id: str) -> Optional[dict]:
    # TODO: Use Redis: data = redis_client.get(f"session:{session_id}")
    return _sessions_mock_db.get(session_id)


class CompareRequest(BaseModel):
    # Enforce safe format patterns to block path traversal strings
    old_doc_id: str = Field(..., pattern=r"^[a-zA-Z0-9\-]+$")
    new_doc_id: str = Field(..., pattern=r"^[a-zA-Z0-9\-]+$")
    country: str = Field(..., pattern="^(usa|uk|india|china|russia|germany)$")
    industry: str = Field(..., pattern="^(banking|insurance|healthcare)$")
    role: str = Field(..., pattern="^(compliance_officer|general_user|legal_consultant)$")
    language: str = Field(default="en", pattern="^(en|es|hi|zh|ru|de)$")
    risk_filter: Optional[str] = Field(default=None, pattern="^(high|medium|low|none)?$")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    language: str = Field(default="en")


def get_doc(doc_id: str) -> dict:
    # 🌟 Strictly isolate and resolve safe file paths
    safe_name = f"{doc_id}.json"
    doc_path = (UPLOAD_PATH / safe_name).resolve()
    
    # 🌟 Explicitly block directory traversal attacks
    if not doc_path.is_relative_to(UPLOAD_PATH):
        logger.warning(f"Directory traversal attempt blocked for doc_id: {doc_id}")
        raise HTTPException(400, "Invalid document identifier")

    if not doc_path.exists():
        raise HTTPException(404, "Document not found. Re-upload required.")
    try:
        with doc_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Error reading stored document %s: %s", doc_id, exc)
        raise HTTPException(500, "Failed to read stored document")


@router.post("/compare", summary="Compare two uploaded documents")
async def compare_documents(req: CompareRequest):
    old_doc = get_doc(req.old_doc_id)
    new_doc = get_doc(req.new_doc_id)

    old_masked = full_mask(old_doc["text"], req.language)
    new_masked = full_mask(new_doc["text"], req.language)

    for text, fname in [(old_masked.masked_text, old_doc["filename"]),
                        (new_masked.masked_text, new_doc["filename"])]:
        valid, reason = validate_input(text, fname)
        if not valid:
            raise HTTPException(400, reason)

    diff_result = compute_diff(old_masked.masked_text, new_masked.masked_text)

    pipeline = get_pipeline()
    pair_id = pipeline.index_pair(old_masked.masked_text, new_masked.masked_text)

    impact = pipeline.generate_impact_summary(
        pair_id=pair_id,
        diff_summary=diff_result.summary,
        country=req.country,
        industry=req.industry,
        role=req.role,
        language=req.language,
    )

    clean_answer, was_modified = sanitize_llm_output(impact["answer"])
    grounding = check_response_grounding(clean_answer, impact.get("sources", []))
    agency_data = get_agencies(req.country, req.industry)

    # Use secure token generators to guarantee multi-worker randomness
    import secrets
    session_id = secrets.token_hex(16)
    
    result = {
        "session_id": session_id,
        "pair_id": pair_id,
        "old_filename": old_doc["filename"],
        "new_filename": new_doc["filename"],
        "similarity_score": diff_result.similarity_score,
        "diff_summary": diff_result.summary,
        "diff_chunks": [
            {
                "chunk_id": c.chunk_id,
                "change_type": c.change_type.value,
                "risk_level": c.risk_level.value,
                "risk_keywords": c.risk_keywords,
                "old_text": c.old_text[:500] if c.old_text else None,
                "new_text": c.new_text[:500] if c.new_text else None,
            }
            for c in diff_result.chunks
            if c.change_type.value != "unchanged"
        ],
        "regulatory_impact": {
            "answer": clean_answer,
            "sources": impact.get("sources", []),
            "tokens_used": impact.get("tokens_used", 0),
            "grounding_confidence": grounding["confidence"],
            "pii_sanitized": was_modified,
        },
        "compliance_context": {
            "country": req.country,
            "industry": req.industry,
            "role": req.role,
            "agencies": agency_data["agencies"],
            "key_regulations": agency_data["key_regs"],
        },
        "pii_stats": {
            "old_doc_redactions": old_masked.redaction_count,
            "new_doc_redactions": new_masked.redaction_count,
        },
    }

    # Persist session state securely
    save_session(session_id, {
        "result": result, 
        "pair_id": pair_id,
        "country": req.country, 
        "industry": req.industry,
        "role": req.role
    })
    
    return result


@router.get("/compare/{session_id}", summary="Retrieve a previous comparison result")
async def get_comparison(session_id: str):
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session["result"]


@router.post("/compare/{session_id}/query", summary="Follow-up RAG query on a comparison session")
async def query_comparison(session_id: str, req: QueryRequest):
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    pipeline = get_pipeline()
    result = pipeline.analyze(
        pair_id=session["pair_id"],
        question=req.question,
        country=session["country"],
        industry=session["industry"],
        role=session["role"],
        language=req.language,
    )

    clean_answer, was_modified = sanitize_llm_output(result["answer"])
    grounding = check_response_grounding(clean_answer, result.get("sources", []))

    return {
        "answer": clean_answer,
        "sources": result.get("sources", []),
        "tokens_used": result.get("tokens_used", 0),
        "grounding_confidence": grounding["confidence"],
        "pii_sanitized": was_modified,
    }

import re  # 🌟 Ensure re is imported at the top of the file

def sanitize_for_json(obj):
    """Recursively converts all non-primitive objects and methods into strings."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif callable(obj):  # 🌟 Intercepts uncalled methods like ext.strip
        return str(obj()) if hasattr(obj, "__name__") else str(obj)
    else:
        return str(obj)

def store_doc(doc_id: str, data: dict):
    print(f"storing the files {doc_id}")
    
    # 🌟 FIX: Explicitly run the regex compilation match check
    if not re.match(r"^[a-zA-Z0-9\-]+$", doc_id):
        raise HTTPException(400, "Malformed Document Target ID")
    
    print(f"Attempting to store document {doc_id} at {UPLOAD_PATH}")
    doc_path = (UPLOAD_PATH / f"{doc_id}.json").resolve()
    if not doc_path.is_relative_to(UPLOAD_PATH):
        raise HTTPException(400, "Access denied")

    try:
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        # 🌟 FIX: Deep clean the payload to remove any stray methods or objects
        clean_data = sanitize_for_json(data)

        with doc_path.open("w", encoding="utf-8") as f:
            json.dump(clean_data, f, ensure_ascii=False, indent=2)
            
    except Exception as exc:
        logger.error("Failed to persist document %s to %s: %s", doc_id, doc_path, exc)
        raise HTTPException(500, f"Unable to store uploaded document: {str(exc)}")
