import difflib
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"

class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

_RISK_KEYWORDS = {
    RiskLevel.HIGH: ["mandatory", "prohibited", "penalty", "fine", "sanction", "immediate", "terminate", "revoke", "suspended", "violation", "breach", "criminal", "imprisonment", "gdpr", "hipaa", "pci", "aml", "kyc", "fatf", "solvency"],
    RiskLevel.MEDIUM: ["required", "must", "shall", "deadline", "compliance", "reporting", "disclosure", "audit", "review", "approval", "authorization", "notification", "submit"],
    RiskLevel.LOW: ["recommended", "should", "may", "guidance", "best practice", "encouraged", "optional"]
}

@dataclass
class DiffChunk:
    chunk_id: str
    change_type: ChangeType
    old_text: Optional[str]
    new_text: Optional[str]
    risk_level: RiskLevel
    risk_keywords: List[str] = field(default_factory=list)

@dataclass
class DiffResult:
    chunks: List[DiffChunk]
    summary: dict
    similarity_score: float

def compute_diff(old_text: str, new_text: str) -> DiffResult:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    
    chunks: List[DiffChunk] = []
    summary = {"total_chunks": 0, "added": 0, "removed": 0, "modified": 0, "unchanged": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0}

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_chunk = "".join(old_lines[i1:i2]) if i1 < i2 else ""
        new_chunk = "".join(new_lines[j1:j2]) if j1 < j2 else ""
        combined = f"{old_chunk}\n{new_chunk}".lower()

        if tag == "equal":
            change_type = ChangeType.UNCHANGED
            risk = RiskLevel.NONE
        else:
            change_type = ChangeType.ADDED if tag == "insert" else (ChangeType.REMOVED if tag == "delete" else ChangeType.MODIFIED)
            risk = RiskLevel.NONE
            for level in [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]:
                if any(kw in combined for kw in _RISK_KEYWORDS[level]):
                    risk = level
                    break
        
        summary[change_type.value] += 1
        if risk != RiskLevel.NONE:
            summary[f"{risk.value}_risk"] += 1

        kws = [kw for kw in _RISK_KEYWORDS[risk] if kw in combined] if risk != RiskLevel.NONE else []
        chunk_id = hashlib.md5(f"{tag}:{i1}:{j1}".encode()).hexdigest()[:8]
        
        chunks.append(DiffChunk(
            chunk_id=chunk_id, change_type=change_type,
            old_text=old_chunk if old_chunk else None,
            new_text=new_chunk if new_chunk else None,
            risk_level=risk, risk_keywords=kws
        ))

    summary["total_chunks"] = len(chunks)
    return DiffResult(chunks=chunks, summary=summary, similarity_score=round(matcher.ratio(), 4))