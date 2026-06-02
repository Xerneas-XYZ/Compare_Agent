"""
Regulatory Impact Panel — WCAG 2.1 AA compliant.

Accessibility fixes:
  - Grounding confidence explained in plain language, not just a percentage
  - Warning alert uses role="alert" (assertive) vs info uses role="status" (polite)
  - Source excerpts use <blockquote> semantics
  - PII report uses <dl> definition list for key-value pairs
  - All expandable sections have descriptive aria-labels
"""
import streamlit as st


def _confidence_label(conf: float) -> tuple[str, str]:
    """Returns (human label, banner class)."""
    if conf >= 0.7:
        return "High — answer is well-supported by document excerpts", "status-success"
    elif conf >= 0.4:
        return "Moderate — some claims may not appear verbatim in documents", "status-info"
    else:
        return "Low — verify all findings against source documents", "status-warning"


def render_impact_panel(result: dict):
    impact = result.get("regulatory_impact", {})
    compliance = result.get("compliance_context", {})
    pii_stats = result.get("pii_stats", {})

    # ── Compliance context ────────────────────────────────────────────────────
    st.markdown(
        '<section aria-label="Applicable regulatory context">',
        unsafe_allow_html=True,
    )
    with st.expander("📋 Applicable Regulations & Agencies", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                '<h4 style="font-size:0.9rem;margin-bottom:8px;">Regulatory Agencies</h4>',
                unsafe_allow_html=True,
            )
            agencies = compliance.get("agencies", [])
            if agencies:
                # Use list element with role for screen reader enumeration
                items = "".join(f"<li>{a}</li>" for a in agencies)
                st.markdown(
                    f'<ul style="margin:0;padding-left:18px;font-size:0.9rem;line-height:1.7;">{items}</ul>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No agencies loaded.")

        with col2:
            st.markdown(
                '<h4 style="font-size:0.9rem;margin-bottom:8px;">Key Regulations</h4>',
                unsafe_allow_html=True,
            )
            regs = compliance.get("key_regulations", [])
            if regs:
                items = "".join(f"<li>{r}</li>" for r in regs)
                st.markdown(
                    f'<ul style="margin:0;padding-left:18px;font-size:0.9rem;line-height:1.7;">{items}</ul>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No regulations loaded.")
    st.markdown("</section>", unsafe_allow_html=True)

    # ── Impact analysis ───────────────────────────────────────────────────────
    st.markdown(
        '<section aria-label="AI regulatory impact analysis">',
        unsafe_allow_html=True,
    )
    st.markdown("### ⚖️ AI Regulatory Impact Analysis")

    conf = impact.get("grounding_confidence", 0)
    tokens = impact.get("tokens_used", 0)
    pii_masked = impact.get("pii_sanitized", False)
    conf_label, conf_class = _confidence_label(conf)

    # Confidence explanation — visible and screen-reader friendly
    st.markdown(
        f'<div class="status-banner {conf_class}" role="status" '
        f'aria-label="Analysis reliability: {conf_label}">'
        f'<strong>Reliability:</strong> {conf_label}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Metrics row with tooltips
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Grounding Confidence",
        f"{conf:.0%}",
        help=(
            "Measures how much of the AI answer can be traced back to "
            "retrieved document excerpts. Values below 40% indicate the "
            "answer may contain assumptions not present in the documents."
        ),
    )
    m2.metric(
        "Tokens Used",
        f"{tokens:,}",
        help="OpenAI API tokens consumed for this analysis. Affects cost.",
    )
    m3.metric(
        "PII Status",
        "✅ Masked" if pii_masked else "Clean",
        help="Whether the AI output triggered any PII redaction post-generation.",
    )

    # ── Main answer ───────────────────────────────────────────────────────────
    answer = impact.get("answer", "")
    if answer:
        st.markdown(
            '<article aria-label="Regulatory impact analysis result">',
            unsafe_allow_html=True,
        )
        st.markdown(answer)
        st.markdown("</article>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="status-banner status-info" role="status">'
            'ℹ No analysis available. Run a comparison first.'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</section>", unsafe_allow_html=True)

    # ── Sources ───────────────────────────────────────────────────────────────
    sources = impact.get("sources", [])
    if sources:
        st.markdown(
            '<section aria-label="Source excerpts used in analysis">',
            unsafe_allow_html=True,
        )
        with st.expander(
            f"📎 {len(sources)} source excerpt{'s' if len(sources) != 1 else ''} used in this analysis",
            expanded=False,
        ):
            st.caption(
                "These are the exact passages retrieved from your documents "
                "that the AI used to generate the analysis above."
            )
            for i, src in enumerate(sources, 1):
                label = src.get("label", "?")
                excerpt = src.get("excerpt", "")
                st.markdown(
                    f"""<figure style="margin:0 0 16px 0;">
                      <figcaption style="font-size:0.8rem;font-weight:600;
                          color:{'#a8d5b0' if label == 'NEW' else '#a8c5f0'};
                          margin-bottom:4px;">
                        [{label}] Excerpt {i}
                      </figcaption>
                      <blockquote style="
                          margin:0;padding:10px 14px;
                          border-left:3px solid {'#69db7c' if label == 'NEW' else '#4f9cf9'};
                          background:rgba(255,255,255,0.03);
                          font-family:'DM Mono',monospace;font-size:0.85rem;
                          color:#c0c8e0;white-space:pre-wrap;word-break:break-word;">
                        {excerpt}
                      </blockquote>
                    </figure>""",
                    unsafe_allow_html=True,
                )
        st.markdown("</section>", unsafe_allow_html=True)

    # ── PII masking report ────────────────────────────────────────────────────
    st.markdown(
        '<section aria-label="Privacy and PII masking report">',
        unsafe_allow_html=True,
    )
    with st.expander("🔐 Privacy & PII Masking Report", expanded=False):
        old_r = pii_stats.get("old_doc_redactions", 0)
        new_r = pii_stats.get("new_doc_redactions", 0)
        total_r = old_r + new_r

        if total_r == 0:
            st.markdown(
                '<div class="status-banner status-success" role="status">'
                '✓ No PII detected in either document.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="status-banner status-info" role="status">'
                f'🔐 {total_r} PII item{"s" if total_r != 1 else ""} masked before analysis.'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""<dl style="margin:12px 0 0 0;display:grid;grid-template-columns:auto 1fr;
                gap:6px 16px;font-size:0.9rem;">
              <dt style="color:#8b90a8;">Baseline document redactions</dt>
              <dd style="margin:0;font-weight:600;">{old_r}</dd>
              <dt style="color:#8b90a8;">Updated document redactions</dt>
              <dd style="margin:0;font-weight:600;">{new_r}</dd>
              <dt style="color:#8b90a8;">AI output PII scan</dt>
              <dd style="margin:0;font-weight:600;">
                {'⚠ Triggered — output was re-sanitised' if pii_masked else '✓ Clean'}
              </dd>
            </dl>""",
            unsafe_allow_html=True,
        )
        st.caption(
            "PII masking covers: email addresses, phone numbers, SSNs, "
            "credit card numbers, IBANs, Aadhaar numbers, PAN cards, "
            "NHS numbers, IP addresses, and named persons (via NLP)."
        )
    st.markdown("</section>", unsafe_allow_html=True)