# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS ECS / ALB                            │
│                                                                 │
│  ┌──────────────────┐        ┌──────────────────────────────┐   │
│  │  Streamlit UI    │◄──────►│     FastAPI Backend          │   │
│  │  Port 8501       │  REST  │     Port 8000                │   │
│  │                  │        │                              │   │
│  │  - Upload panel  │        │  ┌────────────────────────┐  │   │
│  │  - Diff viewer   │        │  │  Document Parser       │  │   │
│  │  - Impact panel  │        │  │  pdf/txt/csv/json/      │  │   │
│  │  - Q&A chat      │        │  │  docx/xlsx/pptx        │  │   │
│  │  - Export        │        │  └────────────────────────┘  │   │
│  └──────────────────┘        │  ┌────────────────────────┐  │   │
│                              │  │  PII Masker            │  │   │
│                              │  │  regex + spaCy NER     │  │   │
│                              │  └────────────────────────┘  │   │
│                              │  ┌────────────────────────┐  │   │
│                              │  │  Diff Engine           │  │   │
│                              │  │  difflib + risk KW     │  │   │
│                              │  └────────────────────────┘  │   │
│                              │  ┌────────────────────────┐  │   │
│                              │  │  RAG Pipeline          │  │   │
│                              │  │  FAISS + embeddings    │  │   │
│                              │  │  + gpt-4o-mini         │  │   │
│                              │  └────────────────────────┘  │   │
│                              │  ┌────────────────────────┐  │   │
│                              │  │  Guardrails            │  │   │
│                              │  │  input + output checks │  │   │
│                              │  └────────────────────────┘  │   │
│                              └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                        │
                             ┌──────────┴──────────┐
                             │   External APIs      │
                             │  OpenAI API          │
                             │  LangSmith (opt)     │
                             └─────────────────────┘
```

## Request Flow

```
1. User uploads OLD doc + NEW doc
   → FastAPI /upload → Parser → text extracted
   → doc_id returned (UUID)

2. User clicks Compare
   → FastAPI /compare
   → PII masker runs on both texts (regex + NER)
   → Guardrail validates input (injection check, size check)
   → Diff Engine computes structural diff (difflib)
   → Risk scorer tags each chunk (keyword matching — no LLM)
   → RAG pipeline: chunks embedded → FAISS indexed
   → LLM called ONCE for impact summary (max 1024 tokens)
   → LLM output scanned for PII leakage
   → Grounding confidence computed
   → session_id returned

3. Follow-up Q&A
   → FastAPI /compare/{session_id}/query
   → RAG retrieves top-4 chunks
   → LLM answers (max 1024 tokens)
   → PII scan on output

4. Export
   → /export/{session_id}/pdf  → reportlab PDF
   → /export/{session_id}/json → raw result
```

## Token Budget per Comparison

| Operation | Model | Tokens (est.) |
|---|---|---|
| Embedding (800-char chunk × N) | text-embedding-3-small | ~N × 200 |
| Impact summary | gpt-4o-mini | ~2000 in / 500 out |
| Q&A per question | gpt-4o-mini | ~1500 in / 400 out |
| PII masking | none (regex/spaCy) | $0 |
| Diff engine | none (difflib) | $0 |

Estimated cost per full comparison: **~$0.002–0.005** with gpt-4o-mini.

## Data Flow — PII Guarantee

```
Raw doc bytes
    ↓
Parser (text extraction)
    ↓
PII Masker Layer 1: Regex (SSN, email, CC, IBAN, Aadhar, PAN, NHS...)
    ↓
PII Masker Layer 2: spaCy NER (PERSON entities)
    ↓ [REDACTED] tokens replace PII
LLM / RAG (never sees raw PII)
    ↓
Output PII scan (post-LLM)
    ↓
Response to UI
```

## Compliance Registry

`app/core/compliance_registry.py` is the single source of truth for all agencies and regulations.
The LLM is **never asked to generate** agency names or regulation titles — it only references
what's passed in the prompt from this registry. This eliminates hallucination of regulation names.

## Scalability

- FAISS index is in-memory per process. For multi-instance ECS, replace with a
  persistent vector store (Pinecone, pgvector, Weaviate).
- Session store is in-memory dict. Replace with ElastiCache Redis for multi-instance.
- File uploads go to local `/tmp`. Replace with S3 presigned URL upload for production.