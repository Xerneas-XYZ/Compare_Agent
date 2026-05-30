# backend/main.py 
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Depends 
from fastapi.middleware.cors import CORSMiddleware 
from fastapi.security import OAuth2PasswordRequestForm 
import shutil, os, tempfile, json 
from backend.ingestion import parse_document, index_document, get_text_by_id 
from backend.compare import text_diff, semantic_compare 
from backend.auth import authenticate_user, create_access_token, decode_token, require_role 
from backend.audit import record_audit, audit_middleware 
from backend.storage import init_db 
from typing import Optional 
 
init_db() 
 
app = FastAPI(title="Policy Compare POC") 
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]) 
app.middleware("http")(audit_middleware) 
 
@app.post("/token") 
async def login(form_data: OAuth2PasswordRequestForm = Depends()): 
    user = authenticate_user(form_data.username, form_data.password) 
    if not user: 
        raise HTTPException(status_code=401, detail="Invalid credentials") 
    token = create_access_token({"sub": user["username"], "roles": user["roles"]}) 
    return {"access_token": token, "token_type": "bearer"} 
 
def get_current_user(authorization: Optional[str] = Header(None)): 
    if not authorization: 
        return None 
    scheme, _, token = authorization.partition(" ") 
    payload = decode_token(token) 
    return payload 
 
@app.post("/upload/") 
async def upload(file: UploadFile = File(...), authorization: Optional[str] = Header(None)): 
    user = get_current_user(authorization) 
    if not user: 
        raise HTTPException(status_code=401, detail="Unauthorized") 
    # RBAC: only admin or viewer can upload 
    if not require_role(user, ["admin", "viewer"]): 
        raise HTTPException(status_code=403, detail="Forbidden") 
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) 
    try: 
        with open(tmp.name, "wb") as f: 
            shutil.copyfileobj(file.file, f) 
        masked_text, pii_summary = parse_document(tmp.name) 
        doc_id = index_document(file.filename, masked_text, metadata={"uploader": user.get("sub"), "pii_summary": pii_summary}) 
        record_audit(user=user.get("sub"), action="upload", target=file.filename, details={"doc_id": doc_id, "pii_summary": pii_summary}) 
        return {"doc_id": doc_id, "filename": file.filename, "pii_summary": pii_summary} 
    finally: 
        try: 
            os.unlink(tmp.name) 
        except Exception: 
            pass 
 
@app.post("/compare/") 
async def compare(a_id: int, b_id: int, authorization: Optional[str] = Header(None)): 
    user = get_current_user(authorization) 
    if not user: 
        raise HTTPException(status_code=401, detail="Unauthorized") 
    # RBAC: admin and auditor can compare; viewers can only view existing comparisons 
    if not require_role(user, ["admin", "auditor", "viewer"]): 
        raise HTTPException(status_code=403, detail="Forbidden") 
    a_text = get_text_by_id(a_id) 
    b_text = get_text_by_id(b_id) 
    if a_text is None or b_text is None: 
        raise HTTPException(status_code=404, detail="Document not found") 
    diffs = text_diff(a_text, b_text) 
    semantic = semantic_compare(a_text, b_text) 
    # For demo, LangGraph orchestration is represented as a simple LLM call inside semantic_compare 
    record_audit(user=user.get("sub"), action="compare", target=f"{a_id} vs {b_id}", details={"a_id": a_id, "b_id": b_id}) 
    return {"diffs": diffs, "semantic": semantic} 
    # Add these imports near the top of backend/main.py 
from fastapi import Query 
from backend.storage import SessionLocal, Audit, Document 
 
# Add this endpoint to list recent audit entries (RBAC: auditor/admin) 
@app.get("/audit/") 
async def list_audit(limit: int = Query(50, ge=1, le=500), authorization: Optional[str] = Header(None)): 
    user = get_current_user(authorization) 
    if not user: 
        raise HTTPException(status_code=401, detail="Unauthorized") 
    if not require_role(user, ["admin", "auditor"]): 
        # viewers should not see full audit in demo 
        raise HTTPException(status_code=403, detail="Forbidden") 
    db = SessionLocal() 
    try: 
        rows = db.query(Audit).order_by(Audit.timestamp.desc()).limit(limit).all() 
        out = [] 
        for r in rows: 
            out.append({"id": r.id, "user": r.user, "action": r.action, "target": r.target, "details": r.details, "timestamp": r.timestamp.isoformat()}) 
        return out 
    finally: 
        db.close() 
    
 
# Add this endpoint to list indexed documents (all roles) 
@app.get("/documents/") 
async def list_documents(authorization: Optional[str] = Header(None)): 
    user = get_current_user(authorization) 
    if not user: 
        raise HTTPException(status_code=401, detail="Unauthorized") 
    db = SessionLocal() 
    try: 
        rows = db.query(Document).order_by(Document.created_at.desc()).limit(200).all() 
        out = [] 
        for r in rows: 
            out.append({"id": r.id, "filename": r.filename, "metadata": r.metadata, "created_at": r.created_at.isoformat()}) 
        return out 
    finally: 
        db.close() 