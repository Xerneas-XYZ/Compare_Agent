import streamlit as st 
import requests 
import tempfile 
import os 
from typing import Optional 
 
# ---------- Configuration ---------- 
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000") 
st.set_page_config(page_title="Policy Compare", layout="wide", initial_sidebar_state="expanded") 
 
# ---------- Helpers ---------- 
def get_token(username: str, password: str) -> Optional[str]: 
    try: 
        r = requests.post(f"{BACKEND_URL}/token", data={"username": username, "password": password}, timeout=30) 
        if r.status_code == 200: 
            return r.json().get("access_token") 
    except Exception: 
        return None 
    return None 
 
def upload_file(file_obj, token: str): 
    # streamlit file uploader returns a BytesIO-like object 
    files = {"file": (file_obj.name, file_obj.getvalue(), file_obj.type or "application/octet-stream")} 
    headers = {"Authorization": f"Bearer {token}"} 
    r = requests.post(f"{BACKEND_URL}/upload/", files=files, headers=headers, timeout=120) 
    r.raise_for_status() 
    return r.json() 
 
def compare_docs(a_id: int, b_id: int, token: str): 
    headers = {"Authorization": f"Bearer {token}"} 
    params = {"a_id": a_id, "b_id": b_id} 
    r = requests.post(f"{BACKEND_URL}/compare/", params=params, headers=headers, timeout=120) 
    r.raise_for_status() 
    return r.json() 
 
def fetch_audit(limit: int, token: str): 
    headers = {"Authorization": f"Bearer {token}"} 
    try: 
        r = requests.get(f"{BACKEND_URL}/audit/", params={"limit": limit}, headers=headers, timeout=30) 
        if r.status_code == 200: 
            return r.json() 
    except Exception: 
        return [] 
    return [] 
 
def fetch_documents(token: str): 
    headers = {"Authorization": f"Bearer {token}"} 
    try: 
        r = requests.get(f"{BACKEND_URL}/documents/", headers=headers, timeout=30) 
        if r.status_code == 200: 
            return r.json() 
    except Exception: 
        return [] 
    return [] 
 
# ---------- Sidebar: Auth & Settings ---------- 
st.sidebar.header("Demo Authentication") 
st.sidebar.markdown("Use demo users: **alice / alicepass**, **bob / bobpass**, **carol / carolpass**") 
username = st.sidebar.text_input("Username", value="alice", help="Demo username for RBAC") 
password = st.sidebar.text_input("Password", value="alicepass", type="password", help="Demo password") 
token = None 
if st.sidebar.button("Get Token", use_container_width=True): 
    token = get_token(username, password) 
    if token: 
        st.sidebar.success("Token acquired — stored in session only") 
        st.session_state["token"] = token 
    else: 
        st.sidebar.error("Failed to get token. Check backend and credentials.") 
else: 
    token = st.session_state.get("token") 
 
st.sidebar.markdown("---") 
st.sidebar.header("Accessibility") 
st.sidebar.checkbox("Large text mode", key="large_text") 
st.sidebar.checkbox("High contrast", key="high_contrast") 
 
# ---------- Main UI ---------- 
if st.session_state.get("large_text"): 
    st.markdown("<style>body { font-size: 18px; }</style>", unsafe_allow_html=True) 
if st.session_state.get("high_contrast"): 
    st.markdown("<style>body { background-color: #000; color: #fff; }</style>", unsafe_allow_html=True) 
 
st.title("Policy & Document Comparison Assistant") 
st.markdown("Upload a legacy policy and a modernized policy to compare text and semantic differences. Keyboard accessible and screen-reader friendly.") 
 
col1, col2 = st.columns([1, 1]) 
 
with col1: 
    st.subheader("Legacy policy (A)") 
    legacy_file = st.file_uploader("Upload legacy policy", type=["pdf", "docx", "txt", "csv"], key="legacy", help="Select the legacy policy document") 
    st.markdown("**PII will be masked on upload.**") 
 
with col2: 
    st.subheader("Modernized policy (B)") 
    modern_file = st.file_uploader("Upload modernized policy", type=["pdf", "docx", "txt", "csv"], key="modern", help="Select the modernized policy document") 
 
st.markdown("---") 
 
# Upload & Compare actions 
col_upload, col_actions = st.columns([1, 2]) 
with col_upload: 
    st.button("Clear token", on_click=lambda: st.session_state.pop("token", None)) 
with col_actions: 
    compare_btn = st.button("Upload & Compare", help="Uploads both files, masks PII, indexes, and runs comparison") 
 
# Results area 
results_expander = st.expander("Comparison results", expanded=True) 
with results_expander: 
    if compare_btn: 
        if not token: 
            st.error("You must obtain a token from the sidebar before uploading.") 
        elif not legacy_file or not modern_file: 
            st.error("Please upload both documents.") 
        else: 
            try: 
                with st.spinner("Uploading legacy document..."): 
                    r1 = upload_file(legacy_file, token) 
                with st.spinner("Uploading modern document..."): 
                    r2 = upload_file(modern_file, token) 
                a_id = r1["doc_id"] 
                b_id = r2["doc_id"] 
 
                st.success("Files uploaded and masked. PII summary shown below.") 
                st.subheader("PII Summary") 
                st.write("Legacy (A):", r1.get("pii_summary", {})) 
                st.write("Modern (B):", r2.get("pii_summary", {})) 
 
                with st.spinner("Running comparison..."): 
                    comp = compare_docs(a_id, b_id, token) 
 
                st.subheader("Unified Text Diff") 
                st.code(comp.get("diffs", ""), language="diff") 
 
                st.subheader("Semantic Summary") 
                sem = comp.get("semantic", {}) 
                st.write(sem.get("summary", sem)) 
 
                st.subheader("Top semantic matches (sample)") 
                matches = sem.get("matches", [])[:10] 
                for m in matches: 
                    st.markdown(f"**A chunk {m.get('a_index')}**") 
                    st.write(m.get("a_text")) 
                    neigh = m.get("neighbors", [])[:3] 
                    for n in neigh: 
                        st.markdown(f"- **B chunk {n.get('b_index')}** (distance {n.get('distance'):.4f})") 
                        st.write(n.get("b_text")) 
 
                st.success("Comparison complete. Audit entries recorded in backend.") 
            except requests.HTTPError as e: 
                st.error(f"Backend error: {e.response.text if e.response is not None else str(e)}") 
            except Exception as e: 
                st.error(f"Unexpected error: {str(e)}") 
 
# Audit and Documents panels 
st.markdown("---") 
st.subheader("Recent audit trail") 
if token: 
    try: 
        audits = fetch_audit(limit=25, token=token) 
        if audits: 
            for a in audits: 
                ts = a.get("timestamp", "") 
                user = a.get("user", "unknown") 
                action = a.get("action", "") 
                target = a.get("target", "") 
                details = a.get("details", {}) 
                st.markdown(f"**{ts}** — **{user}** — {action} — {target}") 
                st.write(details) 
        else: 
            st.info("No audit entries found or insufficient permissions to view audit.") 
    except Exception: 
        st.info("Unable to fetch audit entries.") 
else: 
    st.info("Get a token to view audit entries.") 
 
st.markdown("---") 
st.subheader("Indexed documents") 
if token: 
    docs = fetch_documents(token) 
    if docs: 
        for d in docs: 
            st.markdown(f"**ID {d.get('id')}** — {d.get('filename')} — uploaded by {d.get('metadata', {}).get('uploader')}") 
            st.write("PII summary:", d.get("metadata", {}).get("pii_summary", {})) 
    else: 
        st.info("No documents indexed yet or insufficient permissions.") 
else: 
    st.info("Get a token to view indexed documents.") 
 
# Footer accessibility note 
st.markdown( 
    """ 
    <hr/> 
    <small>Accessibility: keyboard focus order follows the visual layout. Screen readers will read PII summary and audit entries as plain text. For production, integrate ARIA attributes and test with NVDA/JAWS/VoiceOver.</small> 
    """, 
    unsafe_allow_html=True, 
) 