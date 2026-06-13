import uuid
import json
import logging
import re
import secrets
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
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

# --- CACHE DIRECTORY FOR SESSIONS ---
SESSION_CACHE_PATH = Path("./session_cache").resolve()
SESSION_CACHE_PATH.mkdir(parents=True, exist_ok=True)

def save_session(session_id: str, data: dict):
    """Persists session state to disk to survive server reloads and share across workers."""
    try:
        session_file = SESSION_CACHE_PATH / f"{session_id}.json"
        with session_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to persist session {session_id} to disk: {e}")

def load_session(session_id: str) -> Optional[dict]:
    """Loads session state from disk cache."""
    session_file = SESSION_CACHE_PATH / f"{session_id}.json"
    if not session_file.exists():
        return None
    try:
        with session_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read session file {session_id}: {e}")
        return None


class CompareRequest(BaseModel):
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
    safe_name = f"{doc_id}.json"
    doc_path = (UPLOAD_PATH / safe_name).resolve()
    
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

    # Persist session state securely to disk
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
        raise HTTPException(status_code=404, detail="Session not found")
        
    if "pair_id" not in session:
        raise HTTPException(status_code=500, detail="Session corrupted: Missing pair_id")

    pipeline = get_pipeline()
    
    try:
        result = pipeline.analyze(
            pair_id=session["pair_id"],
            question=req.question,
            country=session.get("country", "US"),
            industry=session.get("industry", "General"),
            role=session.get("role", "Analyst"),
            language=getattr(req, "language", "en"),
        )
        
        if "not indexed" in result["answer"]:
            return {
                "answer": "Session expired or memory wiped. Please re-run the comparison.",
                "sources": [],
                "tokens_used": 0,
                "grounding_confidence": 0.0,
                "pii_sanitized": False,
            }

        clean_answer = result["answer"]
        was_modified = False
        confidence = 0.0
        
        try:
            clean_answer, was_modified = sanitize_llm_output(result["answer"])
            grounding = check_response_grounding(clean_answer, result.get("sources", []))
            confidence = grounding.get("confidence", 0.0)
        except Exception as helper_err:
            logger.warning(f"Helper function failed (returning raw LLM output instead). Error: {helper_err}")

        return {
            "answer": clean_answer,
            "sources": result.get("sources", []),
            "tokens_used": result.get("tokens_used", 0),
            "grounding_confidence": confidence,
            "pii_sanitized": was_modified,
        }

    except Exception as e:
        logger.exception("Failed during RAG query pipeline:")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif callable(obj):  
        return str(obj()) if hasattr(obj, "__name__") else str(obj)
    else:
        return str(obj)


def store_doc(doc_id: str, data: dict):
    if not re.match(r"^[a-zA-Z0-9\-]+$", doc_id):
        raise HTTPException(400, "Malformed Document Target ID")
    
    doc_path = (UPLOAD_PATH / f"{doc_id}.json").resolve()
    if not doc_path.is_relative_to(UPLOAD_PATH):
        raise HTTPException(400, "Access denied")

    try:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        clean_data = sanitize_for_json(data)
        with doc_path.open("w", encoding="utf-8") as f:
            json.dump(clean_data, f, ensure_ascii=False, indent=2)
            
    except Exception as exc:
        logger.error("Failed to persist document %s to %s: %s", doc_id, doc_path, exc)
        raise HTTPException(500, f"Unable to store uploaded document: {str(exc)}")