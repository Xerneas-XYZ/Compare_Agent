# Security

## PII Handling
- PII masked BEFORE any LLM call using deterministic regex + spaCy NER
- LLM output scanned post-generation for residual PII
- No raw document text stored in session state or logs
- Upload files written to ephemeral `/tmp` — cleared on container restart

## Prompt Injection
- Input documents scanned for injection patterns before processing
- Agent max_iterations=6 prevents runaway loops
- Static system prompt not modifiable by document content

## API Security
- CORS restricted to configured origins
- Secret key required (min 16 chars) for session signing
- File type validation (extension + content-type)
- File size hard cap (50MB default)
- Rate limiting: 30 requests/minute per IP (configurable)

## Infrastructure
- Non-root container user (`appuser`)
- Secrets via AWS Secrets Manager (never in env vars in prod)
- HTTPS enforced via ALB with TLS 1.3 policy
- HTTP → HTTPS redirect
- Health checks on both containers

## API Keys
- OpenAI API key: AWS Secrets Manager only in prod
- Never log API keys or user document content
- LangSmith tracing disabled unless explicitly enabled

## What is NOT covered (needs production hardening)
- Document-level encryption at rest (add KMS + S3 SSE)
- Audit log per user action (add structured logging + CloudWatch)
- RBAC enforcement (roles are advisory — add JWT + auth middleware)
- FAISS index persistence (in-memory only — add persistent vector DB)
- Multi-tenancy isolation (sessions share in-memory store — add Redis with key namespacing)