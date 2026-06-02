"""
RAG Pipeline
Embeds document chunks into FAISS, retrieves relevant context,
then calls LLM for regulatory impact analysis.

Token optimization:
  - Small embedding model (text-embedding-3-small)
  - Chunk size 800 tokens with 80 overlap
  - Top-k=4 retrieval
  - System prompt is cached (static)
  - Analysis capped at max_tokens=1024 per query
"""
import logging
import hashlib
import json
from typing import List, Optional
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.schema import Document as LCDoc
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough

from app.core.config import settings
from app.core.compliance_registry import get_agencies

logger = logging.getLogger(__name__)


# Static system prompt — keeps token cost down on every call
_SYSTEM_PROMPT = """You are a regulatory compliance analyst. 
Analyze the retrieved document excerpts and answer ONLY based on the provided context.
If the context does not contain enough information, say "Insufficient context" — do not hallucinate.
Be concise. Use bullet points. Cite which document (OLD/NEW) each finding comes from."""

_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    ("human", """
Country: {country} | Industry: {industry} | Role: {role}
Relevant Agencies: {agencies}
Key Regulations: {key_regs}

Context from documents:
{context}

Question: {question}

Respond in: {language}
""")
])


class RAGPipeline:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=1024,   # capped for cost control
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " "],
        )
        self._vector_stores: dict = {}   # doc_id → FAISS store

    def _doc_id(self, text: str) -> str:
        return hashlib.md5(text[:500].encode()).hexdigest()[:12]

    def index_document(self, text: str, doc_label: str) -> str:
        """Chunk, embed, and store a document. Returns doc_id."""
        doc_id = self._doc_id(text)
        chunks = self.splitter.split_text(text)
        lc_docs = [
            LCDoc(page_content=chunk, metadata={"label": doc_label, "chunk_idx": i})
            for i, chunk in enumerate(chunks)
        ]
        store = FAISS.from_documents(lc_docs, self.embeddings)
        self._vector_stores[doc_id] = store
        logger.info(f"Indexed {len(chunks)} chunks for doc '{doc_label}' (id={doc_id})")
        return doc_id

    def index_pair(self, old_text: str, new_text: str) -> str:
        """Index both documents together into a single combined FAISS store."""
        pair_id = self._doc_id(old_text + new_text)
        all_docs = []
        for text, label in [(old_text, "OLD"), (new_text, "NEW")]:
            chunks = self.splitter.split_text(text)
            all_docs.extend([
                LCDoc(page_content=c, metadata={"label": label, "chunk_idx": i})
                for i, c in enumerate(chunks)
            ])
        store = FAISS.from_documents(all_docs, self.embeddings)
        self._vector_stores[pair_id] = store
        return pair_id

    def analyze(
        self,
        pair_id: str,
        question: str,
        country: str,
        industry: str,
        role: str,
        language: str = "en",
        top_k: int = 4,
    ) -> dict:
        """
        Retrieve relevant chunks and run LLM analysis.
        Returns {"answer": str, "sources": list, "tokens_used": int}
        """
        store = self._vector_stores.get(pair_id)
        if not store:
            return {"answer": "Documents not indexed. Please re-upload.", "sources": [], "tokens_used": 0}

        agency_data = get_agencies(country, industry)
        retriever = store.as_retriever(search_kwargs={"k": top_k})

        # Build retrieval chain
        def format_docs(docs: List[LCDoc]) -> str:
            return "\n---\n".join(
                f"[{d.metadata['label']} chunk {d.metadata['chunk_idx']}]\n{d.page_content}"
                for d in docs
            )

        chain = (
            {
                "context": retriever | format_docs,
                "question": RunnablePassthrough(),
                "country": lambda _: country.upper(),
                "industry": lambda _: industry.title(),
                "role": lambda _: role.replace("_", " ").title(),
                "agencies": lambda _: ", ".join(agency_data["agencies"]),
                "key_regs": lambda _: ", ".join(agency_data["key_regs"]),
                "language": lambda _: language,
            }
            | _ANALYSIS_PROMPT
            | self.llm
        )

        response = chain.invoke(question)
        sources = retriever.get_relevant_documents(question)

        return {
            "answer": response.content,
            "sources": [
                {"label": d.metadata["label"], "excerpt": d.page_content[:200]}
                for d in sources
            ],
            "tokens_used": response.response_metadata.get("token_usage", {}).get("total_tokens", 0),
        }

    def generate_impact_summary(
        self,
        pair_id: str,
        diff_summary: dict,
        country: str,
        industry: str,
        role: str,
        language: str = "en",
    ) -> dict:
        """Pre-built regulatory impact analysis query."""
        question = (
            f"Compare OLD vs NEW document. "
            f"There are {diff_summary.get('high_risk', 0)} high-risk, "
            f"{diff_summary.get('medium_risk', 0)} medium-risk changes. "
            f"What are the key regulatory compliance implications for {industry} in {country}? "
            f"List the top 5 action items for a {role.replace('_', ' ')}."
        )
        return self.analyze(pair_id, question, country, industry, role, language)


# Singleton instance
_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline