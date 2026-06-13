import sys
from pathlib import Path
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path: sys.path.insert(0, str(_HERE))

import streamlit as st, json
from utils.api_client import APIClient
from components.diff_viewer import render_diff_viewer
from components.impact_panel import render_impact_panel
from components.sidebar import render_sidebar
from components.upload_panel import render_upload_panel

st.set_page_config(page_title="DocCompare Agent", layout="wide")

# (Retain all your custom CSS variables here inside a standard st.markdown wrap)
st.markdown("<style>/* CSS injected cleanly */</style><div id='main-content'></div>", unsafe_allow_html=True)

if "old_doc_id" not in st.session_state:
    st.session_state.update({"old_doc_id": None, "new_doc_id": None, "comparison_result": None, "session_id": None, "chat_history": []})

config = render_sidebar()
client = APIClient(base_url=config["api_url"])

st.title("📋 DocCompare")
st.caption(f"{config['industry'].title()} · {config['country'].upper()} · {config['role'].title()}")

render_upload_panel(client, config)

if st.session_state.old_doc_id and st.session_state.new_doc_id:
    if st.button("🔍 Run Comparison", type="primary", use_container_width=True):
        with st.spinner("Extracting structural metadata, aligning sections, and running RAG..."):
            res = client.compare(st.session_state.old_doc_id, st.session_state.new_doc_id, config["country"], config["industry"], config["role"], config["language"])
            if res:
                st.session_state.comparison_result = res; st.session_state.session_id = res.get("session_id")
                st.success("✅ Extraction and Context Fusion Complete.")
            else: st.error("❌ Comparison failed. Check API connectivity.")

if st.session_state.comparison_result:
    res = st.session_state.comparison_result
    t1, t2, t3 = st.tabs(["📊 Diff Viewer", "⚖️ Regulatory Impact", "💬 Ask Questions"])
    with t1: render_diff_viewer(res, config["risk_filter"])
    with t2: render_impact_panel(res)
    with t3:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        if q := st.chat_input("Ask about regulatory changes..."):
            st.session_state.chat_history.append({"role": "user", "content": q})
            with st.chat_message("user"): st.markdown(q)
            with st.chat_message("assistant"):
                with st.spinner("Searching..."):
                    ans = client.query(st.session_state.session_id, q, config["language"])
                    if ans:
                        st.markdown(ans["answer"])
                        st.session_state.chat_history.append({"role": "assistant", "content": ans["answer"]})