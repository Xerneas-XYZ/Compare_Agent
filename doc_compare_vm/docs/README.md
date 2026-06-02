# Document Comparison Agent

Agentic regulatory document comparison platform for **banking, insurance, and healthcare**.

## Features
- **7 formats**: PDF, TXT, CSV, JSON, DOCX, XLSX, PPTX
- **Side-by-side diff viewer** with colour-coded risk highlighting (HIGH/MEDIUM/LOW)
- **Regulatory impact analysis** via RAG — grounded, no hallucination of agency names
- **PII masking** before any LLM call (regex + spaCy NER)
- **6 languages**: English, Spanish, Hindi, Mandarin, Russian, German
- **6 countries**: USA, UK, India, China, Russia, Germany
- **3 roles**: Compliance Officer, Legal Consultant, General User
- **Export**: PDF report, JSON

## Quick Start

```bash
# 1. Clone
git clone https://github.com/your-org/doc-compare-agent && cd doc-compare-agent

# 2. Set env vars
cp .env.example .env
# Edit .env: set OPENAI_API_KEY

# 3. Run with Docker Compose
cd infra/docker
docker compose up --build

# 4. Open
# Frontend: http://localhost:8501
# API docs: http://localhost:8000/api/docs
```

## Architecture

```
User → Streamlit UI (8501)
         ↓ REST
     FastAPI Backend (8000)
         ├── Document Parser    (pdfplumber, docx, openpyxl, pptx)
         ├── PII Masker         (regex + spaCy NER)
         ├── Diff Engine        (difflib + risk keyword scoring)
         ├── RAG Pipeline       (FAISS + text-embedding-3-small + gpt-4o-mini)
         ├── Comparison Agent   (LangChain ReAct)
         └── Guardrails         (input validation + output PII scan)
```

See `docs/ARCHITECTURE.md` for full detail.

## Cost Optimization
- Default model: `gpt-4o-mini` (20x cheaper than GPT-4o)
- Embedding: `text-embedding-3-small` (5x cheaper than ada-002)
- Chunk size: 800 tokens, overlap 80
- LLM max_tokens: 1024 per call
- Diff is computed deterministically (no LLM) — LLM only called for impact summary + Q&A
- PII masking uses regex/spaCy (zero cost)

## Environment Variables

| Variable | Default | Required |
|---|---|---|
| `OPENAI_API_KEY` | — | ✅ |
| `LLM_MODEL` | `gpt-4o-mini` | No |
| `LANGSMITH_API_KEY` | — | No |
| `SECRET_KEY` | — | ✅ in prod |
| `MAX_FILE_SIZE_MB` | `50` | No |

## Running Tests

```bash
cd backend
pytest tests/test_core.py -v          # unit tests (no API key needed)
pytest observability/evals/ -v        # DeepEval RAG quality (needs OPENAI_API_KEY)
```

## Deployment

See `docs/RUNBOOK.md` for AWS ECS/ALB deployment steps.