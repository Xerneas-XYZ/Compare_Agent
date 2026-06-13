import requests
from typing import Optional

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.last_upload_meta: Optional[dict] = None
        self.last_error: Optional[str] = None

    def upload(self, file) -> Optional[str]:
        self.last_error = None
        try:
            resp = self.session.post(f"{self.base_url}/api/v1/upload", files={"file": (file.name, file.getvalue(), file.type)}, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            self.last_upload_meta = {"filename": data["filename"]}
            return data["doc_id"]
        except Exception as e:
            self.last_error = str(e)
            return None

    def compare(self, old_doc_id, new_doc_id, country, industry, role, language) -> Optional[dict]:
        try:
            resp = self.session.post(f"{self.base_url}/api/v1/compare", json={"old_doc_id": old_doc_id, "new_doc_id": new_doc_id, "country": country, "industry": industry, "role": role, "language": language}, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.last_error = str(e)
            return None

    def query(self, session_id: str, question: str, language: str = "en") -> Optional[dict]:
        try:
            resp = self.session.post(f"{self.base_url}/api/v1/compare/{session_id}/query", json={"question": question, "language": language}, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None