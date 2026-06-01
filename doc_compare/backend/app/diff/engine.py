"""
Diff Engine
Produces structured diffs between two document texts:
  - Line-level diff (for exact change tracking)
  - Section-level semantic diff (for regulatory impact detection)
  - Risk scoring per changed section (no hallucination — rule-based keywords)
"""
import difflib
import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


class ChangeType(str, Enum):
    ADDED    = "added"
    REMOVED  = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class RiskLevel(str, Enum):
    HIGH    = "high"
    MEDIUM  = "medium"
    LOW     = "low"
    NONE    = "none"


# ── Risk keyword lookup — deterministic, no hallucination ────────────────────
_RISK_KEYWORDS = {
    RiskLevel.HIGH: [
        "mandatory", "prohibited", "penalty", "fine", "sanction", "immediate",
        "terminate", "revoke", "suspended", "violation", "breach", "criminal",
        "imprisonment", "gdpr", "hipaa", "pci", "aml", "kyc", "fatf",
        "capital requirement", "solvency", "liquidity ratio",
    ],
    RiskLevel.MEDIUM: [
        "required", "must", "shall", "deadline", "compliance", "reporting",
        "disclosure", "audit", "review", "approval", "authorization",
        "notification", "submit", "certify",
    ],
    RiskLevel.LOW: [
        "recommended", "should", "may", "guidance", "best practice",
        "encouraged", "consider", "optional",
    ],
}


def _score_risk(text: str) -> RiskLevel:
    text_lower = text.lower()
    for level in (RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW):
        if any(kw in text_lower for kw in _RISK_KEYWORDS[level]):
            return level
    return RiskLevel.NONE


@dataclass
class DiffChunk:
    chunk_id: str
    change_type: ChangeType
    old_text: Optional[str]
    new_text: Optional[str]
    risk_level: RiskLevel
    risk_keywords: List[str] = field(default_factory=list)
    old_line_start: Optional[int] = None
    new_line_start: Optional[int] = None


@dataclass
class DiffResult:
    chunks: List[DiffChunk]
    summary: dict
    similarity_score: float   # 0.0 – 1.0


def _extract_keywords_found(text: str, level: RiskLevel) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in _RISK_KEYWORDS[level] if kw in text_lower]


def compute_diff(old_text: str, new_text: str) -> DiffResult:
    """
    Compute a structured diff between two documents.
    Uses SequenceMatcher for similarity + unified diff for chunks.
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    similarity = matcher.ratio()

    chunks: List[DiffChunk] = []
    summary = {
        "total_chunks": 0,
        "added": 0,
        "removed": 0,
        "modified": 0,
        "unchanged": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
    }

    opcodes = matcher.get_opcodes()

    for tag, i1, i2, j1, j2 in opcodes:
        old_chunk = "".join(old_lines[i1:i2]) if i1 < i2 else None
        new_chunk = "".join(new_lines[j1:j2]) if j1 < j2 else None

        if tag == "equal":
            change_type = ChangeType.UNCHANGED
            risk = RiskLevel.NONE
        elif tag == "insert":
            change_type = ChangeType.ADDED
            risk = _score_risk(new_chunk or "")
        elif tag == "delete":
            change_type = ChangeType.REMOVED
            risk = _score_risk(old_chunk or "")
        else:  # replace
            change_type = ChangeType.MODIFIED
            combined = (old_chunk or "") + (new_chunk or "")
            risk = _score_risk(combined)

        if tag == "equal":
            summary["unchanged"] += 1
        else:
            summary[change_type.value] += 1
            if risk == RiskLevel.HIGH:
                summary["high_risk"] += 1
            elif risk == RiskLevel.MEDIUM:
                summary["medium_risk"] += 1
            elif risk == RiskLevel.LOW:
                summary["low_risk"] += 1

        chunk_text = (new_chunk or old_chunk or "")
        chunk_id = hashlib.md5(f"{tag}{i1}{j1}{chunk_text[:50]}".encode()).hexdigest()[:8]

        kws = _extract_keywords_found(chunk_text, risk) if risk != RiskLevel.NONE else []

        chunks.append(DiffChunk(
            chunk_id=chunk_id,
            change_type=change_type,
            old_text=old_chunk,
            new_text=new_chunk,
            risk_level=risk,
            risk_keywords=kws,
            old_line_start=i1 + 1 if i1 < i2 else None,
            new_line_start=j1 + 1 if j1 < j2 else None,
        ))

    summary["total_chunks"] = len(chunks)

    return DiffResult(
        chunks=chunks,
        summary=summary,
        similarity_score=round(similarity, 4),
    )


def filter_diff(result: DiffResult, min_risk: RiskLevel = RiskLevel.NONE) -> DiffResult:
    """Return only chunks at or above specified risk level."""
    order = [RiskLevel.NONE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
    threshold = order.index(min_risk)
    filtered = [c for c in result.chunks if order.index(c.risk_level) >= threshold]
    return DiffResult(
        chunks=filtered,
        summary=result.summary,
        similarity_score=result.similarity_score,
    )