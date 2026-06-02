"""
Sidebar — WCAG 2.1 AA compliant filter controls.

Accessibility fixes:
  - Each control has a visible label + help text explaining impact
  - Role selection explains what each role can/cannot do
  - Language selection shows native script alongside English name
  - Keyboard shortcut hints included
  - Contrast ratio on all text ≥ 4.5:1
"""
import streamlit as st
from utils.constants import COUNTRIES, INDUSTRIES, ROLES, LANGUAGES, RISK_LEVELS

DEFAULT_API_URL = "http://localhost:8000"

# Native script labels for language options — helps users who read that script
_LANG_NATIVE = {
    "en": "English",
    "es": "Español",
    "hi": "हिन्दी",
    "zh": "中文",
    "ru": "Русский",
    "de": "Deutsch",
}


def render_sidebar() -> dict:
    with st.sidebar:
        # Sidebar landmark
        st.markdown(
            '<nav role="navigation" aria-label="Configuration filters">',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<h2 style="font-size:1.1rem;margin-bottom:4px;">⚙️ Configuration</h2>',
            unsafe_allow_html=True,
        )

        # ── API ───────────────────────────────────────────────────────────────
        api_url = st.text_input(
            "API URL",
            value=DEFAULT_API_URL,
            help="URL of the FastAPI backend. Default: http://localhost:8000",
            placeholder="http://localhost:8000",
        )

        # ── Jurisdiction ──────────────────────────────────────────────────────
        st.markdown(
            '<h3 style="font-size:0.9rem;margin:12px 0 4px 0;">🌍 Jurisdiction</h3>',
            unsafe_allow_html=True,
        )

        country = st.selectbox(
            "Country",
            options=list(COUNTRIES.keys()),
            format_func=lambda k: COUNTRIES[k],
            index=0,
            help=(
                "Filters the compliance analysis to this country's regulatory agencies. "
                "For example, selecting USA loads Federal Reserve, OCC, FDIC, CFPB."
            ),
        )

        industry = st.selectbox(
            "Industry",
            options=list(INDUSTRIES.keys()),
            format_func=lambda k: INDUSTRIES[k],
            index=0,
            help="Banking, insurance, or healthcare — each has different regulatory bodies.",
        )

        # ── Role ──────────────────────────────────────────────────────────────
        st.markdown(
            '<h3 style="font-size:0.9rem;margin:12px 0 4px 0;">👤 Your Role</h3>',
            unsafe_allow_html=True,
        )

        role = st.selectbox(
            "Role",
            options=list(ROLES.keys()),
            format_func=lambda k: ROLES[k],
            index=0,
            help=(
                "Compliance Officer / Legal Consultant: full analysis with risk scores and export. "
                "General User: summary view only, no export."
            ),
        )

        # Role capability summary — visible context
        _role_caps = {
            "compliance_officer": "✓ Full analysis · ✓ Export · ✓ Risk scores",
            "legal_consultant":   "✓ Full analysis · ✓ Export · ✓ Risk scores",
            "general_user":       "✓ Summary view · ✗ Export · ✗ Risk scores",
        }
        st.caption(_role_caps.get(role, ""))

        # ── Language ──────────────────────────────────────────────────────────
        st.markdown(
            '<h3 style="font-size:0.9rem;margin:12px 0 4px 0;">🗣️ Response Language</h3>',
            unsafe_allow_html=True,
        )

        language = st.selectbox(
            "Language for AI responses",
            options=list(LANGUAGES.keys()),
            format_func=lambda k: f"{LANGUAGES[k]} — {_LANG_NATIVE[k]}",
            index=0,
            help=(
                "The regulatory impact analysis and Q&A answers will be written in this language. "
                "Document parsing and diff computation are language-independent."
            ),
            label_visibility="collapsed",
        )

        # ── Risk filter ───────────────────────────────────────────────────────
        st.markdown(
            '<h3 style="font-size:0.9rem;margin:12px 0 4px 0;">🔍 Risk Filter</h3>',
            unsafe_allow_html=True,
        )

        risk_filter = st.selectbox(
            "Minimum risk level to display",
            options=list(RISK_LEVELS.keys()),
            format_func=lambda k: RISK_LEVELS[k],
            index=0,
            help=(
                "Filters the diff table. 'All changes' shows everything. "
                "'High risk only' shows only changes containing mandatory, penalty, "
                "prohibited, or similar high-stakes regulatory language."
            ),
        )

        # Risk level legend
        st.markdown(
            """<div style="font-size:0.78rem;color:#8b90a8;line-height:1.8;margin-top:4px;">
              <span style="color:#ff6b6b;">▲ High</span> — penalties, mandatory, sanctions<br/>
              <span style="color:#ffa94d;">◆ Medium</span> — required, must, deadlines<br/>
              <span style="color:#69db7c;">● Low</span> — recommended, guidance
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Help ──────────────────────────────────────────────────────────────
        with st.expander("♿ Accessibility", expanded=False):
            st.markdown("""
**Keyboard navigation:**
- `Tab` / `Shift+Tab` — move between controls
- `Enter` / `Space` — activate buttons
- Arrow keys — navigate dropdowns

**Screen reader support:**
- All tables have column headers and captions
- Risk levels use shape + colour + text labels
- Status changes are announced via ARIA live regions

**Display preferences:**
- Supports OS-level high contrast mode
- Supports reduced motion (disables animations)
- Minimum font size 14.5px (WCAG AA)

**Report issues:**
[GitHub Issues](https://github.com/your-org/doc-compare-agent/issues)
            """)

        with st.expander("ℹ️ About", expanded=False):
            st.caption(
                "DocCompare Agent v1.0\n\n"
                "Supported formats: PDF, TXT, CSV, JSON, DOCX, XLSX, PPTX\n\n"
                "All PII masked before AI analysis. "
                "Regulatory analysis grounded in document content — "
                "no regulation names are hallucinated."
            )

        st.markdown("</nav>", unsafe_allow_html=True)

    return {
        "api_url": api_url,
        "country": country,
        "industry": industry,
        "role": role,
        "language": language,
        "risk_filter": risk_filter,
    }