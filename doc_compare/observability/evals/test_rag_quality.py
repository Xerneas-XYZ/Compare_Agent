"""
DeepEval Test Suite
Tests:
  - Answer relevancy
  - Faithfulness (no hallucination)
  - Contextual recall
  - PII leakage check (custom metric)
Run: pytest observability/evals/test_rag_quality.py -v
"""
import pytest
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRecallMetric,
)
from deepeval.test_case import LLMTestCase

# ── Fixtures — sample banking regulation test cases ───────────────────────────
SAMPLE_CASES = [
    {
        "input": "What new capital requirements are introduced in the updated policy?",
        "actual_output": "The updated policy increases Tier 1 capital ratio from 6% to 8% effective Q1 2025.",
        "expected_output": "Tier 1 capital ratio increases to 8%",
        "retrieval_context": [
            "Section 4.2: Minimum Tier 1 capital ratio raised from 6% to 8% effective January 2025.",
            "Section 4.3: Total capital ratio remains at 10.5%.",
        ],
    },
    {
        "input": "Are there new reporting deadlines for insurance claims?",
        "actual_output": "Claims must now be reported within 48 hours instead of 72 hours.",
        "expected_output": "Reporting window reduced to 48 hours",
        "retrieval_context": [
            "Amendment 3.1: Claims reporting deadline amended from 72 hours to 48 hours.",
        ],
    },
]


@pytest.mark.parametrize("case", SAMPLE_CASES)
def test_answer_relevancy(case):
    metric = AnswerRelevancyMetric(threshold=0.7, model="gpt-4o-mini")
    test_case = LLMTestCase(
        input=case["input"],
        actual_output=case["actual_output"],
        retrieval_context=case["retrieval_context"],
    )
    assert_test(test_case, [metric])


@pytest.mark.parametrize("case", SAMPLE_CASES)
def test_faithfulness(case):
    """Ensures model doesn't hallucinate beyond retrieved context."""
    metric = FaithfulnessMetric(threshold=0.8, model="gpt-4o-mini")
    test_case = LLMTestCase(
        input=case["input"],
        actual_output=case["actual_output"],
        retrieval_context=case["retrieval_context"],
    )
    assert_test(test_case, [metric])


@pytest.mark.parametrize("case", SAMPLE_CASES)
def test_contextual_recall(case):
    metric = ContextualRecallMetric(threshold=0.7, model="gpt-4o-mini")
    test_case = LLMTestCase(
        input=case["input"],
        actual_output=case["actual_output"],
        expected_output=case["expected_output"],
        retrieval_context=case["retrieval_context"],
    )
    assert_test(test_case, [metric])


# ── Custom PII leakage metric ─────────────────────────────────────────────────
import re

_PII_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",       # SSN
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",  # email
    r"\b(?:\d{4}[-\s]?){3}\d{4}\b", # credit card
]
_PII_RE = re.compile("|".join(_PII_PATTERNS))


@pytest.mark.parametrize("case", SAMPLE_CASES)
def test_no_pii_in_output(case):
    """Custom check: LLM output must not contain PII patterns."""
    output = case["actual_output"]
    matches = _PII_RE.findall(output)
    assert not matches, f"PII found in LLM output: {matches}"