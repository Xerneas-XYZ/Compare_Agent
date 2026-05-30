# backend/compare.py 
from difflib import unified_diff 
from typing import List, Dict 
import os, json 
from openai import OpenAI 
import numpy as np 
import faiss 
from backend.ingestion import mask_pii 
 
OPENAI_KEY = os.getenv("OPENAI_API_KEY", None) 
 
# Simple text diff 
def text_diff(a: str, b: str) -> str: 
    a_lines = a.splitlines(keepends=True) 
    b_lines = b.splitlines(keepends=True) 
    diff = unified_diff(a_lines, b_lines, fromfile="legacy", tofile="modern", lineterm="") 
    return "".join(diff) 
 
# Embedding + FAISS semantic compare (demo) 
def embed_texts(texts: List[str]) -> List[List[float]]: 
    # Use OpenAI embeddings if key present; otherwise fallback to simple hashing vector (demo) 
    if OPENAI_KEY: 
        client = OpenAI(api_key=OPENAI_KEY) 
        resp = client.embeddings.create(model="text-embedding-3-small", input=texts) 
        return [r.embedding for r in resp.data] 
    # fallback: deterministic pseudo-embedding 
    return [[float((hash(t) % 1000) / 1000.0) for _ in range(1536)] for t in texts] 
 
def semantic_compare(a: str, b: str, top_k: int = 5) -> Dict: 
    # Chunking naive split by paragraphs 
    a_chunks = [c.strip() for c in a.split("\n\n") if c.strip()] 
    b_chunks = [c.strip() for c in b.split("\n\n") if c.strip()] 
    texts = a_chunks + b_chunks 
    if not texts: 
        return {"summary": "No content"} 
    embs = embed_texts(texts) 
    dim = len(embs[0]) 
    index = faiss.IndexFlatL2(dim) 
    import numpy as np 
    index.add(np.array(embs).astype('float32')) 
    # For each a_chunk, find nearest b_chunk 
    results = [] 
    for i, ac in enumerate(a_chunks): 
        q = np.array([embs[i]]).astype('float32') 
        D, I = index.search(q, top_k) 
        # filter to b indices 
        neighbors = [] 
        for dist, idx in zip(D[0], I[0]): 
            if idx >= len(a_chunks): 
                neighbors.append({"b_index": idx - len(a_chunks), "distance": float(dist), "b_text": b_chunks[idx - len(a_chunks)]}) 
        results.append({"a_index": i, "a_text": ac, "neighbors": neighbors}) 
    # Simple summary via LLM if available 
    summary = "Semantic comparison produced neighbor matches." 
    if OPENAI_KEY: 
        client = OpenAI(api_key=OPENAI_KEY) 
        prompt = "Summarize regulatory differences between two documents based on these matches:\n\n" + json.dumps(results[:10]) 
        resp = client.responses.create(model="gpt-4o-mini", input=prompt, max_tokens=400) 
        summary = resp.output_text 
    return {"matches": results, "summary": summary} 