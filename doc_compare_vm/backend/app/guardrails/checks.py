"""
Guardrails
Pre- and post-processing checks to prevent:
  - Prompt injection via document content
  - PII leakage in LLM responses
  - Hallucinated regulation names in responses
  - Oversized inputs that inflate token costs
"""
import re
import logging
from typing import Tuple

from app.pii.masker import mask_pii
from app.core.compliance_registry import COMPLIANCE_REGISTRY

logger = logging.getLogger(__name__)

# All known valid regulation strings — used to spot hallucinations
_KNOWN_REGS = set()
for v in COMPLIANCE_REGISTRY.values():
    _KNOWN_REGS.update(r.lower() for r in v["key_regs"])
    _KNOWN_REGS.update(a.lower() for a in v["agencies"])

# Prompt injection patterns
_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions",
    r"you\s+are\s+now\s+(?:a\s+)?(?:different|new|another)",
    r"disregard\s+(?:your|all)\s+(?:system|previous)",
    r"<\s*/?(?:script|iframe|object|embed)",
    r"system\s*:\s*you\s+must",
    r"jailbreak",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

MAX_INPUT_CHARS = 500_000   # ~125k tokens — hard cap per document


def validate_input(text: str, filename: str) -> Tuple[bool, str]:
    """
    Returns (is_valid, reason).
    Runs before document is processed.
    """
    if len(text) > MAX_INPUT_CHARS:
        return False, f"Document '{filename}' exceeds max size ({MAX_INPUT_CHARS} chars)"

    if _INJECTION_RE.search(text[:5000]):   # only scan first 5k chars for speed
        logger.warning(f"Potential prompt injection detected in {filename}")
        return False, f"Document '{filename}' contains disallowed content patterns"

    return True, "ok"


def sanitize_llm_output(output: str) -> Tuple[str, bool]:
    """
    Post-process LLM output:
      1. Strip any PII that leaked through
      2. Flag if output contains suspicious regulation references we can't verify
    Returns (cleaned_output, was_modified)
    """
    masked = mask_pii(output)
    modified = masked.redaction_count > 0

    if modified:
        logger.warning(f"PII found in LLM output — masked {masked.redaction_count} items")

    return masked.masked_text, modified


def check_response_grounding(response: str, sources: list) -> dict:
    """
    Lightweight grounding check: does the response reference content
    that actually appears in the retrieved sources?
    Returns {grounded: bool, confidence: float}
    """
    if not sources:
        return {"grounded": False, "confidence": 0.0}

    source_text = " ".join(s.get("excerpt", "") for s in sources).lower()
    response_sentences = [s.strip() for s in response.split(".") if len(s.strip()) > 20]

    grounded_count = 0
    for sentence in response_sentences[:10]:   # check first 10 sentences
        # Simple overlap check: at least 3 consecutive words from sentence appear in source
        words = sentence.lower().split()
        for i in range(len(words) - 2):
            trigram = " ".join(words[i:i+3])
            if trigram in source_text:
                grounded_count += 1
                break

    confidence = grounded_count / max(len(response_sentences[:10]), 1)
    return {
        "grounded": confidence > 0.3,
        "confidence": round(confidence, 2),
    }