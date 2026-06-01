# Endpoint Contracts

## POST /api/v1/upload

**Request**: `multipart/form-data`
- `file`: one of `.pdf .txt .csv .json .docx .xlsx .pptx`, max 50MB

**Response 200**:
```json
{
  "doc_id": "uuid-string",
  "filename": "policy_v2.pdf",
  "char_count": 42000,
  "page_count": 12,
  "format": "pdf"
}
```

**Errors**: 400 (bad extension), 413 (too large), 422 (parse failure)

---

## POST /api/v1/compare

**Request**:
```json
{
  "old_doc_id": "uuid",
  "new_doc_id": "uuid",
  "country": "usa|uk|india|china|russia|germany",
  "industry": "banking|insurance|healthcare",
  "role": "compliance_officer|general_user|legal_consultant",
  "language": "en|es|hi|zh|ru|de",
  "risk_filter": "none|low|medium|high"
}
```

**Response 200**:
```json
{
  "session_id": "uuid",
  "pair_id": "hash",
  "old_filename": "policy_v1.pdf",
  "new_filename": "policy_v2.pdf",
  "similarity_score": 0.82,
  "diff_summary": {
    "total_chunks": 140,
    "added": 12,
    "removed": 8,
    "modified": 24,
    "unchanged": 96,
    "high_risk": 5,
    "medium_risk": 15,
    "low_risk": 4
  },
  "diff_chunks": [
    {
      "chunk_id": "a1b2c3d4",
      "change_type": "modified",
      "risk_level": "high",
      "risk_keywords": ["mandatory", "penalty"],
      "old_text": "Reporting is optional within 5 business days.",
      "new_text": "Reporting is mandatory within 48 hours. Penalty: $10,000/day."
    }
  ],
  "regulatory_impact": {
    "answer": "## Key Regulatory Changes\n1. Reporting timeline reduced...",
    "sources": [{"label": "OLD", "excerpt": "..."}],
    "tokens_used": 1840,
    "grounding_confidence": 0.78,
    "pii_sanitized": false
  },
  "compliance_context": {
    "country": "usa",
    "industry": "banking",
    "role": "compliance_officer",
    "agencies": ["Federal Reserve", "OCC", "FDIC", "CFPB", "FinCEN"],
    "key_regulations": ["Dodd-Frank Act", "BSA/AML", "CRA", "GLBA", "Basel III"]
  },
  "pii_stats": {
    "old_doc_redactions": 3,
    "new_doc_redactions": 2
  }
}
```

---

## GET /api/v1/compare/{session_id}

Returns previously computed comparison result (same schema as above).

**Errors**: 404 if session expired or not found.

---

## POST /api/v1/compare/{session_id}/query

**Request**:
```json
{
  "question": "What are the new penalty clauses in Section 3?",
  "language": "en"
}
```

**Response 200**:
```json
{
  "answer": "Section 3 introduces a penalty of $10,000/day...",
  "sources": [{"label": "NEW", "excerpt": "Section 3.4: Penalty for..."}],
  "tokens_used": 420,
  "grounding_confidence": 0.85,
  "pii_sanitized": false
}
```

---

## GET /api/v1/export/{session_id}/pdf

Returns binary PDF. `Content-Type: application/pdf`

## GET /api/v1/export/{session_id}/json

Returns raw comparison JSON. `Content-Type: application/json`

---

## GET /api/v1/health

```json
{"status": "ok", "timestamp": "2025-01-01T00:00:00"}
```

## GET /api/v1/ready

```json
{
  "status": "ready",
  "checks": {"faiss": "ok", "pdfplumber": "ok"}
}
```