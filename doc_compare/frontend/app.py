"""
Document Comparison Agent — Streamlit UI
WCAG 2.1 AA compliant, keyboard navigable, screen-reader friendly.
"""
import sys
from pathlib import Path

# Ensure the frontend directory is on sys.path regardless of where
# `streamlit run` is invoked from (project root, parent dir, etc.)
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import streamlit as st
import json

from utils.api_client import APIClient
from utils.constants import COUNTRIES, INDUSTRIES, ROLES, LANGUAGES
from components.diff_viewer import render_diff_viewer
from components.impact_panel import render_impact_panel
from components.sidebar import render_sidebar
from components.upload_panel import render_upload_panel

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DocCompare — Regulatory Document Comparison",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Report a bug": "https://github.com/your-org/doc-compare-agent/issues",
        "About": "Document Comparison Agent v1.0 — Regulatory Compliance Platform",
    },
)

# ── Global accessibility + design CSS ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Fraunces:opsz,wght@9..144,300;9..144,600&display=swap');

/* ── Design tokens ── */
:root {
  --clr-bg:        #0f1117;
  --clr-surface:   #1a1d27;
  --clr-border:    #2e3245;
  --clr-text:      #e8eaf0;
  --clr-muted:     #8b90a8;
  --clr-accent:    #4f9cf9;
  --clr-high:      #ff6b6b;
  --clr-high-bg:   rgba(255,107,107,0.12);
  --clr-medium:    #ffa94d;
  --clr-medium-bg: rgba(255,169,77,0.10);
  --clr-low:       #69db7c;
  --clr-low-bg:    rgba(105,219,124,0.10);
  --clr-added:     rgba(105,219,124,0.08);
  --clr-removed:   rgba(255,107,107,0.08);
  --clr-modified:  rgba(255,169,77,0.08);
  --radius:        8px;
  --font-ui:       'Fraunces', Georgia, serif;
  --font-mono:     'DM Mono', 'Fira Code', monospace;
  --focus-ring:    0 0 0 3px rgba(79,156,249,0.5);
  --transition:    0.18s ease;
}

/* ══════════════════════════════════════════════════════
   WHITESPACE KILL — Streamlit injects huge default gaps
   ══════════════════════════════════════════════════════ */

/* Main content area: cut the 6rem top padding Streamlit adds */
.main .block-container {
  padding-top: 1rem !important;
  padding-bottom: 1rem !important;
  max-width: 100% !important;
}

/* Kill the 1rem bottom margin on every stMarkdown block element */
.stMarkdown, .stMarkdown p, div[data-testid="stMarkdownContainer"] {
  margin-bottom: 0 !important;
}
/* But keep a little breathing room between actual paragraph text */
div[data-testid="stMarkdownContainer"] > p + p { margin-top: 0.4rem !important; }

/* Streamlit metric cards: tighten vertical padding */
div[data-testid="metric-container"] { padding: 0.4rem 0 !important; }

/* stCaption has huge top margin by default */
.stCaption, div[data-testid="stCaptionContainer"] {
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  line-height: 1.4 !important;
}

/* st.divider adds 1.5rem top + bottom — halve it */
hr[data-testid="stDivider"] { margin: 0.5rem 0 !important; }

/* Selectbox + text_input: cut their vertical gaps */
div[data-testid="stSelectbox"], div[data-testid="stTextInput"] {
  margin-bottom: 0.35rem !important;
}
div[data-testid="stSelectbox"] > label,
div[data-testid="stTextInput"]  > label {
  margin-bottom: 1px !important;
  padding-bottom: 0 !important;
}

/* Buttons: shrink the wrapper padding */
div[data-testid="stButton"] { margin-bottom: 0 !important; }

/* Tab bar: no extra vertical padding */
div[data-baseweb="tab-list"] { padding: 0 !important; }
div[data-baseweb="tab-panel"] { padding-top: 0.75rem !important; }

/* Expander: tighter header */
div[data-testid="stExpander"] details summary {
  padding: 6px 8px !important;
}
div[data-testid="stExpander"] details > div {
  padding: 6px 8px 8px !important;
}

/* Column gap: Streamlit defaults to 1rem, tighten to 0.75rem */
div[data-testid="stHorizontalBlock"] { gap: 0.75rem !important; }

/* File uploader: cut its enormous top padding */
div[data-testid="stFileUploader"] { margin-bottom: 0.25rem !important; }
div[data-testid="stFileUploader"] > section { padding: 0.5rem !important; }

/* Sidebar: kill the huge padding-top */
section[data-testid="stSidebar"] > div:first-child {
  padding-top: 0.75rem !important;
}
section[data-testid="stSidebar"] .block-container {
  padding-top: 0 !important;
  padding-bottom: 0.5rem !important;
}
/* Sidebar widget gaps */
section[data-testid="stSidebar"] div[data-testid="stSelectbox"],
section[data-testid="stSidebar"] div[data-testid="stTextInput"] {
  margin-bottom: 0.2rem !important;
}
/* Sidebar section headings injected via st.markdown — strip their default p margin */
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] h3,
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] h2 {
  margin-top: 0.6rem !important;
  margin-bottom: 0.1rem !important;
}

/* ── Skip-to-content ── */
.skip-link {
  position: fixed; top: -100%; left: 0; z-index: 9999;
  background: var(--clr-accent); color: #fff;
  padding: 10px 18px; font-size: 1rem; font-weight: 600;
  border-radius: 0 0 var(--radius) 0;
  text-decoration: none; transition: top 0.2s;
}
.skip-link:focus { top: 0; }

/* ── Focus rings ── */
*:focus-visible {
  outline: none !important;
  box-shadow: var(--focus-ring) !important;
  border-radius: 4px;
}
button:focus-visible, [role="button"]:focus-visible,
a:focus-visible, select:focus-visible,
input:focus-visible, textarea:focus-visible {
  box-shadow: var(--focus-ring) !important;
}

/* ── Risk badges ── */
.risk-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 20px;
  font-size: 0.75rem; font-weight: 600; letter-spacing: 0.04em;
  font-family: var(--font-mono); white-space: nowrap;
}
.risk-high   { background: var(--clr-high-bg);    color: var(--clr-high);   border: 1px solid rgba(255,107,107,0.3); }
.risk-medium { background: var(--clr-medium-bg);  color: var(--clr-medium); border: 1px solid rgba(255,169,77,0.3); }
.risk-low    { background: var(--clr-low-bg);     color: var(--clr-low);    border: 1px solid rgba(105,219,124,0.3); }
.risk-none   { background: rgba(139,144,168,0.1); color: var(--clr-muted);  border: 1px solid rgba(139,144,168,0.2); }
.risk-high::before   { content: "▲"; }
.risk-medium::before { content: "◆"; }
.risk-low::before    { content: "●"; }
.risk-none::before   { content: "○"; }

/* ── Change labels ── */
.change-added    { color: var(--clr-low);    font-family: var(--font-mono); }
.change-removed  { color: var(--clr-high);   font-family: var(--font-mono); }
.change-modified { color: var(--clr-medium); font-family: var(--font-mono); }

/* ── Diff table ── */
.diff-table {
  width: 100%; border-collapse: collapse;
  font-size: 0.92rem; font-family: var(--font-mono);
  border: 1px solid var(--clr-border); border-radius: var(--radius);
  overflow: hidden;
}
.diff-table caption {
  caption-side: top; text-align: left; padding: 6px 12px;
  font-size: 0.82rem; color: var(--clr-muted); font-family: var(--font-ui);
}
.diff-table thead th {
  padding: 8px 12px; text-align: left;
  font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  background: var(--clr-surface); color: var(--clr-muted);
  border-bottom: 1px solid var(--clr-border);
}
.diff-table thead th:nth-child(3) { color: #a8c5f0; }
.diff-table thead th:nth-child(4) { color: #a8d5b0; }
.diff-table tbody tr { border-bottom: 1px solid var(--clr-border); }
.diff-table tbody tr:focus-within { box-shadow: inset 0 0 0 2px var(--clr-accent); }
.diff-table tbody tr:last-child { border-bottom: none; }
.diff-table td { padding: 8px 12px; vertical-align: top; line-height: 1.5; }
.diff-table td pre {
  margin: 0; white-space: pre-wrap; word-break: break-word;
  font-family: var(--font-mono); font-size: inherit; color: var(--clr-text);
}
.diff-table .kw-tag {
  display: inline-block; margin: 2px;
  padding: 1px 5px; border-radius: 3px;
  background: rgba(79,156,249,0.15); color: var(--clr-accent);
  font-size: 0.72rem; font-family: var(--font-mono);
}

/* ── Status banners ── */
.status-banner {
  padding: 8px 12px; border-radius: var(--radius);
  font-size: 0.88rem; margin-bottom: 6px;
  display: flex; align-items: center; gap: 8px;
}
.status-success { background: var(--clr-low-bg);    color: var(--clr-low);    border: 1px solid rgba(105,219,124,0.3); }
.status-warning { background: var(--clr-medium-bg); color: var(--clr-medium); border: 1px solid rgba(255,169,77,0.3); }
.status-error   { background: var(--clr-high-bg);   color: var(--clr-high);   border: 1px solid rgba(255,107,107,0.3); }
.status-info    { background: rgba(79,156,249,0.1); color: var(--clr-accent); border: 1px solid rgba(79,156,249,0.25); }

/* ── Progress steps: compact single line ── */
.steps { display: flex; gap: 0; margin: 0 0 8px 0; }
.step {
  flex: 1; padding: 6px 10px; text-align: center;
  font-size: 0.78rem; font-family: var(--font-ui);
  background: var(--clr-surface); border-bottom: 2px solid var(--clr-border);
  color: var(--clr-muted);
}
.step.active  { border-bottom-color: var(--clr-accent); color: var(--clr-text); font-weight: 600; }
.step.done    { border-bottom-color: var(--clr-low);    color: var(--clr-low); }
.step .step-num { font-size: 0.65rem; opacity: 0.5; display: inline; margin-right: 4px; }

/* ── High-contrast mode ── */
@media (forced-colors: active) {
  .risk-badge, .diff-table td, .status-banner { border: 2px solid ButtonText; }
  .risk-high::before, .risk-medium::before, .risk-low::before { forced-color-adjust: none; }
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition: none !important; animation: none !important; }
}

/* ── Streamlit component overrides ── */
.stTabs [data-baseweb="tab"] { font-family: var(--font-ui); font-size: 0.9rem; padding: 8px 14px !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { font-weight: 600; }
.stButton > button { font-family: var(--font-ui); }
.stButton > button:focus-visible { box-shadow: var(--focus-ring) !important; }
div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
div[data-testid="stMetricLabel"] { font-size: 0.78rem !important; }
</style>

<!-- Skip link must be first in DOM for keyboard users -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<!-- ARIA live region: announces async state changes to screen readers -->
<div
  id="live-region"
  aria-live="polite"
  aria-atomic="true"
  style="position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;"
></div>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS = {
    "old_doc_id": None, "old_doc_meta": None,
    "new_doc_id": None, "new_doc_meta": None,
    "session_id": None, "comparison_result": None,
    "chat_history": [], "upload_error": None,
    "last_announcement": "",
    "_last_config": None,   # tracks country/industry/role/language for invalidation
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _announce(msg: str):
    """Inject text into ARIA live region so screen readers announce it."""
    st.markdown(
        f'<script>document.getElementById("live-region").textContent="{msg}";</script>',
        unsafe_allow_html=True,
    )


def _step_indicator():
    old_done = bool(st.session_state.old_doc_id)
    new_done = bool(st.session_state.new_doc_id)
    result_done = bool(st.session_state.comparison_result)

    steps_html = f"""
    <div class="steps" role="list" aria-label="Workflow progress">
      <div class="step {'done' if old_done else 'active'}" role="listitem">
        <span class="step-num" aria-hidden="true">01</span>
        {'✓ ' if old_done else ''}Upload Old Doc
      </div>
      <div class="step {'done' if new_done else ('active' if old_done else '')}" role="listitem">
        <span class="step-num" aria-hidden="true">02</span>
        {'✓ ' if new_done else ''}Upload New Doc
      </div>
      <div class="step {'done' if result_done else ('active' if (old_done and new_done) else '')}" role="listitem">
        <span class="step-num" aria-hidden="true">03</span>
        {'✓ ' if result_done else ''}Run Comparison
      </div>
      <div class="step {'active' if result_done else ''}" role="listitem">
        <span class="step-num" aria-hidden="true">04</span>
        Review Results
      </div>
    </div>
    """
    st.markdown(steps_html, unsafe_allow_html=True)


# ── Layout ────────────────────────────────────────────────────────────────────
config = render_sidebar()
client = APIClient(base_url=config["api_url"])

# If country/industry/role/language changed, discard previous comparison result
# so the user is never shown analysis from a different jurisdiction or language
_config_sig = (config["country"], config["industry"], config["role"], config["language"])
if st.session_state._last_config is not None and st.session_state._last_config != _config_sig:
    st.session_state.comparison_result = None
    st.session_state.session_id = None
    st.session_state.chat_history = []
st.session_state._last_config = _config_sig

# Probe backend once per session; auto-enables mock if unreachable
if "_backend_probed" not in st.session_state:
    st.session_state._backend_probed = True
    st.session_state._backend_live = client.ping()
elif st.session_state.get("_backend_live") is False:
    client.set_mock(True)

st.markdown('<main id="main-content" role="main">', unsafe_allow_html=True)

# Header + steps in one tight block
st.markdown(
    f"""<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:4px;">
      <h1 style="font-family:var(--font-ui,Georgia);font-weight:300;font-size:1.55rem;
          letter-spacing:-0.02em;color:var(--clr-text,#e8eaf0);margin:0;">
          📋 DocCompare
      </h1>
      <span style="color:var(--clr-muted,#8b90a8);font-size:0.8rem;">
          {config['industry'].title()} · {config['country'].upper()} · {config['role'].replace('_',' ').title()}
      </span>
    </div>""",
    unsafe_allow_html=True,
)
_step_indicator()

# ── Upload ────────────────────────────────────────────────────────────────────
render_upload_panel(client, config)

# ── Compare ───────────────────────────────────────────────────────────────────
if st.session_state.old_doc_id and st.session_state.new_doc_id:
    st.markdown(
        '<section aria-label="Run comparison" style="margin-top:12px;">',
        unsafe_allow_html=True,
    )
    col_btn, col_note = st.columns([2, 8])
    with col_btn:
        compare_clicked = st.button(
            "🔍 Run Comparison",
            type="primary",
            use_container_width=True,
            help="Compare both documents. PII is masked before analysis.",
            key="btn_compare",
        )
    with col_note:
        st.markdown(
            '<div class="status-banner status-info" role="note" aria-label="Privacy notice">'
            '🔐 All personally identifiable information (PII) is masked before any AI analysis.'
            '</div>',
            unsafe_allow_html=True,
        )

    if compare_clicked:
        _announce("Comparison started. Masking PII, computing diff, running analysis.")
        with st.spinner("Masking PII → Computing diff → Running RAG analysis…"):
            result = client.compare(
                old_doc_id=st.session_state.old_doc_id,
                new_doc_id=st.session_state.new_doc_id,
                country=config["country"],
                industry=config["industry"],
                role=config["role"],
                language=config["language"],
            )
        if result:
            st.session_state.comparison_result = result
            st.session_state.session_id = result.get("session_id")
            high = result.get("diff_summary", {}).get("high_risk", 0)
            _announce(
                f"Comparison complete. {high} high-risk changes found. "
                "Results are now available in the tabs below."
            )
            st.success(
                f"✅ Comparison complete — "
                f"{result['diff_summary'].get('total_chunks',0)} chunks analysed, "
                f"{high} high-risk changes identified."
            )
        else:
            _announce("Comparison failed. Please check API connection.")
            st.error(
                "❌ Comparison failed. Check that the API is reachable at: "
                f"`{config['api_url']}`"
            )
    st.markdown("</section>", unsafe_allow_html=True)

def _render_qa_tab(client, result, config):
    st.markdown(
        '<section aria-label="Question and answer">',
        unsafe_allow_html=True,
    )
    st.markdown("### 💬 Ask Questions About the Documents")
    st.caption(
        "Answers are grounded in document content only. "
        "The AI cannot cite regulations not present in the uploaded files."
    )

    # Chat history
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state.chat_history):
            with st.chat_message(
                msg["role"],
                avatar="🧑" if msg["role"] == "user" else "🤖",
            ):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and "meta" in msg:
                    m = msg["meta"]
                    st.caption(
                        f"Grounding: {m.get('grounding_confidence',0):.0%} · "
                        f"Tokens: {m.get('tokens_used',0)}"
                    )

    if question := st.chat_input(
        "Ask about regulatory changes, clauses, obligations…",
        key="qa_input",
    ):
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(question)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Searching document context…"):
                answer = client.query(
                    session_id=st.session_state.session_id,
                    question=question,
                    language=config["language"],
                )
            if answer:
                st.markdown(answer["answer"])
                conf = answer.get("grounding_confidence", 0)
                if conf < 0.3:
                    st.markdown(
                        '<div class="status-banner status-warning" role="alert">'
                        '⚠️ Low grounding confidence — verify this answer against source documents.'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                st.caption(
                    f"Grounding confidence: {conf:.0%} · "
                    f"Tokens used: {answer.get('tokens_used', 0)}"
                )
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer["answer"],
                    "meta": answer,
                })
                _announce(f"Answer ready. Grounding confidence: {conf:.0%}.")
            else:
                st.markdown(
                    '<div class="status-banner status-error" role="alert">'
                    '❌ Query failed — check API connection.'
                    '</div>',
                    unsafe_allow_html=True,
                )

    if st.session_state.chat_history:
        if st.button("🗑️ Clear conversation", key="btn_clear_chat",
                     help="Remove all questions and answers from this session"):
            st.session_state.chat_history = []
            _announce("Conversation cleared.")
            st.rerun()

    st.markdown("</section>", unsafe_allow_html=True)


def _render_export_tab(client, result):
    st.markdown(
        '<section aria-label="Export options">',
        unsafe_allow_html=True,
    )
    st.markdown("### 📤 Export Comparison Report")
    st.caption("Exports contain masked text only — PII is never included in exported files.")

    col1, col2, col_spacer = st.columns([3, 3, 4])

    with col1:
        st.markdown("**PDF Report**")
        st.caption("Formatted report with diff summary, impact analysis, and agency context.")
        if client.is_mock:
            st.markdown(
                '<div style="font-size:0.82rem;color:#8b90a8;padding:6px 0;">'
                'PDF export requires a running backend. Use JSON export below.'
                '</div>',
                unsafe_allow_html=True,
            )
        elif st.button(
            "📄 Generate PDF",
            use_container_width=True,
            key="btn_pdf",
            help="Download a formatted PDF report of this comparison",
        ):
            with st.spinner("Generating PDF…"):
                pdf_bytes = client.export_pdf(st.session_state.session_id)
            if pdf_bytes:
                st.download_button(
                    "⬇️ Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"comparison_{st.session_state.session_id[:8]}.pdf",
                    mime="application/pdf",
                    key="dl_pdf",
                )
                _announce("PDF ready. Download button appeared.")
            else:
                st.error("PDF generation failed. Try JSON export instead.")

    with col2:
        st.markdown("**JSON Data**")
        st.caption("Raw comparison data including all diff chunks and analysis.")
        st.download_button(
            "⬇️ Download JSON",
            data=json.dumps(result, indent=2, ensure_ascii=False),
            file_name=f"comparison_{st.session_state.session_id[:8]}.json",
            mime="application/json",
            key="dl_json",
            help="Download the full comparison result as a JSON file",
        )

    st.markdown("</section>", unsafe_allow_html=True)

# ── Results tabs ──────────────────────────────────────────────────────────────
if st.session_state.comparison_result:
    result = st.session_state.comparison_result
    tabs = st.tabs([
        "📊 Diff Viewer",
        "⚖️ Regulatory Impact",
        "💬 Ask Questions",
        "📤 Export",
    ])

    with tabs[0]:
        render_diff_viewer(result, config["risk_filter"])

    with tabs[1]:
        render_impact_panel(result)

    with tabs[2]:
        _render_qa_tab(client, result, config)

    with tabs[3]:
        _render_export_tab(client, result)

st.markdown("</main>", unsafe_allow_html=True)

st.markdown("</main>", unsafe_allow_html=True)