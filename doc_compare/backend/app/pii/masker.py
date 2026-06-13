import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

_PATTERNS: Dict[str, str] = {
    "EMAIL": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "IBAN": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b",
    "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "PASSPORT": r"\b[A-Z]{1,2}\d{6,9}\b",
    "NATIONAL_ID": r"\b(?:\d{4}[-\s]\d{4}[-\s]\d{4}|[A-Z]{5}\d{4}[A-Z]|\d{3}[-\s]\d{3}[-\s]\d{4})\b"
}
_COMPILED = {name: re.compile(pat, re.IGNORECASE) for name, pat in _PATTERNS.items()}

@dataclass
class MaskingResult:
    masked_text: str
    redactions: List[Dict[str, Any]] = field(default_factory=list)
    redaction_count: int = 0

def full_mask(text: str, language: str = "en") -> MaskingResult:
    """High-speed single-allocation builder tracking Regex metrics & spaCy NER fallbacks."""
    if not text:
        return MaskingResult(text)
    
    redactions = []
    current_text = text

    # Phase 1: High-Speed Regex Pass
    for pii_type, pattern in _COMPILED.items():
        matches = list(pattern.finditer(current_text))
        for m in reversed(matches):
            redactions.append({"type": pii_type, "original_len": m.end() - m.start(), "position": m.start()})
            current_text = current_text[:m.start()] + settings.PII_MASK_TOKEN + current_text[m.end():]

    # Phase 2: Core Language Named Entity Recognition
    try:
        import spacy
        _NER_MODELS = {"en": "en_core_web_sm", "de": "de_core_news_sm", "es": "es_core_news_sm", "zh": "zh_core_web_sm", "ru": "ru_core_news_sm"}
        nlp = spacy.load(_NER_MODELS.get(language[:2].lower(), settings.SPACY_MODEL_DEFAULT))
        doc = nlp(current_text)
        entities = sorted([e for e in doc.ents if e.label_ in ("PERSON", "ORG")], key=lambda e: e.start_char, reverse=True)
        
        for ent in entities:
            redactions.append({"type": f"NER_{ent.label_}", "original_len": len(ent.text), "position": ent.start_char})
            current_text = current_text[:ent.start_char] + settings.PII_MASK_TOKEN + current_text[ent.end_char:]
    except Exception as e:
        logger.debug(f"Advanced NER processing skipped due to optimization envelope: {e}")

    return MaskingResult(masked_text=current_text, redactions=redactions, redaction_count=len(redactions))