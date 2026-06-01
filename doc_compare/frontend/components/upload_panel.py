"""
Upload Panel — WCAG 2.1 AA compliant, with demo-mode support.
"""
import streamlit as st
from pathlib import Path

_ALLOWED_TYPES = ["pdf", "txt", "csv", "json", "docx", "xlsx", "pptx"]
_MAX_MB = 50


def _fmt_size(char_count: int) -> str:
    kb = char_count / 1024
    if kb < 1024:
        return f"{kb:.0f} KB"
    return f"{kb/1024:.1f} MB"


def _doc_card(label: str, meta: dict):
    fmt = str(meta.get("format", "—")).upper()
    fname = meta.get("filename", "—")
    size = _fmt_size(meta.get("char_count", 0))
    pages = f" · {meta['page_count']} pages" if meta.get("page_count") else ""
    st.markdown(
        f'<div style="background:rgba(105,219,124,0.08);border:1px solid rgba(105,219,124,0.25);'
        f'border-radius:8px;padding:10px 12px;" role="status" aria-label="{label} uploaded successfully">'
        f'<div style="font-size:0.78rem;color:#69db7c;font-weight:600;margin-bottom:3px;">✓ {label} ready</div>'
        f'<div style="font-size:0.82rem;color:#b0b8d0;font-family:monospace;">'
        f'📄 {fname} &nbsp;·&nbsp; {fmt} &nbsp;·&nbsp; {size}{pages}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _error_card(msg: str, doc_label: str):
    # Note: all content on same line inside each div — avoids Streamlit stripping
    # closing tags and leaking adjacent text characters into the rendered output
    st.markdown(
        f'<div style="background:rgba(255,107,107,0.08);border:1px solid rgba(255,107,107,0.3);'
        f'border-radius:8px;padding:10px 12px;" role="alert" aria-label="{doc_label} upload error">'
        f'<div style="font-size:0.85rem;color:#ff6b6b;font-weight:600;">⚠ Upload failed</div>'
        f'<div style="font-size:0.82rem;color:#d0b0b0;margin-top:3px;">{msg}</div>'
        f'<div style="font-size:0.75rem;color:#8b90a8;margin-top:4px;">Accepted: PDF, TXT, CSV, JSON, DOCX, XLSX, PPTX · Max {_MAX_MB} MB</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _demo_banner():
    st.markdown(
        '<div style="background:rgba(255,169,77,0.08);border:1px solid rgba(255,169,77,0.25);'
        'border-radius:8px;padding:8px 12px;margin-bottom:6px;font-size:0.82rem;color:#ffa94d;" '
        'role="status" aria-label="Demo mode active">'
        '🎭 <strong>Demo mode</strong> — backend not reachable. '
        'Uploads are accepted and a sample comparison will run so you can explore the UI. '
        'Start the FastAPI backend to use real documents.'
        '</div>',
        unsafe_allow_html=True,
    )


def render_upload_panel(client, config):
    # ── Demo mode banner ──────────────────────────────────────────────────────
    if client.is_mock:
        _demo_banner()

    st.markdown(
        '<section aria-label="Document upload" id="upload-section">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">'
        '<span style="font-size:0.95rem;font-weight:600;">📁 Upload Documents</span>'
        '<span style="font-size:0.78rem;color:#8b90a8;">PDF, TXT, CSV, JSON, DOCX, XLSX, PPTX · Max 50 MB</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    col_old, col_new = st.columns(2, gap="medium")

    # ── Old document ──────────────────────────────────────────────────────────
    with col_old:
        st.markdown(
            '<p style="font-size:0.88rem;font-weight:600;margin:0 0 2px 0;color:#c8cfe0;">'
            '📄 Baseline / Old Document</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<span style="font-size:0.75rem;color:#8b90a8;">Previous version — comparing FROM</span>',
            unsafe_allow_html=True,
        )
        old_file = st.file_uploader(
            "Upload baseline document",
            type=_ALLOWED_TYPES,
            key="old_uploader",
            help="Previous version of your policy or regulatory document",
            label_visibility="collapsed",
        )

        if old_file:
            if st.session_state.get("_old_fname") != old_file.name:
                with st.spinner(f"Uploading {old_file.name}…"):
                    result = client.upload(old_file)
                if result:
                    st.session_state.old_doc_id = result
                    st.session_state.old_doc_meta = client.last_upload_meta
                    st.session_state["_old_fname"] = old_file.name
                    st.session_state["_old_err"] = None
                else:
                    st.session_state.old_doc_id = None
                    st.session_state["_old_err"] = client.last_error or "Upload failed"

            if st.session_state.old_doc_id and st.session_state.get("old_doc_meta"):
                _doc_card("Baseline document", st.session_state.old_doc_meta)
            elif st.session_state.get("_old_err"):
                _error_card(st.session_state["_old_err"], "Baseline document")
        else:
            st.markdown(
                '<div style="border:2px dashed #2e3245;border-radius:8px;padding:10px 12px;'
                'background:#1a1d27;font-size:0.78rem;color:#8b90a8;" aria-hidden="true">'
                '📂 Drag &amp; drop or click Browse above</div>',
                unsafe_allow_html=True,
            )

    # ── New document ──────────────────────────────────────────────────────────
    with col_new:
        st.markdown(
            '<p style="font-size:0.88rem;font-weight:600;margin:0 0 2px 0;color:#c8cfe0;">'
            '📄 Updated / New Document</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<span style="font-size:0.75rem;color:#8b90a8;">Current version — comparing TO</span>',
            unsafe_allow_html=True,
        )
        new_file = st.file_uploader(
            "Upload updated document",
            type=_ALLOWED_TYPES,
            key="new_uploader",
            help="New or updated version of the document",
            label_visibility="collapsed",
        )

        if new_file:
            if st.session_state.get("_new_fname") != new_file.name:
                with st.spinner(f"Uploading {new_file.name}…"):
                    result = client.upload(new_file)
                if result:
                    st.session_state.new_doc_id = result
                    st.session_state.new_doc_meta = client.last_upload_meta
                    st.session_state["_new_fname"] = new_file.name
                    st.session_state["_new_err"] = None
                else:
                    st.session_state.new_doc_id = None
                    st.session_state["_new_err"] = client.last_error or "Upload failed"

            if st.session_state.new_doc_id and st.session_state.get("new_doc_meta"):
                _doc_card("Updated document", st.session_state.new_doc_meta)
            elif st.session_state.get("_new_err"):
                _error_card(st.session_state["_new_err"], "Updated document")
        else:
            st.markdown(
                '<div style="border:2px dashed #2e3245;border-radius:8px;padding:10px 12px;'
                'background:#1a1d27;font-size:0.78rem;color:#8b90a8;" aria-hidden="true">'
                '📂 Drag &amp; drop or click Browse above</div>',
                unsafe_allow_html=True,
            )

    # ── Clear button ──────────────────────────────────────────────────────────
    if st.session_state.old_doc_id or st.session_state.new_doc_id:
        if st.button("✕ Clear uploads", key="btn_clear_uploads",
                     help="Remove uploaded documents and start over"):
            for k in ["old_doc_id", "old_doc_meta", "_old_fname", "_old_err",
                      "new_doc_id", "new_doc_meta", "_new_fname", "_new_err",
                      "comparison_result", "session_id", "chat_history"]:
                st.session_state[k] = None if "history" not in k else []
            st.rerun()

    st.markdown("</section>", unsafe_allow_html=True)