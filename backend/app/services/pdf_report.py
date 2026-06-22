"""Render a one-page brutalist PDF summary from a `pdfaudit.Report`.

The page is laid out as:
  - File header
  - Worst-severity stamp (or "CLEAN" if nothing was found)
  - Counts by severity
  - A table of findings (page, vector, evidence snippet, recommendation)

The visual style intentionally mirrors the Neubrutalism frontend: thick
black borders, hard-offset shadow look (no blur, just a translation),
flat colors, no rounded corners.
"""
from __future__ import annotations

import io
from typing import Iterable
from xml.sax.saxutils import escape as _xml_escape


def _esc(s: object) -> str:
    """Escape text before it goes into a reportlab Paragraph.

    reportlab parses a mini-HTML markup in Paragraph text, so unescaped user
    content (filename, recovered evidence, error messages) containing '<' or '&'
    raises a parse error and 500s the request. Escaping renders it literally.
    """
    return _xml_escape(str(s)) if s is not None else ""

from pdfaudit import Report, Severity
from pdfaudit.model import Finding
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Neubrutalism palette — same tokens as the frontend.
INK = HexColor("#000000")
PAPER = HexColor("#FFFFFF")
SUN = HexColor("#FFEB3B")
PINK = HexColor("#FF4FB4")
SKY = HexColor("#3D9CFF")
LEAF = HexColor("#7CFF6B")
GRAPE = HexColor("#9B5CFF")

# Severity → background color (matches the frontend SeverityBadge).
SEVERITY_FILL = {
    Severity.CRITICAL: PINK,
    Severity.HIGH: SUN,
    Severity.MEDIUM: SKY,
    Severity.LOW: LEAF,
    Severity.INFO: PAPER,
}


def _evidence_snippet(evidence: str | None, max_len: int = 80) -> str:
    """Trim long evidence to a single line, ellipsizing the tail."""
    if not evidence:
        return "—"
    snippet = evidence.replace("\n", " ⏎ ").strip()
    if len(snippet) > max_len:
        snippet = snippet[: max_len - 1] + "…"
    return snippet


def _count_by_severity(findings: Iterable[Finding]) -> dict[Severity, int]:
    counts: dict[Severity, int] = {s: 0 for s in Severity}
    for f in findings:
        counts[f.severity] += 1
    return counts


def render_report_pdf(report: Report) -> bytes:
    """Render a one-page-ish summary PDF and return its bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="PDF Redaction Audit Report",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=22, textColor=INK, leading=24, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=INK, leading=14, spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, textColor=INK, leading=11)
    mono = ParagraphStyle("mono", parent=styles["BodyText"], fontName="Courier", fontSize=8, textColor=INK, leading=10)
    stamp_text = ParagraphStyle("stamp", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=36, alignment=1, leading=40)

    story: list = []

    # Header
    story.append(Paragraph("PDF REDACTION AUDIT", h1))
    story.append(
        Paragraph(
            f"file: <b>{_esc(report.path)}</b> &nbsp; findings: <b>{len(report.findings)}</b>",
            body,
        )
    )
    story.append(Spacer(1, 0.18 * inch))

    # Worst-severity stamp. A no-findings scan is only CLEAN when every detector
    # ran; if a detector errored the result is PARTIAL (not trustworthy-clean).
    worst = report.worst_severity
    if worst is not None:
        stamp_label = worst.label.upper()
        stamp_fill = SEVERITY_FILL[worst]
    elif report.detector_errors:
        stamp_label = "PARTIAL"
        stamp_fill = SUN
    else:
        stamp_label = "CLEAN"
        stamp_fill = LEAF

    stamp_table = Table(
        [[Paragraph(stamp_label, stamp_text)]],
        colWidths=[3.5 * inch],
        rowHeights=[0.8 * inch],
    )
    stamp_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), stamp_fill),
                ("BOX", (0, 0), (-1, -1), 3, INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    # Indent the stamp a touch so it looks like a sticker on the page.
    stamp_row = Table([[stamp_table, ""]], colWidths=[3.7 * inch, 3.0 * inch])
    stamp_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(stamp_row)
    story.append(Spacer(1, 0.18 * inch))

    # Severity counts
    counts = _count_by_severity(report.findings)
    counts_text = " &nbsp;·&nbsp; ".join(
        f"<b>{counts[s]}</b> {s.label.upper()}" for s in reversed(Severity)
    )
    story.append(Paragraph(f"SEVERITY BREAKDOWN: {counts_text}", h2))
    story.append(Spacer(1, 0.08 * inch))

    # Detector errors (if any)
    if report.detector_errors:
        story.append(Paragraph("DETECTOR ERRORS (scan continued with partial coverage):", h2))
        err_lines = "<br/>".join(f"<b>{_esc(name)}</b>: {_esc(msg)}" for name, msg in report.detector_errors.items())
        story.append(Paragraph(err_lines, mono))
        story.append(Spacer(1, 0.08 * inch))

    # Findings table
    story.append(Paragraph("FINDINGS", h2))
    if not report.findings:
        story.append(Paragraph("No recoverable content detected.", body))
    else:
        rows = [["#", "SEV", "VECTOR", "PAGE", "EVIDENCE", "RECOMMENDATION"]]
        for i, f in enumerate(report.findings, start=1):
            rows.append(
                [
                    str(i),
                    f.severity.label.upper(),
                    f.vector,
                    str(f.page) if f.page is not None else "—",
                    # Escaped Paragraph so evidence wraps inside the cell (instead of
                    # overflowing) and markup chars in recovered text can't crash it.
                    Paragraph(_esc(_evidence_snippet(f.evidence)), mono),
                    Paragraph(_esc(f.recommendation or "—"), body),
                ]
            )
        tbl = Table(
            rows,
            colWidths=[0.3 * inch, 0.7 * inch, 1.4 * inch, 0.5 * inch, 2.0 * inch, 2.4 * inch],
            repeatRows=1,
        )
        tbl_style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), PAPER),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTNAME", (4, 1), (4, -1), "Courier"),  # evidence column is monospace
                ("BOX", (0, 0), (-1, -1), 1.5, INK),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, INK),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
        # Color the SEV cell background per row.
        for r, f in enumerate(report.findings, start=1):
            tbl_style.add("BACKGROUND", (1, r), (1, r), SEVERITY_FILL[f.severity])
            tbl_style.add("FONTNAME", (1, r), (1, r), "Helvetica-Bold")
        tbl.setStyle(tbl_style)
        story.append(tbl)

    doc.build(story)
    return buf.getvalue()