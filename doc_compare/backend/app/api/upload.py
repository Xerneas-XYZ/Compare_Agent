"""
Upload API Router
POST /api/v1/upload  — Upload one or two documents; returns doc_id(s)
"""
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path

from app.parsers.document_parser import parse_document
from app.core.config import settings
from app.api.compare import store_doc

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload", summary="Upload a document for comparison")
@router.post("/upload/", summary="Upload a document for comparison (trailing slash)")
async def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {settings.ALLOWED_EXTENSIONS}")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")

    result = parse_document("", content, file.filename or "unknown")
    if not result.success:
        raise HTTPException(422, f"Failed to parse document: {result.error}")

    if not result.text.strip():
        raise HTTPException(422, "Document appears to be empty or could not extract text")

    doc_id = str(uuid.uuid4())
    # Log receipt for easier debugging of upload/timeouts
    logger.info(f"Received upload: filename={file.filename} size={len(content)} bytes")
    store_doc(doc_id, {
        "doc_id": doc_id,
        "filename": file.filename,
        "text": result.text,
        "metadata": result.metadata,
        "page_count": result.page_count,
        "char_count": len(result.text),
    })

    logger.info(f"Uploaded {file.filename} → doc_id={doc_id} ({len(result.text)} chars)")

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "char_count": len(result.text),
        "page_count": result.page_count,
        "format": result.metadata.get("format"),
    }