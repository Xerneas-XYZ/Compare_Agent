"""
HTTP client with built-in mock mode.

Mock mode activates automatically when the backend is unreachable on first contact,
or can be forced via DEMO_MODE=true env var or the sidebar toggle.

Mock mode lets you:
  - Upload any supported file (parsed client-side for metadata only)
  - Run a canned comparison with realistic diff output
  - Ask Q&A questions (returns templated answers)
  - Export JSON (real data), PDF (placeholder)

No OpenAI key needed in mock mode.
"""
import logging
import os
import uuid
import hashlib
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Mock data ─────────────────────────────────────────────────────────────────
_MOCK_DIFF_CHUNKS = [
    {"chunk_id": "a1b2c3d4", "change_type": "modified", "risk_level": "high",
     "risk_keywords": ["mandatory", "penalty"],
     "old_text": "Reporting is optional within 5 business days of incident.",
     "new_text": "Reporting is mandatory within 48 hours of incident. Penalty: $10,000/day for non-compliance."},
    {"chunk_id": "b2c3d4e5", "change_type": "added", "risk_level": "high",
     "risk_keywords": ["prohibited", "sanctions"],
     "old_text": None,
     "new_text": "Section 5.3 (NEW): Transactions with sanctioned entities are strictly prohibited under updated OFAC guidelines."},
    {"chunk_id": "c3d4e5f6", "change_type": "modified", "risk_level": "medium",
     "risk_keywords": ["required", "must", "submit"],
     "old_text": "Quarterly reports must be submitted within 45 days of quarter end.",
     "new_text": "Quarterly reports must be submitted within 30 days of quarter end. Late submission requires written explanation."},
    {"chunk_id": "d4e5f6g7", "change_type": "modified", "risk_level": "medium",
     "risk_keywords": ["required", "deadline"],
     "old_text": "Enhanced Due Diligence (EDD) recommended for high-risk customers within 30 days.",
     "new_text": "Enhanced Due Diligence (EDD) is now required for all high-risk customers within 15 days of onboarding."},
    {"chunk_id": "e5f6g7h8", "change_type": "added", "risk_level": "medium",
     "risk_keywords": ["must", "certify"],
     "old_text": None,
     "new_text": "Section 7.1 (NEW): All compliance officers must certify completion of updated AML training annually."},
    {"chunk_id": "f6g7h8i9", "change_type": "modified", "risk_level": "low",
     "risk_keywords": ["recommended", "should"],
     "old_text": "Internal audits are recommended on an annual basis.",
     "new_text": "Internal audits are recommended bi-annually. External audits encouraged every 3 years."},
    {"chunk_id": "g7h8i9j0", "change_type": "removed", "risk_level": "low",
     "risk_keywords": ["guidance"],
     "old_text": "Appendix C: Legacy guidance on paper-based record keeping (superseded).",
     "new_text": None},
    {"chunk_id": "h8i9j0k1", "change_type": "modified", "risk_level": "none",
     "risk_keywords": [],
     "old_text": "Document version: 1.2 | Effective: January 2024",
     "new_text": "Document version: 2.0 | Effective: January 2025"},
]

_MOCK_IMPACT_ANSWER = """## Key Regulatory Changes Identified

**1. Incident Reporting Deadline (HIGH RISK)**
The reporting window has been cut from 5 business days to 48 hours. This is a material change requiring immediate process updates — your current workflow likely cannot meet this deadline without automation.

**2. Sanctions Compliance (HIGH RISK)**
A new explicit prohibition on OFAC-sanctioned entity transactions has been added. If not already in place, a real-time sanctions screening integration should be prioritised before the effective date.

**3. Quarterly Reporting Acceleration (MEDIUM RISK)**
Submission deadline tightened from 45 to 30 days. Review your data aggregation pipeline to confirm this is achievable.

**4. EDD Now Mandatory (MEDIUM RISK)**
Enhanced Due Diligence has shifted from recommended to required, with a tighter 15-day window. Update onboarding workflows and escalation triggers accordingly.

## Top 5 Action Items

1. ⚠️ Redesign incident reporting workflow to meet the 48-hour mandatory deadline
2. ⚠️ Integrate real-time OFAC/sanctions screening if not already operational
3. 📋 Update quarterly reporting pipeline to deliver within 30 days
4. 📋 Revise KYC/onboarding procedures to enforce 15-day EDD requirement
5. 📋 Schedule mandatory AML training certification for all compliance staff
"""


class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.last_upload_meta: Optional[dict] = None
        self.last_error: Optional[str] = None
        # Auto-detect mock mode; can be overridden by caller
        self._mock = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
        self._mock_docs: dict = {}   # doc_id → {filename, text, ...}
        self._mock_sessions: dict = {}

    @property
    def is_mock(self) -> bool:
        return self._mock

    def set_mock(self, enabled: bool):
        self._mock = enabled

    def ping(self) -> bool:
        """Check if backend is reachable. Sets mock mode if not."""
        try:
            r = self.session.get(f"{self.base_url}/api/v1/health", timeout=3)
            reachable = r.status_code == 200
            if not reachable:
                self._mock = True
            return reachable
        except Exception:
            self._mock = True
            return False

    # ── Upload ────────────────────────────────────────────────────────────────
    def upload(self, file) -> Optional[str]:
        self.last_error = None
        self.last_upload_meta = None

        if self._mock:
            return self._mock_upload(file)

        try:
            resp = self.session.post(
                f"{self.base_url}/api/v1/upload",
                files={"file": (file.name, file.getvalue(),
                                file.type or "application/octet-stream")},
                timeout=60,
            )
            if resp.status_code == 400:
                self.last_error = "Unsupported file type. Accepted: PDF, TXT, CSV, JSON, DOCX, XLSX, PPTX."
                return None
            if resp.status_code == 413:
                self.last_error = "File is too large. Maximum size is 50 MB."
                return None
            if resp.status_code == 422:
                self.last_error = resp.json().get("detail", "Could not extract text from this file.")
                return None
            resp.raise_for_status()
            data = resp.json()
            self.last_upload_meta = data
            return data["doc_id"]
        except requests.ConnectionError:
            # Auto-switch to mock on first connection failure
            self._mock = True
            logger.warning("Backend unreachable — switching to demo mode")
            return self._mock_upload(file)
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            self.last_error = str(e)
            return None

    def _mock_upload(self, file) -> str:
        """Parse file client-side for metadata; store minimal info."""
        name = file.name or "unknown"
        ext = Path(name).suffix.lower()
        data = file.getvalue()
        doc_id = str(uuid.uuid4())

        # Basic metadata without full parsing
        char_count = len(data)
        page_count = None
        fmt = ext.lstrip(".")

        # Rough text extraction for display
        if ext == ".txt":
            try:
                text = data.decode("utf-8", errors="replace")
                char_count = len(text)
            except Exception:
                pass
        elif ext == ".pdf":
            page_count = max(1, data.count(b"/Page "))  # rough heuristic

        meta = {
            "doc_id": doc_id,
            "filename": name,
            "char_count": char_count,
            "page_count": page_count,
            "format": fmt,
        }
        self._mock_docs[doc_id] = meta
        self.last_upload_meta = meta
        return doc_id

    # ── Compare ───────────────────────────────────────────────────────────────
    def compare(self, old_doc_id, new_doc_id, country, industry, role, language) -> Optional[dict]:
        self.last_error = None

        if self._mock:
            return self._mock_compare(old_doc_id, new_doc_id, country, industry, role)

        try:
            resp = self.session.post(
                f"{self.base_url}/api/v1/compare",
                json={"old_doc_id": old_doc_id, "new_doc_id": new_doc_id,
                      "country": country, "industry": industry,
                      "role": role, "language": language},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            self._mock = True
            return self._mock_compare(old_doc_id, new_doc_id, country, industry, role)
        except Exception as e:
            logger.error(f"Compare failed: {e}")
            self.last_error = str(e)
            return None

    def _mock_compare(self, old_doc_id, new_doc_id, country, industry, role) -> dict:
        from app.core.compliance_registry import COMPLIANCE_REGISTRY
        agency_data = COMPLIANCE_REGISTRY.get(
            (country.lower(), industry.lower()),
            {"agencies": ["Demo Agency"], "key_regs": ["Demo Regulation"]}
        )
        old_meta = self._mock_docs.get(old_doc_id, {"filename": "old_document"})
        new_meta = self._mock_docs.get(new_doc_id, {"filename": "new_document"})
        session_id = str(uuid.uuid4())

        result = {
            "session_id": session_id,
            "pair_id": hashlib.md5(f"{old_doc_id}{new_doc_id}".encode()).hexdigest()[:12],
            "old_filename": old_meta.get("filename", "old_document"),
            "new_filename": new_meta.get("filename", "new_document"),
            "similarity_score": 0.74,
            "diff_summary": {
                "total_chunks": len(_MOCK_DIFF_CHUNKS),
                "added": sum(1 for c in _MOCK_DIFF_CHUNKS if c["change_type"] == "added"),
                "removed": sum(1 for c in _MOCK_DIFF_CHUNKS if c["change_type"] == "removed"),
                "modified": sum(1 for c in _MOCK_DIFF_CHUNKS if c["change_type"] == "modified"),
                "unchanged": 142,
                "high_risk": sum(1 for c in _MOCK_DIFF_CHUNKS if c["risk_level"] == "high"),
                "medium_risk": sum(1 for c in _MOCK_DIFF_CHUNKS if c["risk_level"] == "medium"),
                "low_risk": sum(1 for c in _MOCK_DIFF_CHUNKS if c["risk_level"] == "low"),
            },
            "diff_chunks": _MOCK_DIFF_CHUNKS,
            "regulatory_impact": {
                "answer": _MOCK_IMPACT_ANSWER,
                "sources": [
                    {"label": "OLD", "excerpt": "Reporting is optional within 5 business days..."},
                    {"label": "NEW", "excerpt": "Reporting is mandatory within 48 hours..."},
                ],
                "tokens_used": 0,
                "grounding_confidence": 0.82,
                "pii_sanitized": False,
            },
            "compliance_context": {
                "country": country,
                "industry": industry,
                "role": role,
                "agencies": agency_data["agencies"],
                "key_regulations": agency_data["key_regs"],
            },
            "pii_stats": {"old_doc_redactions": 0, "new_doc_redactions": 0},
            "_demo_mode": True,
        }
        self._mock_sessions[session_id] = result
        return result

    # ── Query ─────────────────────────────────────────────────────────────────
    def query(self, session_id: str, question: str, language: str = "en") -> Optional[dict]:
        self.last_error = None

        if self._mock:
            return self._mock_query(question)

        try:
            resp = self.session.post(
                f"{self.base_url}/api/v1/compare/{session_id}/query",
                json={"question": question, "language": language},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            self._mock = True
            return self._mock_query(question)
        except Exception as e:
            logger.error(f"Query failed: {e}")
            self.last_error = str(e)
            return None

    def _mock_query(self, question: str) -> dict:
        q = question.lower()
        if any(w in q for w in ["penalty", "fine", "sanction"]):
            answer = "**Demo:** The updated policy introduces a $10,000/day penalty for late incident reporting. Sanctions compliance has also been tightened with an explicit OFAC prohibition."
        elif any(w in q for w in ["deadline", "report", "submit"]):
            answer = "**Demo:** Two deadlines changed: incident reporting reduced from 5 days → 48 hours (HIGH risk), and quarterly reports from 45 days → 30 days (MEDIUM risk)."
        elif any(w in q for w in ["edd", "kyc", "due diligence"]):
            answer = "**Demo:** Enhanced Due Diligence shifted from recommended to mandatory, with the completion window cut from 30 to 15 days post-onboarding."
        else:
            answer = f"**Demo mode:** This is a simulated answer for *\"{question}\"*. Connect a running backend to get real RAG-grounded answers from your documents."
        return {
            "answer": answer,
            "sources": [{"label": "DEMO", "excerpt": "Demo mode — no real document indexed."}],
            "tokens_used": 0,
            "grounding_confidence": 0.0,
            "pii_sanitized": False,
        }

    # ── Export ────────────────────────────────────────────────────────────────
    def export_pdf(self, session_id: str) -> Optional[bytes]:
        self.last_error = None

        if self._mock:
            return None  # caller shows JSON fallback message in demo mode

        try:
            resp = self.session.get(
                f"{self.base_url}/api/v1/export/{session_id}/pdf", timeout=30
            )
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            self.last_error = str(e)
            return None