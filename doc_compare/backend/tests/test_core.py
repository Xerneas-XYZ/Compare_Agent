"""
Backend unit tests — no LLM calls, no external services.
Covers: diff engine, PII masker, parser, compliance registry.
"""
import pytest
from app.diff.engine import compute_diff, ChangeType, RiskLevel
from app.pii.masker import mask_pii
from app.core.compliance_registry import get_agencies, COMPLIANCE_REGISTRY


# ── Diff engine ───────────────────────────────────────────────────────────────
class TestDiffEngine:
    def test_identical_documents(self):
        text = "The policy requires annual review of capital ratios."
        result = compute_diff(text, text)
        assert result.similarity_score == 1.0
        assert result.summary["added"] == 0
        assert result.summary["removed"] == 0

    def test_added_content_detected(self):
        old = "Section 1: Capital requirements apply."
        new = "Section 1: Capital requirements apply.\nSection 2: AML compliance is mandatory."
        result = compute_diff(old, new)
        added = [c for c in result.chunks if c.change_type == ChangeType.ADDED]
        assert len(added) > 0

    def test_high_risk_keyword_detected(self):
        old = "Reporting is optional."
        new = "Reporting is mandatory. Penalty for non-compliance: $50,000 fine."
        result = compute_diff(old, new)
        high_risk = [c for c in result.chunks if c.risk_level == RiskLevel.HIGH]
        assert len(high_risk) > 0, "Should detect 'mandatory' and 'penalty' as high-risk"

    def test_similarity_score_range(self):
        result = compute_diff("abc def ghi", "abc def xyz")
        assert 0.0 <= result.similarity_score <= 1.0

    def test_empty_documents(self):
        result = compute_diff("", "")
        assert result.similarity_score == 1.0


# ── PII masker ────────────────────────────────────────────────────────────────
class TestPIIMasker:
    def test_email_masked(self):
        result = mask_pii("Contact john.doe@example.com for details.")
        assert "john.doe@example.com" not in result.masked_text
        assert "[REDACTED]" in result.masked_text
        assert result.redaction_count == 1

    def test_ssn_masked(self):
        result = mask_pii("SSN: 123-45-6789")
        assert "123-45-6789" not in result.masked_text

    def test_credit_card_masked(self):
        result = mask_pii("Card: 4111 1111 1111 1111")
        assert "4111 1111 1111 1111" not in result.masked_text

    def test_aadhar_masked(self):
        result = mask_pii("Aadhaar: 1234 5678 9012")
        assert "1234 5678 9012" not in result.masked_text

    def test_no_pii_unchanged(self):
        text = "The capital requirement is 8% for Tier 1 assets."
        result = mask_pii(text)
        assert result.redaction_count == 0
        assert result.masked_text == text

    def test_multiple_pii_types(self):
        text = "Email: user@bank.com, SSN: 987-65-4321"
        result = mask_pii(text)
        assert result.redaction_count >= 2


# ── Compliance registry ───────────────────────────────────────────────────────
class TestComplianceRegistry:
    def test_all_countries_and_industries_covered(self):
        countries = ["usa", "uk", "india", "china", "russia", "germany"]
        industries = ["banking", "insurance", "healthcare"]
        for country in countries:
            for industry in industries:
                data = get_agencies(country, industry)
                assert len(data["agencies"]) > 0, f"No agencies for {country}/{industry}"
                assert len(data["key_regs"]) > 0, f"No regulations for {country}/{industry}"

    def test_unknown_country_returns_empty(self):
        data = get_agencies("mars", "banking")
        assert data["agencies"] == []

    def test_usa_banking_contains_fed(self):
        data = get_agencies("usa", "banking")
        assert any("Federal Reserve" in a for a in data["agencies"])

    def test_india_healthcare_contains_dpdp(self):
        data = get_agencies("india", "healthcare")
        assert any("DPDP" in r for r in data["key_regs"])