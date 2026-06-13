import logging
import hmac
import hashlib
import json
from typing import List, Dict, Any, Tuple
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.documents import Document as LCDoc
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.core.registry import get_agencies

logger = logging.getLogger(__name__)

# --- STEP 2: AGENT ROUTING INTENT PROMPT ---
_ROUTING_SYSTEM_PROMPT = """You are the orchestration routing layer of a policy comparison system.
Your job is to analyze the user's question and extract the core operational topic sections or keywords that need to be compared (e.g., "Copays", "Maternity Care", "Exclusions", "Limits").
Output your answer ONLY as a clean JSON list of strings representing the target section concepts. No explanations, no markdown code blocks.
Example input: "How did the outpatient surgery copay change?"
Example output: ["Outpatient Surgery", "Copay", "Fees"]"""

_ROUTING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _ROUTING_SYSTEM_PROMPT),
    ("human", "Analyze this question: '{question}'")
])

# --- STEP 4: STRICT DELTA PROMPTING PROMPT ---
_DELTA_SYSTEM_PROMPT = """You are an expert regulatory compliance auditor specialized in highly structured contracts and policies.
Your task is to analyze parallel document sections provided to you side-by-side and isolate the strict structural changes (deltas).

CRITICAL OPERATIONAL RULES:
1. Focus heavily on financial numbers, percentage shifts, added/removed exclusions, coverage thresholds, and liability boundaries.
2. Do not summarize unchanged text. If a section did not change structurally, omit it.
3. Use strict structural formatting. Cite findings line-by-line back to the parallel section headers.
4. If the fused context contains insufficient evidence to confirm a change, output "Insufficient context for precise delta determination" — NEVER hallucinate names or metrics."""

_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _DELTA_SYSTEM_PROMPT),
    ("human", """
Country: {country} | Industry: {industry} | Role: {role}
Applicable Agencies: {agencies}
Key Regulations: {key_regs}

=== STEP 3: SIDE-BY-SIDE FUSED CONTEXT ===
{fused_context}

User Question: {question}
Format the structural deltas output in: {language}
""")
])

class SafeRAGEngine:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(model=settings.EMBEDDING_MODEL, openai_api_key=settings.OPENAI_API_KEY)
        self.llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.0, max_tokens=settings.LLM_MAX_TOKENS, openai_api_key=settings.OPENAI_API_KEY)
        self.router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, response_format={"type": "json_object"}, openai_api_key=settings.OPENAI_API_KEY)

    def _pair_id(self, old_text: str, new_text: str) -> str:
        return hmac.new(settings.SECRET_KEY.encode(), f"{old_text[:5000]}{new_text[:5000]}".encode(), hashlib.sha256).hexdigest()[:32]

    def build_index_from_structural_chunks(self, old_chunks: List[Dict], new_chunks: List[Dict]) -> str:
        """Implements Strategy Step 1: Saves explicitly tagged structural entities into separate index directories."""
        # We concatenate the top chunk structures to create a stable signature key
        sig_base = "".join([c["text"][:500] for c in old_chunks[:2] + new_chunks[:2]])
        pair_id = hmac.new(settings.SECRET_KEY.encode(), sig_base.encode(), hashlib.sha256).hexdigest()[:32]
        
        lc_docs = []
        for chunk in old_chunks:
            lc_docs.append(LCDoc(page_content=chunk["text"], metadata=chunk["metadata"]))
        for chunk in new_chunks:
            lc_docs.append(LCDoc(page_content=chunk["text"], metadata=chunk["metadata"]))

        store = FAISS.from_documents(lc_docs, self.embeddings)
        store.save_local(str(settings.FAISS_INDEX_PATH / pair_id))
        return pair_id

    def _extract_routing_targets(self, question: str) -> List[str]:
        """Implements Strategy Step 2: The Agent step extracting targeting matrices."""
        try:
            chain = _ROUTING_PROMPT | self.router_llm
            response = chain.invoke({"question": question})
            parsed = json.loads(response.content)
            # Fetch extracted targets out of the structured key array fallback
            return parsed.get("targets", list(parsed.values())[0])
        except Exception as e:
            logger.error(f"Target routing parser failed: {e}. Falling back to token mapping extraction.")
            return [w for w in question.split() if len(w) > 4]

    def load_align_and_compare(self, pair_id: str, question: str, ctx: dict) -> dict:
        """
        Executes Steps 2, 3, and 4 sequentially:
        - Route query targeting metadata
        - Fuse contexts side-by-side
        - Output strict delta evaluations
        """
        index_path = settings.FAISS_INDEX_PATH / pair_id
        if not index_path.exists():
            return {"answer": "Vector structures not found. Please re-upload.", "sources": [], "tokens_used": 0}
        
        store = FAISS.load_local(str(index_path), self.embeddings, allow_dangerous_deserialization=True)
        
        # Step 2: Targeted Agent Routing Evaluation Pass
        routing_targets = self._extract_routing_targets(question)
        logger.info(f"Orchestration Agent targeted matching routing vectors to tokens: {routing_targets}")
        
        # Build query strings maximizing matching probability scores against metadata definitions
        routing_query = " ".join(routing_targets)
        
        # Over-retrieve chunks to guarantee we collect matching segments from both files
        raw_docs = store.similarity_search(routing_query, k=12)
        
        # Group segments by section headers to execute Side-by-Side Context Fusion (Step 3)
        old_sections: Dict[str, List[str]] = {}
        new_sections: Dict[str, List[str]] = {}
        
        for doc in raw_docs:
            lbl = doc.metadata.get("doc_label")
            sec = doc.metadata.get("section", "General Structure")
            if lbl == "OLD":
                old_sections.setdefault(sec, []).append(doc.page_content)
            elif lbl == "NEW":
                new_sections.setdefault(sec, []).append(doc.page_content)

        # Step 3: Structural Context Fusion Pipeline Pass
        # Find overlapping active sections targeted by our routing agent
        fused_blocks = []
        all_matched_sections = set(old_sections.keys()).union(set(new_sections.keys()))
        
        for section in all_matched_sections:
            old_body = "\n".join(old_sections.get(section, ["(Section text missing/not found in old document source)"]))
            new_body = "\n".join(new_sections.get(section, ["(Section text missing/not found in new document source)"]))
            
            fused_blocks.append(
                f"### PARALLEL STRUCTURE MATCH: {section}\n"
                f"--- CONTEXT A: OLD POLICY SECTION CONTENT ---\n{old_body}\n"
                f"--- CONTEXT B: NEW POLICY SECTION CONTENT ---\n{new_body}\n"
                f"==========================================================="
            )

        fused_context_str = "\n\n".join(fused_blocks)
        if not fused_context_str.strip():
            fused_context_str = "No overlapping or parallel structured categories could be dynamically isolated for this concept question query."

        # Step 4: Generation with Strict Delta Prompting
        agency_data = get_agencies(ctx["country"], ctx["industry"])
        chain = _ANALYSIS_PROMPT | self.llm
        
        response = chain.invoke({
            "context": fused_context_str,
            "fused_context": fused_context_str,
            "question": question,
            "country": ctx["country"].upper(),
            "industry": ctx["industry"].title(),
            "role": ctx["role"].upper(),
            "agencies": ", ".join(agency_data["agencies"]),
            "key_regs": ", ".join(agency_data["key_regs"]),
            "language": ctx.get("language", "en")
        })

        return {
            "answer": response.content,
            "sources": [{"label": doc.metadata.get("doc_label"), "excerpt": doc.page_content[:150]} for doc in raw_docs[:4]],
            "tokens_used": response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
        }