"""
Compare API Router
POST /api/v1/compare   — Full document comparison pipeline
GET  /api/v1/compare/{session_id}  — Retrieve previous result
POST /api/v1/compare/{session_id}/query  — Follow-up RAG query
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
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

# In-memory session store (replace with Redis in prod)
_sessions: dict = {}


class CompareRequest(BaseModel):
    old_doc_id: str
    new_doc_id: str
    country: str = Field(..., pattern="^(usa|uk|india|china|russia|germany)$")
    industry: str = Field(..., pattern="^(banking|insurance|healthcare)$")
    role: str = Field(..., pattern="^(compliance_officer|general_user|legal_consultant)$")
    language: str = Field(default="en", pattern="^(en|es|hi|zh|ru|de)$")
    risk_filter: Optional[str] = Field(default=None, pattern="^(high|medium|low|none)?$")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    language: str = Field(default="en")


# Temporary in-memory doc store (in prod: S3 presigned URL → local temp)
_doc_store: dict = {}


def get_doc(doc_id: str) -> dict:
    doc = _doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found. Re-upload required.")
    return doc


@router.post("/compare", summary="Compare two uploaded documents")
async def compare_documents(req: CompareRequest):
    old_doc = get_doc(req.old_doc_id)
    new_doc = get_doc(req.new_doc_id)

    # 1. Mask PII in both
    old_masked = full_mask(old_doc["text"], req.language)
    new_masked = full_mask(new_doc["text"], req.language)

    # 2. Validate inputs
    for text, fname in [(old_masked.masked_text, old_doc["filename"]),
                        (new_masked.masked_text, new_doc["filename"])]:
        valid, reason = validate_input(text, fname)
        if not valid:
            raise HTTPException(400, reason)

    # 3. Compute structural diff
    diff_result = compute_diff(old_masked.masked_text, new_masked.masked_text)

    # 4. Index for RAG
    pipeline = get_pipeline()
    pair_id = pipeline.index_pair(old_masked.masked_text, new_masked.masked_text)

    # 5. Generate impact summary
    impact = pipeline.generate_impact_summary(
        pair_id=pair_id,
        diff_summary=diff_result.summary,
        country=req.country,
        industry=req.industry,
        role=req.role,
        language=req.language,
    )

    # 6. Sanitize LLM output
    clean_answer, was_modified = sanitize_llm_output(impact["answer"])
    grounding = check_response_grounding(clean_answer, impact.get("sources", []))

    # 7. Agency context
    agency_data = get_agencies(req.country, req.industry)

    session_id = str(uuid.uuid4())
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
            if c.change_type.value != "unchanged"   # skip unchanged in response
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

    _sessions[session_id] = {"result": result, "pair_id": pair_id,
                              "country": req.country, "industry": req.industry,
                              "role": req.role}
    return result


@router.get("/compare/{session_id}", summary="Retrieve a previous comparison result")
async def get_comparison(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session["result"]


@router.post("/compare/{session_id}/query", summary="Follow-up RAG query on a comparison session")
async def query_comparison(session_id: str, req: QueryRequest):
    session = _sessions.get(session_id)
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


# Expose doc store for upload router
def store_doc(doc_id: str, data: dict):
    _doc_store[doc_id] = data