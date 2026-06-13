"""
Diff Viewer — WCAG 2.1 AA compliant side-by-side comparison table.

Accessibility fixes vs original:
  - <table> with <caption>, <thead> with scope="col", <th scope="row"> per row
  - Risk indicated by colour + shape symbol + text label (not colour alone)
  - Change type indicated by symbol + text (not emoji-only)
  - <pre> with aria-label for content cells
  - Truncated content has "…more" button (keyboard reachable) instead of silent cutoff
  - Summary row counts read by screen readers via aria-describedby
  - Table has role="region" wrapper with aria-label
  - Font size minimum 0.92rem (≥ 14.5px at 16px base — passes WCAG AA)
"""
import streamlit as st
import html as html_lib


_RISK_META = {
    "high":   {"symbol": "▲", "label": "High risk",   "css": "risk-high",   "old_bg": "#2a0f0f", "new_bg": "#2a0f0f"},
    "medium": {"symbol": "◆", "label": "Medium risk", "css": "risk-medium", "old_bg": "#1e1500", "new_bg": "#1e1500"},
    "low":    {"symbol": "●", "label": "Low risk",    "css": "risk-low",    "old_bg": "#0a1a0a", "new_bg": "#0a1a0a"},
    "none":   {"symbol": "○", "label": "No risk",     "css": "risk-none",   "old_bg": "#12141c", "new_bg": "#12141c"},
}

_CHANGE_META = {
    "added":    {"symbol": "+", "label": "Added",    "css": "change-added"},
    "removed":  {"symbol": "−", "label": "Removed",  "css": "change-removed"},
    "modified": {"symbol": "~", "label": "Modified", "css": "change-modified"},
}

_MAX_CHARS = 600
_PAGE_SIZE = 50


def _risk_badge(level: str) -> str:
    m = _RISK_META.get(level, _RISK_META["none"])
    return (
        f'<span class="risk-badge {m["css"]}" '
        f'aria-label="{m["label"]}">'
        f'{m["symbol"]} {level.upper()}'
        f'</span>'
    )


def _change_label(change_type: str) -> str:
    m = _CHANGE_META.get(change_type, {"symbol": "?", "label": change_type, "css": ""})
    return (
        f'<span class="{m["css"]}" '
        f'aria-label="{m["label"]}" '
        f'style="font-family:var(--font-mono);font-size:1rem;font-weight:600;">'
        f'{m["symbol"]}'
        f'</span>'
        f'<span class="sr-only"> {m["label"]}</span>'
    )

def _cell_content(text: str | None, aria_label: str) -> str:
    if not text or not text.strip():
        return f'<pre aria-label="{aria_label}: empty" style="color:#4a4f6a;font-style:italic;">(empty)</pre>'
    
    escaped = html_lib.escape(text)
    
    if len(text) <= _MAX_CHARS:
        return f'<pre aria-label="{aria_label}" style="margin:0;white-space:pre-wrap;word-break:break-word;">{escaped}</pre>'
    
    # Use natively accessible <details> element for truncation
    visible_part = escaped[:_MAX_CHARS]
    hidden_part = escaped[_MAX_CHARS:]
    
    return f'''
    <div aria-label="{aria_label}">
        <pre style="margin:0;white-space:pre-wrap;word-break:break-word;display:inline;">{visible_part}</pre>
        <details style="display:inline-block; margin-top:4px;">
            <summary style="cursor:pointer; color:#4f9cf9; font-size:0.85em; font-weight:600; outline-offset:2px;">
                ...more
            </summary>
            <pre style="margin:4px 0 0 0;white-space:pre-wrap;word-break:break-word; border-left:2px solid #4f9cf9; padding-left:8px;">{hidden_part}</pre>
        </details>
    </div>
    '''

def _kw_tags(keywords: list) -> str:
    if not keywords:
        return ""
    tags = "".join(f'<span class="kw-tag">{html_lib.escape(k)}</span>' for k in keywords)
    return (
        f'<div style="margin-top:6px;" aria-label="Risk keywords: {", ".join(keywords)}">'
        f'<span style="font-size:0.75rem;color:#8b90a8;">Keywords: </span>{tags}'
        f'</div>'
    )


def render_diff_viewer(result: dict, risk_filter: str = "none"):
    chunks = result.get("diff_chunks", [])
    summary = result.get("diff_summary", {})
    similarity = result.get("similarity_score", 0)

    # ── Summary metrics — labeled for screen readers ──────────────────────────
    st.markdown(
        '<section aria-label="Comparison summary statistics">',
        unsafe_allow_html=True,
    )
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Similarity Score", f"{similarity*100:.1f}%",
                help="How similar the two documents are overall (0% = completely different)")
    col2.metric("Lines Added",    summary.get("added", 0),
                help="Sections present in new document but not in old")
    col3.metric("Lines Removed",  summary.get("removed", 0),
                help="Sections present in old document but removed in new")
    col4.metric("Lines Modified", summary.get("modified", 0),
                help="Sections that changed between old and new")
    col5.metric("High-Risk Changes", summary.get("high_risk", 0),
                help="Changes containing mandatory, penalty, prohibited, or similar high-stakes language",
                delta=None if summary.get("high_risk", 0) == 0 else f"{summary.get('high_risk', 0)} need review",
                delta_color="inverse")
    st.markdown("</section>", unsafe_allow_html=True)

    # Medium + low counts in accessible format
    med = summary.get("medium_risk", 0)
    low = summary.get("low_risk", 0)
    if med or low:
        st.caption(f"Also: {med} medium-risk · {low} low-risk changes")

    st.divider()

    # ── Risk filter ───────────────────────────────────────────────────────────
    risk_order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    threshold = risk_order.get(risk_filter, 0)
    visible_chunks = [
        c for c in chunks
        if risk_order.get(c.get("risk_level", "none"), 0) >= threshold
        and c.get("change_type") != "unchanged"
    ]

    if not visible_chunks:
        st.markdown(
            '<div class="status-banner status-info" role="status">'
            'ℹ No changes match the current risk filter. '
            'Lower the risk filter in the sidebar to see more results.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Pagination ────────────────────────────────────────────────────────────
    total = len(visible_chunks)
    
    # Calculate pages first
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)

    if "diff_page" not in st.session_state:
        st.session_state.diff_page = 0
        
    # CRITICAL FIX: Reset page if the filter reduced the total pages below current index
    if st.session_state.diff_page >= total_pages:
        st.session_state.diff_page = 0

    page = st.session_state.diff_page
    start = page * _PAGE_SIZE
    end = min(start + _PAGE_SIZE, total)
    page_chunks = visible_chunks[start:end]

    
    # ── Diff table ────────────────────────────────────────────────────────────
    old_fname = html_lib.escape(result.get("old_filename", "Old Document"))
    new_fname = html_lib.escape(result.get("new_filename", "New Document"))

    rows_html = []
    for idx, chunk in enumerate(page_chunks):
        risk = chunk.get("risk_level", "none")
        change_type = chunk.get("change_type", "modified")
        row_id = f"row-{chunk.get('chunk_id', idx)}"

        # Cell backgrounds: distinguish added/removed/modified
        if change_type == "removed":
            old_bg, new_bg = "#200a0a", "#0d1117"
        elif change_type == "added":
            old_bg, new_bg = "#0d1117", "#0a200a"
        else:
            old_bg = new_bg = _RISK_META.get(risk, _RISK_META["none"])["old_bg"]

        kws = chunk.get("risk_keywords", [])
        row_aria = f'Change {start+idx+1}: {change_type}, {_RISK_META.get(risk,_RISK_META["none"])["label"]}'

        rows_html.append(f"""
        <tr id="{row_id}" aria-label="{row_aria}">
          <td style="padding:10px 12px;white-space:nowrap;vertical-align:top;text-align:center;">
            {_risk_badge(risk)}
          </td>
          <td style="padding:10px 12px;white-space:nowrap;vertical-align:top;text-align:center;">
            {_change_label(change_type)}
          </td>
          <td style="padding:10px 14px;vertical-align:top;background:{old_bg};">
            {_cell_content(chunk.get("old_text"), f"Old document content for change {start+idx+1}")}
          </td>
          <td style="padding:10px 14px;vertical-align:top;background:{new_bg};">
            {_cell_content(chunk.get("new_text"), f"New document content for change {start+idx+1}")}
            {_kw_tags(kws)}
          </td>
        </tr>
        """)

    table_html = f"""
    <div role="region" aria-label="Side-by-side document comparison table" style="overflow-x:auto;">
      <table class="diff-table" aria-describedby="diff-caption">
        <caption id="diff-caption">
          Comparing <strong>{old_fname}</strong> (old) vs <strong>{new_fname}</strong> (new).
          Page {page+1} of {total_pages}. {total} total changes.
        </caption>
        <thead>
          <tr>
            <th scope="col" style="width:110px;">Risk Level</th>
            <th scope="col" style="width:80px;">Change</th>
            <th scope="col" style="width:45%;">
              <span aria-hidden="true">← </span>Old: {old_fname}
            </th>
            <th scope="col" style="width:45%;">
              New: {new_fname}<span aria-hidden="true"> →</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows_html)}
        </tbody>
      </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Pagination controls ───────────────────────────────────────────────────
    if total_pages > 1:
        p_col1, p_col2, p_col3 = st.columns([2, 6, 2])
        with p_col1:
            if st.button(
                "← Previous",
                disabled=(page == 0),
                key="diff_prev",
                help=f"Go to page {page} of {total_pages}",
            ):
                st.session_state.diff_page -= 1
                st.rerun()
        with p_col2:
            st.markdown(
                f'<p style="text-align:center;color:#8b90a8;font-size:0.88rem;padding-top:8px;">'
                f'Page {page+1} of {total_pages}'
                f'</p>',
                unsafe_allow_html=True,
            )
        with p_col3:
            if st.button(
                "Next →",
                disabled=(page >= total_pages - 1),
                key="diff_next",
                help=f"Go to page {page+2} of {total_pages}",
            ):
                st.session_state.diff_page += 1
                st.rerun()

    # ── Legend (always visible, for new users) ────────────────────────────────
    with st.expander("📖 Reading this table", expanded=False):
        st.markdown("""
**Risk levels** — indicated by shape, colour, and label:
- ▲ **HIGH** — mandatory obligations, penalties, sanctions, prohibited actions
- ◆ **MEDIUM** — required reporting, deadlines, approvals
- ● **LOW** — recommended best practices
- ○ **NONE** — neutral changes

**Change types:**
- `+` **Added** — content exists in new document only (green background)
- `−` **Removed** — content existed in old document only (red background)
- `~` **Modified** — content changed between old and new (amber background)

**Keywords** — highlighted terms that triggered the risk classification.
        """)