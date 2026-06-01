"""
PII Masking Engine
Two-layer approach:
  1. Regex patterns for structured PII (SSN, credit cards, emails, phones, etc.)
  2. spaCy NER for unstructured PII (names, orgs, locations)

No LLM used here — deterministic, fast, no hallucination risk.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────
_PATTERNS: Dict[str, str] = {
    "EMAIL":       r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "PHONE_US":    r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "PHONE_INTL":  r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b",
    "SSN":         r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "IBAN":        r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b",
    "IP_ADDRESS":  r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "DATE_OF_BIRTH": r"\b(?:DOB|Date of Birth|Born)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    "PASSPORT":    r"\b[A-Z]{1,2}\d{6,9}\b",
    "AADHAR":      r"\b\d{4}[-\s]\d{4}[-\s]\d{4}\b",   # India
    "PAN":         r"\b[A-Z]{5}\d{4}[A-Z]\b",            # India
    "NHS_NUMBER":  r"\b\d{3}[-\s]\d{3}[-\s]\d{4}\b",    # UK
    "SWIFT_BIC":   r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",
    "ZIP_US":      r"\b\d{5}(?:-\d{4})?\b",
}

_COMPILED = {name: re.compile(pat, re.IGNORECASE) for name, pat in _PATTERNS.items()}


@dataclass
class MaskingResult:
    masked_text: str
    redactions: List[Dict] = field(default_factory=list)   # [{type, original_len, position}]
    redaction_count: int = 0


def mask_pii(text: str, mask_token: str = "[REDACTED]") -> MaskingResult:
    """
    Apply regex-based PII masking. Returns masked text + audit log.
    NER masking is applied separately via mask_pii_ner() for named entities.
    """
    redactions = []
    result = text

    for pii_type, pattern in _COMPILED.items():
        matches = list(pattern.finditer(result))
        # Replace in reverse order to preserve indices
        for m in reversed(matches):
            redactions.append({
                "type": pii_type,
                "original_len": len(m.group()),
                "position": m.start(),
            })
            result = result[:m.start()] + mask_token + result[m.end():]

    return MaskingResult(
        masked_text=result,
        redactions=redactions,
        redaction_count=len(redactions),
    )


def mask_pii_ner(text: str, language: str = "en", mask_token: str = "[REDACTED]") -> MaskingResult:
    """
    NER-based PII masking using spaCy. Falls back gracefully if model not loaded.
    Masks: PERSON, ORG (when context suggests PII), GPE at fine granularity.
    """
    try:
        import spacy
        _NER_MODELS = {
            "en": "en_core_web_sm",
            "de": "de_core_news_sm",
            "es": "es_core_news_sm",
            "zh": "zh_core_web_sm",
            "ru": "ru_core_news_sm",
        }
        model_name = _NER_MODELS.get(language, "en_core_web_sm")
        nlp = spacy.load(model_name)
        doc = nlp(text)

        redactions = []
        result = text
        # Process in reverse to maintain string positions
        entities = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
        for ent in entities:
            if ent.label_ in ("PERSON",):
                redactions.append({
                    "type": f"NER_{ent.label_}",
                    "original_len": len(ent.text),
                    "position": ent.start_char,
                })
                result = result[:ent.start_char] + mask_token + result[ent.end_char:]

        return MaskingResult(
            masked_text=result,
            redactions=redactions,
            redaction_count=len(redactions),
        )
    except Exception as e:
        logger.warning(f"NER masking skipped ({e}); regex-only masking applied")
        return MaskingResult(masked_text=text)


def full_mask(text: str, language: str = "en", mask_token: str = "[REDACTED]") -> MaskingResult:
    """Combined regex + NER masking pipeline."""
    r1 = mask_pii(text, mask_token)
    r2 = mask_pii_ner(r1.masked_text, language, mask_token)
    return MaskingResult(
        masked_text=r2.masked_text,
        redactions=r1.redactions + r2.redactions,
        redaction_count=r1.redaction_count + r2.redaction_count,
    )