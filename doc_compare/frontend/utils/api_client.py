"""
API client with mock/demo mode.
Mock mode activates automatically when backend is unreachable.
"""
import logging
import os
import uuid
import hashlib
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Language-aware mock content ───────────────────────────────────────────────
_MOCK_IMPACT = {
    "en": """## Key Regulatory Changes (Demo)

**1. Incident Reporting — HIGH RISK**
Deadline cut from 5 business days → 48 hours. Immediate process redesign required.

**2. Sanctions Compliance — HIGH RISK**
New explicit OFAC prohibition added. Real-time screening integration needed.

**3. Quarterly Reporting — MEDIUM RISK**
Submission window tightened from 45 → 30 days.

**4. EDD Now Mandatory — MEDIUM RISK**
Enhanced Due Diligence shifted from recommended to required within 15 days.

## Top 5 Action Items
1. Redesign incident reporting workflow for 48-hour deadline
2. Integrate real-time sanctions screening
3. Update quarterly reporting pipeline
4. Revise KYC onboarding for 15-day EDD requirement
5. Schedule mandatory AML training certification""",

    "zh": """## 主要监管变化（演示）

**1. 事件报告 — 高风险**
截止时间从5个工作日缩短为48小时。需要立即重新设计流程。

**2. 制裁合规 — 高风险**
新增明确的OFAC禁令。需要实时筛查集成。

**3. 季度报告 — 中等风险**
提交窗口从45天缩短至30天。

**4. EDD现为强制性 — 中等风险**
增强尽职调查从建议变为强制，须在15天内完成。

## 前5项行动事项
1. 重新设计事件报告工作流程以满足48小时截止时间
2. 整合实时制裁筛查系统
3. 更新季度报告流程
4. 修订KYC入职流程以符合15天EDD要求
5. 安排强制性反洗钱培训认证""",

    "hi": """## प्रमुख नियामक परिवर्तन (डेमो)

**1. घटना रिपोर्टिंग — उच्च जोखिम**
समय सीमा 5 कार्य दिवस से घटाकर 48 घंटे कर दी गई।

**2. प्रतिबंध अनुपालन — उच्च जोखिम**
नया OFAC प्रतिबंध जोड़ा गया। रीयल-टाइम स्क्रीनिंग आवश्यक।

**3. त्रैमासिक रिपोर्टिंग — मध्यम जोखिम**
सबमिशन विंडो 45 से 30 दिन कर दी गई।

**4. EDD अब अनिवार्य — मध्यम जोखिम**
उन्नत उचित परिश्रम 15 दिनों में पूरा करना अनिवार्य।""",

    "de": """## Wichtige regulatorische Änderungen (Demo)

**1. Vorfallmeldung — HOHES RISIKO**
Frist von 5 Werktagen auf 48 Stunden verkürzt.

**2. Sanktions-Compliance — HOHES RISIKO**
Neues explizites OFAC-Verbot hinzugefügt.

**3. Quartalsberichte — MITTLERES RISIKO**
Einreichungsfenster von 45 auf 30 Tage verkürzt.

**4. EDD jetzt verpflichtend — MITTLERES RISIKO**
Erweiterte Sorgfaltspflicht innerhalb von 15 Tagen erforderlich.""",

    "es": """## Cambios Regulatorios Principales (Demo)

**1. Reporte de Incidentes — ALTO RIESGO**
Plazo reducido de 5 días hábiles a 48 horas.

**2. Cumplimiento de Sanciones — ALTO RIESGO**
Nueva prohibición OFAC añadida. Se requiere detección en tiempo real.

**3. Informes Trimestrales — RIESGO MEDIO**
Ventana de envío reducida de 45 a 30 días.

**4. DDR Ahora Obligatoria — RIESGO MEDIO**
Diligencia debida mejorada obligatoria en 15 días.""",

    "ru": """## Основные регуляторные изменения (Демо)

**1. Отчётность об инцидентах — ВЫСОКИЙ РИСК**
Срок сокращён с 5 рабочих дней до 48 часов.

**2. Соблюдение санкций — ВЫСОКИЙ РИСК**
Добавлен новый явный запрет OFAC.

**3. Ежеквартальная отчётность — СРЕДНИЙ РИСК**
Окно подачи сокращено с 45 до 30 дней.

**4. РДД теперь обязательна — СРЕДНИЙ РИСК**
Расширенная проверка должна быть завершена в течение 15 дней.""",
}

_MOCK_DIFF_CHUNKS = [
    {"chunk_id": "a1b2c3d4", "change_type": "modified", "risk_level": "high",
     "risk_keywords": ["mandatory", "penalty"],
     "old_text": "Reporting is optional within 5 business days of incident.",
     "new_text": "Reporting is mandatory within 48 hours. Penalty: $10,000/day."},
    {"chunk_id": "b2c3d4e5", "change_type": "added", "risk_level": "high",
     "risk_keywords": ["prohibited", "sanctions"],
     "old_text": None,
     "new_text": "Section 5.3 (NEW): Transactions with sanctioned entities are strictly prohibited."},
    {"chunk_id": "c3d4e5f6", "change_type": "modified", "risk_level": "medium",
     "risk_keywords": ["required", "must", "submit"],
     "old_text": "Quarterly reports must be submitted within 45 days of quarter end.",
     "new_text": "Quarterly reports must be submitted within 30 days of quarter end."},
    {"chunk_id": "d4e5f6g7", "change_type": "modified", "risk_level": "medium",
     "risk_keywords": ["required", "deadline"],
     "old_text": "EDD recommended for high-risk customers within 30 days.",
     "new_text": "EDD is now required for all high-risk customers within 15 days."},
    {"chunk_id": "e5f6g7h8", "change_type": "added", "risk_level": "medium",
     "risk_keywords": ["must", "certify"],
     "old_text": None,
     "new_text": "Section 7.1 (NEW): All compliance officers must certify AML training annually."},
    {"chunk_id": "f6g7h8i9", "change_type": "modified", "risk_level": "low",
     "risk_keywords": ["recommended"],
     "old_text": "Internal audits are recommended annually.",
     "new_text": "Internal audits are recommended bi-annually."},
    {"chunk_id": "g7h8i9j0", "change_type": "removed", "risk_level": "low",
     "risk_keywords": [],
     "old_text": "Appendix C: Legacy guidance on paper-based record keeping (superseded).",
     "new_text": None},
    {"chunk_id": "h8i9j0k1", "change_type": "modified", "risk_level": "none",
     "risk_keywords": [],
     "old_text": "Document version: 1.2 | Effective: January 2024",
     "new_text": "Document version: 2.0 | Effective: January 2025"},
]

_AGENCIES = {
    ("usa","banking"):     {"agencies":["Federal Reserve","OCC","FDIC","CFPB"],"key_regs":["Dodd-Frank","BSA/AML","GLBA","Basel III"]},
    ("usa","insurance"):   {"agencies":["NAIC","State DOIs","FIO"],            "key_regs":["ACA","ERISA","McCarran-Ferguson"]},
    ("usa","healthcare"):  {"agencies":["CMS","FDA","OCR","HHS"],              "key_regs":["HIPAA","HITECH","ACA"]},
    ("uk","banking"):      {"agencies":["PRA","FCA","Bank of England"],        "key_regs":["FSMA 2000","SMCR","PSD2","UK GDPR"]},
    ("uk","insurance"):    {"agencies":["PRA","FCA"],                          "key_regs":["Solvency II","Consumer Duty","UK GDPR"]},
    ("uk","healthcare"):   {"agencies":["CQC","MHRA","NHS England"],           "key_regs":["Health & Social Care Act 2012","UK GDPR"]},
    ("india","banking"):   {"agencies":["RBI","SEBI","FIU-IND"],               "key_regs":["Banking Regulation Act","FEMA","PMLA","Basel III"]},
    ("india","insurance"): {"agencies":["IRDAI"],                              "key_regs":["Insurance Act 1938","PMLA"]},
    ("india","healthcare"):{"agencies":["CDSCO","NMC","NABH"],                 "key_regs":["Drugs & Cosmetics Act","DPDP Act 2023"]},
    ("china","banking"):   {"agencies":["PBOC","CBIRC","CSRC"],                "key_regs":["Commercial Banking Law","PIPL","Data Security Law"]},
    ("china","insurance"): {"agencies":["CBIRC"],                              "key_regs":["Insurance Law of PRC","PIPL"]},
    ("china","healthcare"):{"agencies":["NMPA","NHC"],                         "key_regs":["Drug Administration Law","PIPL"]},
    ("russia","banking"):  {"agencies":["Bank of Russia (CBR)"],               "key_regs":["Federal Law on Banks","AML/CFT Law 115-FZ"]},
    ("russia","insurance"):{"agencies":["Bank of Russia (CBR)"],               "key_regs":["Law on Insurance Business","CBR Regulations"]},
    ("russia","healthcare"):{"agencies":["Roszdravnadzor"],                    "key_regs":["Federal Law 323-FZ","Personal Data Law 152-FZ"]},
    ("germany","banking"): {"agencies":["BaFin","Bundesbank","ECB"],           "key_regs":["KWG","MiFID II","Basel III","GDPR","DORA"]},
    ("germany","insurance"):{"agencies":["BaFin"],                             "key_regs":["VAG","Solvency II","IDD","GDPR"]},
    ("germany","healthcare"):{"agencies":["BfArM","GKV-SV"],                  "key_regs":["SGB V","GDPR","MDR 2017/745"]},
}


class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.last_upload_meta: Optional[dict] = None
        self.last_error: Optional[str] = None
        self._mock = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
        self._mock_docs: dict = {}
        self._mock_sessions: dict = {}

    @property
    def is_mock(self) -> bool:
        return self._mock

    def set_mock(self, enabled: bool):
        self._mock = enabled

    def ping(self) -> bool:
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
                f"{self.base_url}/api/v1/upload/",
                files={"file": (file.name, file.getvalue(),
                                file.type or "application/octet-stream")},
                timeout=120,
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
        except requests.ReadTimeout:
            self.last_error = (
                "Upload timed out after 120 seconds. "
                "The backend may be busy or the file is large. Try again or reduce file size."
            )
            return None
        except requests.ConnectionError:
            self._mock = True
            return self._mock_upload(file)
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            self.last_error = str(e)
            return None

    def _mock_upload(self, file) -> str:
        name = file.name or "unknown"
        ext = Path(name).suffix.lower()
        data = file.getvalue()
        # Use content hash as doc_id so same file → same doc_id deterministically
        doc_id = hashlib.sha256(data).hexdigest()[:32]
        char_count = len(data)
        page_count = None
        if ext == ".txt":
            try:
                char_count = len(data.decode("utf-8", errors="replace"))
            except Exception:
                pass
        elif ext == ".pdf":
            page_count = max(1, data.count(b"/Page "))
        meta = {
            "doc_id": doc_id,
            "filename": name,
            "char_count": char_count,
            "page_count": page_count,
            "format": ext.lstrip("."),
            "_content_hash": doc_id,  # exposed so compare can detect identical docs
        }
        self._mock_docs[doc_id] = meta
        self.last_upload_meta = meta
        return doc_id

    # ── Compare ───────────────────────────────────────────────────────────────
    def compare(self, old_doc_id, new_doc_id, country, industry, role, language) -> Optional[dict]:
        self.last_error = None
        if self._mock:
            return self._mock_compare(old_doc_id, new_doc_id, country, industry, role, language)
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
            return self._mock_compare(old_doc_id, new_doc_id, country, industry, role, language)
        except Exception as e:
            logger.error(f"Compare failed: {e}")
            self.last_error = str(e)
            return None

    def _mock_compare(self, old_doc_id, new_doc_id, country, industry, role, language) -> dict:
        agency_data = _AGENCIES.get(
            (country.lower(), industry.lower()),
            {"agencies": ["Demo Agency"], "key_regs": ["Demo Regulation"]}
        )
        old_meta = self._mock_docs.get(old_doc_id, {"filename": "old_document"})
        new_meta = self._mock_docs.get(new_doc_id, {"filename": "new_document"})

        # Detect identical documents — same content hash means same file
        same_doc = old_doc_id == new_doc_id
        if same_doc:
            similarity = 1.0
            chunks = []   # no changes
            diff_summary = {
                "total_chunks": 0, "added": 0, "removed": 0,
                "modified": 0, "unchanged": 0,
                "high_risk": 0, "medium_risk": 0, "low_risk": 0,
            }
            lang_notices = {
                "zh": "两份文件内容完全相同。未检测到任何更改。",
                "hi": "दोनों दस्तावेज़ समान हैं। कोई परिवर्तन नहीं मिला।",
                "de": "Beide Dokumente sind identisch. Keine Änderungen gefunden.",
                "es": "Ambos documentos son idénticos. No se encontraron cambios.",
                "ru": "Оба документа идентичны. Изменений не обнаружено.",
                "en": "Both documents are identical. No changes detected.",
            }
            impact_answer = lang_notices.get(language, lang_notices["en"])
        else:
            similarity = 0.74
            chunks = _MOCK_DIFF_CHUNKS
            diff_summary = {
                "total_chunks": len(chunks),
                "added":    sum(1 for c in chunks if c["change_type"] == "added"),
                "removed":  sum(1 for c in chunks if c["change_type"] == "removed"),
                "modified": sum(1 for c in chunks if c["change_type"] == "modified"),
                "unchanged": 142,
                "high_risk":   sum(1 for c in chunks if c["risk_level"] == "high"),
                "medium_risk": sum(1 for c in chunks if c["risk_level"] == "medium"),
                "low_risk":    sum(1 for c in chunks if c["risk_level"] == "low"),
            }
            impact_answer = _MOCK_IMPACT.get(language, _MOCK_IMPACT["en"])

        session_id = str(uuid.uuid4())
        result = {
            "session_id": session_id,
            "pair_id": hashlib.md5(f"{old_doc_id}{new_doc_id}".encode()).hexdigest()[:12],
            "old_filename": old_meta.get("filename", "old_document"),
            "new_filename": new_meta.get("filename", "new_document"),
            "similarity_score": similarity,
            "diff_summary": diff_summary,
            "diff_chunks": chunks,
            "regulatory_impact": {
                "answer": impact_answer,
                "sources": [] if same_doc else [
                    {"label": "OLD", "excerpt": "Reporting is optional within 5 business days..."},
                    {"label": "NEW", "excerpt": "Reporting is mandatory within 48 hours..."},
                ],
                "tokens_used": 0,
                "grounding_confidence": 1.0 if same_doc else 0.82,
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
            "_language": language,
        }
        self._mock_sessions[session_id] = result
        return result

    # ── Query ─────────────────────────────────────────────────────────────────
    def query(self, session_id: str, question: str, language: str = "en") -> Optional[dict]:
        self.last_error = None
        if self._mock:
            return self._mock_query(question, language)
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
            return self._mock_query(question, language)
        except Exception as e:
            logger.error(f"Query failed: {e}")
            self.last_error = str(e)
            return None

    def _mock_query(self, question: str, language: str = "en") -> dict:
        q = question.lower()
        answers = {
            "en": {
                "penalty": "**Demo:** The updated policy introduces a $10,000/day penalty for late incident reporting.",
                "deadline": "**Demo:** Incident reporting reduced from 5 days → 48 hours (HIGH), quarterly reports from 45 → 30 days (MEDIUM).",
                "edd": "**Demo:** EDD shifted from recommended to mandatory, completion window cut from 30 to 15 days.",
                "default": f"**Demo mode:** Simulated answer for \"{question}\". Connect a running backend for real RAG answers.",
            },
            "zh": {
                "penalty": "**演示：** 更新后的政策对迟交事件报告处以每日10,000美元罚款。",
                "deadline": "**演示：** 事件报告时限从5天缩短为48小时（高风险），季度报告从45天缩短为30天（中等风险）。",
                "edd": "**演示：** EDD从建议变为强制性，完成时限从30天缩短至15天。",
                "default": f"**演示模式：** 《{question}》的模拟回答。连接后端以获取真实RAG答案。",
            },
        }
        lang_answers = answers.get(language, answers["en"])
        if any(w in q for w in ["penalty", "fine", "sanction", "罚款", "制裁"]):
            answer = lang_answers["penalty"]
        elif any(w in q for w in ["deadline", "report", "submit", "截止", "期限"]):
            answer = lang_answers["deadline"]
        elif any(w in q for w in ["edd", "kyc", "due diligence", "尽职"]):
            answer = lang_answers["edd"]
        else:
            answer = lang_answers["default"]
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
            return None
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