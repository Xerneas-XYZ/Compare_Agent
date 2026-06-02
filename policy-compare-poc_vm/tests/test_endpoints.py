# tests/test_endpoints.py 
import pytest, os, io 
from httpx import AsyncClient 
from backend.main import app 
from backend.storage import SessionLocal, Document, Audit 
 
@pytest.mark.asyncio 
async def test_upload_and_compare(tmp_path): 
    client = AsyncClient(app=app, base_url="http://test") 
    # login as alice (admin) 
    r = await client.post("/token", data={"username":"alice","password":"alicepass"}) 
    assert r.status_code == 200 
    token = r.json()["access_token"] 
    headers = {"Authorization": f"Bearer {token}"} 
    # create sample files 
    a = tmp_path / "a.txt" 
    b = tmp_path / "b.txt" 
    a.write_text("Policy A\nContact: alice@example.com\nClause 1: keep X") 
    b.write_text("Policy B\nContact: bob@example.com\nClause 1: change X") 
    # upload 
    with open(a, "rb") as fa: 
        r1 = await client.post("/upload/", files={"file": ("a.txt", fa, "text/plain")}, headers=headers) 
    with open(b, "rb") as fb: 
        r2 = await client.post("/upload/", files={"file": ("b.txt", fb, "text/plain")}, headers=headers) 
    assert r1.status_code == 200 and r2.status_code == 200 
    a_id = r1.json()["doc_id"] 
    b_id = r2.json()["doc_id"] 
    # compare 
    r3 = await client.post("/compare/", params={"a_id": a_id, "b_id": b_id}, headers=headers) 
    assert r3.status_code == 200 
    data = r3.json() 
    assert "diffs" in data and "semantic" in data 
    # audit entries exist 
    db = SessionLocal() 
    try: 
        audits = db.query(Audit).all() 
        assert len(audits) >= 3 
    finally: 
        db.close() 
    await client.aclose() 