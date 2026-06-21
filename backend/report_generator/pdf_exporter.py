import os
import logging
from typing import Dict, Any
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

logger = logging.getLogger("metricguard.pdf_exporter")

# Resolve root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GENERATED_DIR = os.path.join(BASE_DIR, "reports", "generated")


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas pattern to compute total page count dynamically 
    and draw consistent headers, footers, and page numbers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569")) # Slate-600

        # Header (Top margin is 72, usable height ends at 720. Header drawn at y=750)
        self.drawString(54, 750, "METRICGUARD — AIOPS ANOMALY DETECTION PLATFORM")
        self.setFont("Helvetica", 8)
        self.drawRightString(558, 750, "CONFIDENTIAL")
        
        # Header divider line
        self.setStrokeColor(colors.HexColor("#cbd5e1")) # Slate-300
        self.setLineWidth(0.5)
        self.line(54, 742, 558, 742)

        # Footer (Bottom margin is 72, usable height starts at 72. Footer drawn at y=40)
        self.line(54, 52, 558, 52)
        self.drawString(54, 40, "MetricGuard Automated System Report")
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 40, page_text)
        
        self.restoreState()


def generate_pdf(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a professional PDF report containing details of the incident,
    RCA confidence, service health, recommendations, and active alerts.
    """
    report_id = report_data.get("report_id", "REP-UNKNOWN")
    logger.info("[PDF_EXPORTER] Exporting PDF for %s.pdf", report_id)

    # Resolve output filepath
    file_path = os.path.join(GENERATED_DIR, f"{report_id}.pdf")
    os.makedirs(GENERATED_DIR, exist_ok=True)

    # Document Setup
    # 54pt margin = 0.75 in. Total width=612, usable width = 612 - 54*2 = 504.
    # Top/Bottom margin set to 72pt (1 in) to clear header/footer text.
    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#ffffff"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#cbd5e1"), # Light Slate
        leading=13,
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#0f172a"), # Slate-900
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=colors.HexColor("#334155"), # Slate-700
        leading=14,
    )
    label_style = ParagraphStyle(
        "ReportLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=colors.HexColor("#1e293b"),
    )
    header_cell_style = ParagraphStyle(
        "HeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.white,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#334155"),
        leading=12,
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell_style,
        fontName="Helvetica-Bold",
    )

    story = []

    # 1. Indigo Title Banner Table
    banner_text = Paragraph(f"INCIDENT SYSTEM REPORT", title_style)
    banner_meta = Paragraph(
        f"<b>Report ID:</b> {report_id}<br/>"
        f"<b>Generated At:</b> {report_data.get('created_at', '')[:19].replace('T', ' ')} UTC",
        subtitle_style
    )
    banner_table = Table([[banner_text, banner_meta]], colWidths=[280, 224])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#312e81")), # Indigo-900
        ('PADDING', (0,0), (-1,-1), 16),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 14))

    # 2. Executive Summary Callout Box
    incident_section = report_data.get("incident", {})
    status = incident_section.get("status", "N/A")
    severity = incident_section.get("severity", "N/A")
    priority = incident_section.get("priority", "N/A")
    root_cause = incident_section.get("root_cause", "N/A")

    summary_text = (
        f"<b>Incident:</b> {incident_section.get('incident_id', 'N/A')} &nbsp;|&nbsp; "
        f"<b>Severity:</b> {severity} &nbsp;|&nbsp; "
        f"<b>Priority:</b> {priority} &nbsp;|&nbsp; "
        f"<b>Status:</b> {status}<br/>"
        f"<b>Primary Root Cause:</b> {root_cause}"
    )
    summary_box_style = ParagraphStyle(
        "SummaryBoxText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#1e3a8a"),
        leading=14,
    )
    summary_table = Table([[Paragraph(summary_text, summary_box_style)]], colWidths=[504])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#eff6ff")), # Blue-50
        ('PADDING', (0,0), (-1,-1), 12),
        ('LINELEFT', (0,0), (0,-1), 4, colors.HexColor("#2563eb")), # Blue-600
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # 3. Incident Details Section
    story.append(Paragraph("1. Incident Details", section_title_style))
    details_data = [
        [Paragraph("Incident ID", label_style), Paragraph(incident_section.get("incident_id", "N/A"), body_style),
         Paragraph("Lifecycle Status", label_style), Paragraph(status, body_style)],
        [Paragraph("Severity Level", label_style), Paragraph(severity, body_style),
         Paragraph("Incident Priority", label_style), Paragraph(priority, body_style)],
        [Paragraph("Created Time", label_style), Paragraph(incident_section.get("created_at", "N/A")[:19].replace('T', ' '), body_style),
         Paragraph("Alert Count", label_style), Paragraph(str(incident_section.get("alert_count", 0)), body_style)]
    ]
    details_table = Table(details_data, colWidths=[100, 152, 100, 152])
    details_table.setStyle(TableStyle([
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor("#f8fafc"), colors.white]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 14))

    # 4. Root Cause Analysis
    story.append(Paragraph("2. Root Cause Analysis (RCA)", section_title_style))
    rca_section = report_data.get("root_cause", {})
    confidence_val = rca_section.get("confidence", 0.0)
    score_val = rca_section.get("score", 0.0)
    
    rca_data = [
        [Paragraph("Inferred Cause", label_style), Paragraph(rca_section.get("cause", "N/A"), body_style)],
        [Paragraph("Correlation Score", label_style), Paragraph(f"{score_val:.2f} / 1.00", body_style)],
        [Paragraph("RCA Confidence", label_style), Paragraph(f"{confidence_val:.1f}%", body_style)]
    ]
    rca_table = Table(rca_data, colWidths=[130, 374])
    rca_table.setStyle(TableStyle([
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor("#f8fafc"), colors.white]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(rca_table)
    story.append(Spacer(1, 14))

    # 5. Service Health & Impacted Services
    story.append(Paragraph("3. Impacted Services & Health Status", section_title_style))
    health_section = report_data.get("service_health", {})
    overall_health = health_section.get("overall_status", "healthy").upper()

    health_box_colors = {
        "HEALTHY": ("#dcfce7", "#15803d"),   # Green
        "WARNING": ("#fef9c3", "#a16207"),   # Yellow
        "DEGRADED": ("#ffedd5", "#c2410c"),  # Orange
        "CRITICAL": ("#fee2e2", "#b91c1c"),  # Red
    }
    bg_col, fg_col = health_box_colors.get(overall_health, ("#f1f5f9", "#475569"))
    
    health_summary_text = f"<b>Overall Service Topology Health:</b> <font color='{fg_col}'><b>{overall_health}</b></font>"
    health_box = Table([[Paragraph(health_summary_text, summary_box_style)]], colWidths=[504])
    health_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg_col)),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor(fg_col)),
    ]))
    story.append(health_box)
    story.append(Spacer(1, 8))

    # Table of service statuses
    health_details = health_section.get("details", [])
    if health_details:
        health_table_data = [
            [Paragraph("Service Name", header_cell_style), 
             Paragraph("Health Status", header_cell_style), 
             Paragraph("Severity", header_cell_style), 
             Paragraph("Root Dependency", header_cell_style)]
        ]
        for item in health_details:
            status_str = item.get("status", "healthy").upper()
            _, item_fg = health_box_colors.get(status_str, ("#f1f5f9", "#475569"))
            
            health_table_data.append([
                Paragraph(item.get("service_name", "N/A").title(), table_cell_bold),
                Paragraph(f"<font color='{item_fg}'><b>{status_str}</b></font>", table_cell_style),
                Paragraph(item.get("severity", "none").upper(), table_cell_style),
                Paragraph(item.get("root_dependency", "None") or "None", table_cell_style),
            ])
        
        health_table = Table(health_table_data, colWidths=[140, 120, 110, 134])
        health_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('PADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(health_table)
    else:
        story.append(Paragraph("No service health details available.", body_style))
    story.append(Spacer(1, 14))

    # Page break if necessary or let reportlab autobreak. Let's force page break to keep Recommendations and Alerts clean on page 2 if needed.
    # To keep pages balanced, let's append a page break here so Recommendations and Alerts are together.
    story.append(PageBreak())

    # 6. Smart Recommendations
    story.append(Paragraph("4. Remediation Recommendations", section_title_style))
    recs_detail = report_data.get("recommendations_detail", [])
    if recs_detail:
        recs_table_data = [
            [Paragraph("Remediation Action Item", header_cell_style), 
             Paragraph("Confidence Score", header_cell_style)]
        ]
        for r in recs_detail:
            conf_pct = r.get("confidence", 0.0) * 100
            recs_table_data.append([
                Paragraph(r.get("action", "N/A"), table_cell_style),
                Paragraph(f"<b>{conf_pct:.0f}%</b>", table_cell_style),
            ])
        recs_table = Table(recs_table_data, colWidths=[400, 104])
        recs_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(recs_table)
    else:
        story.append(Paragraph("No remediation recommendations available for this root cause.", body_style))
    story.append(Spacer(1, 14))

    # 7. Active Alerts Timeline
    story.append(Paragraph("5. Active Alert Timeline Correlation", section_title_style))
    alerts_list = report_data.get("alerts", [])
    if alerts_list:
        alerts_table_data = [
            [Paragraph("Alert ID", header_cell_style), 
             Paragraph("Severity", header_cell_style), 
             Paragraph("Alert Details & Message", header_cell_style), 
             Paragraph("Timestamp", header_cell_style)]
        ]
        for a in alerts_list:
            sev_str = a.get("severity", "LOW").upper()
            _, sev_fg = health_box_colors.get(sev_str, ("#f1f5f9", "#475569"))
            
            alerts_table_data.append([
                Paragraph(a.get("alert_id", "N/A"), table_cell_bold),
                Paragraph(f"<font color='{sev_fg}'><b>{sev_str}</b></font>", table_cell_style),
                Paragraph(f"<b>{a.get('title', 'N/A')}</b><br/>{a.get('message', 'N/A')}", table_cell_style),
                Paragraph(a.get("timestamp", "N/A")[:19].replace('T', ' '), table_cell_style),
            ])
        alerts_table = Table(alerts_table_data, colWidths=[80, 80, 230, 114])
        alerts_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(alerts_table)
    else:
        story.append(Paragraph("No matching alerts correlated within the incident timeframe.", body_style))

    # Build Document using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)

    logger.info("[PDF_EXPORTER] Exported PDF %s.pdf successfully", report_id)
    return {
        "file_path": file_path,
        "format": "pdf"
    }
