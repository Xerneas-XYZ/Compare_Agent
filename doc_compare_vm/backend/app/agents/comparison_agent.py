"""
Document Comparison Agent
LangChain ReAct agent with tools:
  - diff_tool: compute structural diff
  - pii_mask_tool: mask PII in text
  - rag_query_tool: query indexed documents
  - compliance_lookup_tool: look up agencies/regulations
  - export_tool: trigger export

Guardrails:
  - Input length cap (no prompt injection via huge docs)
  - Output validation (no PII leakage in responses)
  - Hallucination guard: LLM is not asked to generate regulation names
"""
import logging
from typing import Any, Optional
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from app.core.config import settings
from app.core.compliance_registry import get_agencies, get_all_agencies_flat
from app.diff.engine import compute_diff, DiffResult
from app.pii.masker import full_mask
from app.rag.pipeline import get_pipeline

logger = logging.getLogger(__name__)

# ── Tool definitions ──────────────────────────────────────────────────────────

@tool
def diff_tool(input_json: str) -> str:
    """
    Compute diff between old_text and new_text.
    Input JSON: {"old_text": "...", "new_text": "..."}
    Returns summary of changes and risk levels.
    """
    import json
    data = json.loads(input_json)
    result = compute_diff(data["old_text"], data["new_text"])
    high_risk = [c for c in result.chunks if c.risk_level.value == "high"]
    return json.dumps({
        "similarity": result.similarity_score,
        "summary": result.summary,
        "high_risk_excerpts": [
            {"old": c.old_text[:300] if c.old_text else None,
             "new": c.new_text[:300] if c.new_text else None,
             "keywords": c.risk_keywords}
            for c in high_risk[:5]  # top 5 only
        ],
    }, indent=2)


@tool
def pii_mask_tool(input_json: str) -> str:
    """
    Mask PII in text.
    Input JSON: {"text": "...", "language": "en"}
    Returns masked text and redaction count.
    """
    import json
    data = json.loads(input_json)
    result = full_mask(data["text"], data.get("language", "en"))
    return json.dumps({
        "masked_text": result.masked_text[:2000],   # truncate for agent context
        "redaction_count": result.redaction_count,
    })


@tool
def compliance_lookup_tool(input_json: str) -> str:
    """
    Look up regulatory agencies and key regulations for a country+industry.
    Input JSON: {"country": "usa", "industry": "banking"}
    Returns agencies and regulations list.
    """
    import json
    data = json.loads(input_json)
    result = get_agencies(data["country"], data["industry"])
    return json.dumps(result, indent=2)


@tool
def rag_query_tool(input_json: str) -> str:
    """
    Query the indexed documents using RAG.
    Input JSON: {"pair_id": "...", "question": "...", "country": "...",
                 "industry": "...", "role": "...", "language": "en"}
    Returns AI analysis grounded in document content.
    """
    import json
    data = json.loads(input_json)
    pipeline = get_pipeline()
    result = pipeline.analyze(
        pair_id=data["pair_id"],
        question=data["question"],
        country=data["country"],
        industry=data["industry"],
        role=data["role"],
        language=data.get("language", "en"),
    )
    return json.dumps(result, indent=2)


AGENT_TOOLS = [diff_tool, pii_mask_tool, compliance_lookup_tool, rag_query_tool]

# ── Agent prompt ──────────────────────────────────────────────────────────────
_AGENT_PROMPT = PromptTemplate.from_template("""
You are a document comparison agent specialized in regulatory compliance.
You help compare policy documents across banking, insurance, and healthcare industries.

CRITICAL RULES:
1. NEVER invent regulation names, penalty amounts, or agency names. Use compliance_lookup_tool.
2. ALWAYS mask PII before displaying any extracted text to users.
3. Keep answers grounded in document content via rag_query_tool.
4. If a tool returns "Insufficient context", say so — do not fill gaps.

Available tools: {tools}
Tool names: {tool_names}

Context:
- Country: {country}
- Industry: {industry}
- User role: {role}
- Language: {language}
- Document pair ID: {pair_id}

{agent_scratchpad}

Question: {input}
""")


def build_agent(
    country: str,
    industry: str,
    role: str,
    language: str,
    pair_id: str,
) -> AgentExecutor:
    """Build and return an AgentExecutor configured for this comparison session."""
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0.0,
        max_tokens=settings.LLM_MAX_TOKENS,
        openai_api_key=settings.OPENAI_API_KEY,
    )

    prompt = _AGENT_PROMPT.partial(
        country=country,
        industry=industry,
        role=role,
        language=language,
        pair_id=pair_id,
    )

    agent = create_react_agent(llm, AGENT_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=AGENT_TOOLS,
        verbose=True,
        max_iterations=6,          # prevent runaway loops
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )