"""
Export Router
GET /api/v1/export/{session_id}/pdf   — Export comparison report as PDF
GET /api/v1/export/{session_id}/json  — Export raw comparison result as JSON
"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_session(session_id: str) -> dict:
    from app.api.compare import _sessions
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.get("/export/{session_id}/json", summary="Export comparison result as JSON")
async def export_json(session_id: str):
    session = _get_session(session_id)
    result = session["result"]
    return JSONResponse(
        content=result,
        headers={
            "Content-Disposition": f'attachment; filename="comparison_{session_id[:8]}.json"'
        }
    )


@router.get("/export/{session_id}/pdf", summary="Export comparison report as PDF")
async def export_pdf(session_id: str):
    """Generate a minimal PDF report using reportlab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        import io

        session = _get_session(session_id)
        result = session["result"]

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph("Document Comparison Report", styles["Title"]))
        story.append(Spacer(1, 12))

        # Metadata
        meta = [
            ["Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
            ["Old Document", result["old_filename"]],
            ["New Document", result["new_filename"]],
            ["Similarity Score", f"{result['similarity_score']*100:.1f}%"],
            ["Country", result["compliance_context"]["country"].upper()],
            ["Industry", result["compliance_context"]["industry"].title()],
            ["Role", result["compliance_context"]["role"].replace("_", " ").title()],
        ]
        t = Table(meta, colWidths=[150, 350])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.lightblue),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))

        # Diff summary
        story.append(Paragraph("Change Summary", styles["Heading2"]))
        summary = result["diff_summary"]
        summary_data = [["Metric", "Count"]] + [
            [k.replace("_", " ").title(), str(v)]
            for k, v in summary.items()
        ]
        st = Table(summary_data, colWidths=[250, 100])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(st)
        story.append(Spacer(1, 16))

        # Regulatory impact
        story.append(Paragraph("Regulatory Impact Analysis", styles["Heading2"]))
        impact_text = result["regulatory_impact"]["answer"]
        for para in impact_text.split("\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), styles["Normal"]))
                story.append(Spacer(1, 4))

        # Agencies
        story.append(Spacer(1, 12))
        story.append(Paragraph("Applicable Agencies & Regulations", styles["Heading2"]))
        agencies = ", ".join(result["compliance_context"]["agencies"])
        regs = ", ".join(result["compliance_context"]["key_regulations"])
        story.append(Paragraph(f"<b>Agencies:</b> {agencies}", styles["Normal"]))
        story.append(Paragraph(f"<b>Key Regulations:</b> {regs}", styles["Normal"]))

        doc.build(story)
        buf.seek(0)

        return Response(
            content=buf.read(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="comparison_{session_id[:8]}.pdf"'
            }
        )

    except ImportError:
        raise HTTPException(500, "reportlab not installed. Run: pip install reportlab")
    except Exception as e:
        logger.exception("PDF export failed")
        raise HTTPException(500, f"PDF generation failed: {str(e)}")