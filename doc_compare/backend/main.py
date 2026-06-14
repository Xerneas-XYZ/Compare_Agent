import time
import uuid
import secrets
import json
import logging
import tempfile
import portalocker
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.compliance_registry import get_agencies, ROLE_PERMISSIONS
from app.pii.masker import full_mask
from app.diff.engine import compute_diff
from app.rag.engine import SafeRAGEngine, validate_and_ground

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting Document Comparison API...")

app = FastAPI(title="Document Comparison Framework", version="2.0.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

rag_engine = SafeRAGEngine()

# --- ATOMIC SECURED STORAGE UTILITIES -
def write_session_locked(session_id: str, payload: dict):
    target = settings.SESSION_CACHE_DIR / f"{session_id}.json"
    with open(target, "w", encoding="utf-8") as f:
        # FIX: Use LOCK_EX for writing to prevent corruption
        portalocker.lock(f, portalocker.LOCK_EX)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        portalocker.lock(f, portalocker.LOCK_UN)

def read_session_locked(session_id: str) -> dict:
    target = settings.SESSION_CACHE_DIR / f"{session_id}.json"
    if not target.exists():
        raise HTTPException(404, "Session record context missing.")
    with open(target, "r", encoding="utf-8") as f:
        portalocker.lock(f, portalocker.LOCK_SH)
        data = json.load(f)
        portalocker.lock(f, portalocker.LOCK_UN)
        return data

# --- REQUEST SCHEMAS ---
class CompareInbound(BaseModel):
    old_doc_id: str = Field(..., pattern=r"^[a-zA-Z0-9\-]+$")
    new_doc_id: str = Field(..., pattern=r"^[a-zA-Z0-9\-]+$")
    country: str = Field(..., pattern="^(usa|uk|india|china|russia|germany)$")
    industry: str = Field(..., pattern="^(banking|insurance|healthcare)$")
    role: str = Field(..., pattern="^(compliance_officer|general_user|legal_consultant)$")
    language: str = Field(default="en", pattern="^(en|es|hi|zh|ru|de)$")

class QueryInbound(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    language: str = Field(default="en")  # FIX: Support translated Q&A queries

# --- API ROUTERS ---
@app.get("/api/v1/health")
def liveness():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/upload")
async def receive_stream(file: UploadFile = File(...)):
    sfx = Path(file.filename or "").suffix.lower()
    
    # Optional: expand this if you are using other formats. 
    # Currently Docling handles pdf and docx best in our pipeline.
    if sfx not in (".pdf", ".docx", ".txt", ".json", ".csv"):
        raise HTTPException(400, "Invalid file format extension.")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=sfx) as local_tmp:
        local_tmp.write(await file.read())
        local_path = Path(local_tmp.name)
        
    try:
        # 1. Generate the unique ID the frontend expects
        doc_id = str(uuid.uuid4())
        
        # 2. Save the metadata mapping to disk so /compare can locate the physical temp file later
        meta_path = settings.UPLOAD_DIR / f"{doc_id}.json"
        with open(meta_path, "w", encoding="utf-8") as out:
            json.dump({
                "doc_id": doc_id,
                "filename": file.filename, 
                "temp_filepath": str(local_path), 
                "suffix": sfx
            }, out, ensure_ascii=False)
            
        # 3. Return the exact schema the Streamlit APIClient needs
        return {"doc_id": doc_id, "filename": file.filename}
        
    except Exception as err:
        # Cleanup the temp file if the JSON write fails
        local_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Streaming write phase failure: {err}")

@app.post("/api/v1/compare")
async def execute_compare(req: CompareInbound):
    try:
        from app.rag.pipeline import chunk_isolated_ingest
        
        old_path = settings.UPLOAD_DIR / f"{req.old_doc_id}.json"
        new_path = settings.UPLOAD_DIR / f"{req.new_doc_id}.json"
        
        with open(old_path, "r") as f: old_meta = json.load(f)
        with open(new_path, "r") as f: new_meta = json.load(f)
        
        # Load the physical file paths generated during the upload phase
        o_path = Path(old_meta["temp_filepath"])
        n_path = Path(new_meta["temp_filepath"])
        
        print(f"Comparing documents: {o_path} vs {n_path}")
        print(f"========================== Old doc metadata started =======================" )
        old_struct_chunks = chunk_isolated_ingest(o_path, old_meta["suffix"], "OLD")
        print(f"========================== New doc metadata started =======================" )
        new_struct_chunks = chunk_isolated_ingest(n_path, new_meta["suffix"], "NEW")
        
        old_flat_text = "\n".join([c["text"] for c in old_struct_chunks])
        new_flat_text = "\n".join([c["text"] for c in new_struct_chunks])
        
        masked_old = full_mask(old_flat_text, req.language)
        masked_new = full_mask(new_flat_text, req.language)
        
        diff_data = compute_diff(masked_old.masked_text, masked_new.masked_text)
        
        pair_id = rag_engine.build_index_from_structural_chunks(old_struct_chunks, new_struct_chunks)
        
        query_context = {"country": req.country, "industry": req.industry, "role": req.role, "language": req.language}
        prompt_str = f"Identify all major changes. Compare parallel metrics. What are the key regulatory compliance implications?"
        
        analysis = rag_engine.load_align_and_compare(pair_id, prompt_str, query_context)
        
        # FIX: Apply strict trigram grounding validation
        ground_metrics = validate_and_ground(analysis["answer"], analysis.get("sources", []))
        
        session_id = secrets.token_hex(16)
        
        # FIX: Build complete payload required by the Streamlit UI
        payload = {
            "session_id": session_id, "pair_id": pair_id,
            "old_filename": old_meta.get("filename", "Old Policy"), "new_filename": new_meta.get("filename", "New Policy"),
            "similarity_score": diff_data.similarity_score, "diff_summary": diff_data.summary,
            "regulatory_impact": {
                "answer": analysis["answer"], 
                "confidence": ground_metrics["confidence"],
                "sources": analysis.get("sources", []),
                "tokens_used": analysis.get("tokens_used", 0)
            },
            "diff_chunks": [vars(c) for c in diff_data.chunks],
            "pii_stats": {
                "old_doc_redactions": masked_old.redaction_count, 
                "new_doc_redactions": masked_new.redaction_count
            },
            "compliance_context": {
                "country": req.country, "industry": req.industry, "role": req.role, **get_agencies(req.country, req.industry)
            }
        }
        
        write_session_locked(session_id, payload)
        return payload
        
    except Exception as e:
        logger.exception("The aligned workflow pipeline crashed during orchestration execution.")
        raise HTTPException(500, f"Extract-Align-Compare routine execution fault: {str(e)}")
    

@app.post("/api/v1/compare/{session_id}/query")
async def execute_query(session_id: str, req: QueryInbound):
    session = read_session_locked(session_id)
    ctx = session["compliance_context"]
    ctx["language"] = req.language
    
    # FIX: Use correct Extract-Align RAG method and apply grounding calculation
    analysis = rag_engine.load_align_and_compare(session["pair_id"], req.question, ctx)
    ground_metrics = validate_and_ground(analysis["answer"], analysis.get("sources", []))
    
    return {
        "answer": analysis["answer"], 
        "sources": analysis.get("sources", []),
        "tokens_used": analysis.get("tokens_used", 0),
        "grounding_confidence": ground_metrics["confidence"]
    }

@app.get("/api/v1/export/{session_id}/pdf")
async def generate_pdf_report(session_id: str):
    """Secured programmatic PDF compiler generation matching target specifications."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        import io

        session = read_session_locked(session_id)
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f"Compliance Audit Report: {session['new_filename']}", styles["Title"]))
        story.append(Spacer(1, 15))

        meta_matrix = [
            ["Metric Parameter", "Audit Valuation"],
            ["Old Source Context", session["old_filename"]],
            ["New Structural Target", session["new_filename"]],
            ["Document Similarity Ratio", f"{session['similarity_score'] * 100:.2f}%"],
            ["Target Evaluation Region", session["compliance_context"]["country"].upper()]
        ]
        t = Table(meta_matrix, colWidths=[200, 300])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.dodgerblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10)
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

        story.append(Paragraph("Automated Regulatory Impact Analysis", styles["Heading2"]))
        story.append(Spacer(1, 10))
        story.append(Paragraph(session["regulatory_impact"]["answer"].replace("\n", "<br/>"), styles["BodyText"]))

        doc.build(story)
        buf.seek(0)
        return Response(content=buf.read(), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=audit_{session_id[:8]}.pdf"})
    except Exception as err:
        logger.exception("PDF Export failed internally")
        raise HTTPException(500, f"Failed compiling structural layout report document elements: {err}")