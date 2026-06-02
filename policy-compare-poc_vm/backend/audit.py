# backend/audit.py 
from fastapi import Request 
from backend.storage import SessionLocal, Audit 
import json 
 
def record_audit(user: str, action: str, target: str, details: dict): 
    db = SessionLocal() 
    try: 
        entry = Audit(user=user, action=action, target=target, details=details) 
        db.add(entry) 
        db.commit() 
    finally: 
        db.close() 
 
async def audit_middleware(request: Request, call_next): 
    # Attach user info if present in header for demo 
    user = request.headers.get("x-demo-user", "anonymous") 
    response = await call_next(request) 
    try: 
        record_audit(user=user, action=request.method + " " + request.url.path, target="", details={"status_code": response.status_code}) 
    except Exception: 
        pass 
    return response 