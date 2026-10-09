"""
PDF Report Generator for GTIN Validator.
Produces a branded, professional PDF report using reportlab.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from brand_fonts import SANS, SANS_BOLD, SERIF_BOLD, register_fonts
from gtin_core import Severity

if TYPE_CHECKING:
    from gtin_core import BatchResult

# Colors — Lailara Design System v2 tokens (was an off-palette Bootstrap scheme)
INK = colors.HexColor("#0d0d0d")          # London-5 — headings, headline numbers
BODY = colors.HexColor("#333333")         # London-20 — body text
GRAY = colors.HexColor("#595959")         # London-35 — subtitles, small text
LIGHT_GRAY = colors.HexColor("#f2f2f2")   # London-95 — zebra row fill
RULE = colors.HexColor("#d9d9d9")         # London-85 — hairline rules, table grid
HEADER_BG = colors.HexColor("#1f2e7a")    # Chicago-20 — table header fill
ACCENT = colors.HexColor("#cc100a")       # Red-42 — brand accent (ink only)
GREEN = colors.HexColor("#158f75")        # Hong Kong-35 — pass / clean
YELLOW = colors.HexColor("#ee8a2a")       # Singapore-55 — warnings
RED = colors.HexColor("#cc100a")          # Red-42 — critical (ink: dots, icons, text)
INFO = colors.HexColor("#1f2e7a")         # Chicago-20 — info severity
SG_SURFACE = colors.HexColor("#fdeee0")   # Singapore-95 — total-row highlight
WHITE = colors.white

# Approximate page height available for content (letter = 792pt, minus margins and buffer)
PAGE_CONTENT_HEIGHT = 792 - (0.75 * 72 * 2) - 40  # ~600pt usable


def severity_color(severity):
    if severity == Severity.CRITICAL:
        return RED
    elif severity == Severity.WARNING:
        return YELLOW
    return INFO


def check_name(check: dict) -> str:
    """Retailer check name with arrows spelled out: the brand fonts have no U+2192."""
    return str(check["check"]).replace(" → ", "-to-")


def generate_pdf_report(validation_data: BatchResult, company_name: str = "") -> BytesIO:
    """Generate a branded PDF report and return as BytesIO."""
    register_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=SERIF_BOLD,
        fontSize=22,
        textColor=INK,
        spaceAfter=6,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName=SANS,
        fontSize=11,
        textColor=GRAY,
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName=SERIF_BOLD,
        fontSize=14,
        textColor=INK,
        spaceBefore=20,
        spaceAfter=10,
        borderWidth=0,
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontName=SANS,
        fontSize=10,
        textColor=BODY,
        spaceAfter=6,
        leading=14,
    )
    small_style = ParagraphStyle(
        "SmallText",
        parent=styles["Normal"],
        fontName=SANS,
        fontSize=8,
        textColor=GRAY,
        spaceAfter=4,
    )
    score_style = ParagraphStyle(
        "ScoreText",
        parent=styles["Normal"],
        fontName=SERIF_BOLD,
        fontSize=36,
        textColor=INK,
        alignment=TA_CENTER,
        spaceAfter=4,
        leading=44,
    )
    grade_style = ParagraphStyle(
        "GradeText",
        parent=styles["Normal"],
        fontName=SANS,
        fontSize=16,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceBefore=16,
        spaceAfter=16,
    )

    elements = []
    summary = validation_data["summary"]
    score = validation_data["score"]
    cost = validation_data["cost_estimate"]
    results = validation_data["results"]

    # --- Title page content ---
    report_title = "Product Data Validation Report"
    if company_name:
        elements.append(Paragraph(company_name, ParagraphStyle(
            "CompanyName", parent=styles["Normal"], fontName=SANS,
            fontSize=12, textColor=ACCENT, spaceAfter=4,
        )))

    elements.append(Paragraph(report_title, title_style))
    elements.append(Paragraph(
        f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        subtitle_style,
    ))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=RULE,
        spaceAfter=20,
    ))

    # --- Readiness Score ---
    elements.append(Paragraph("Submission Readiness Score", heading_style))

    score_color = GREEN if score["score"] >= 75 else (YELLOW if score["score"] >= 50 else RED)
    elements.append(Paragraph(
        f'<font color="{score_color.hexval()}">{score["score"]}</font>'
        f'<font color="{GRAY.hexval()}"> / 100</font>',
        score_style,
    ))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f'Grade: {score["grade"]}', grade_style))
    elements.append(Paragraph(score["interpretation"], body_style))
    elements.append(Spacer(1, 12))

    # --- Summary table ---
    elements.append(Paragraph("Summary", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total GTINs Analyzed", str(summary["total_gtins"])],
        ["Valid GTINs", str(summary["valid"])],
        ["Critical Issues", str(summary["critical_issues"])],
        ["Warnings", str(summary["warnings"])],
        ["Clean (No Errors/Warnings)", str(summary["clean"])],
        ["Duplicate Groups", str(summary["duplicate_groups"])],
        ["Unique Company Prefixes", str(summary["unique_prefixes"])],
    ]
    summary_table = Table(summary_data, colWidths=[3.5 * inch, 2 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (-1, -1), SANS),
        ("FONTNAME", (0, 0), (-1, 0), SANS_BOLD),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # --- Cost of Inaction ---
    if cost:
        elements.append(PageBreak())
        elements.append(Paragraph("Estimated Cost of Inaction", heading_style))
        elements.append(Paragraph(
            "These are planning assumptions applied to your data, not sourced facts. "
            "The per-unit figures behind each total are listed below the table — "
            "adjust them to your own retailer terms and volume.",
            small_style,
        ))

        cost_data = [
            ["Cost Category", "Estimated Annual Range"],
            [
                "Chargebacks from invalid GTINs",
                f"${cost['chargeback_range'][0]:,} – ${cost['chargeback_range'][1]:,}",
            ],
            [
                f"Delayed retailer launches ({cost['delayed_skus']} SKUs)",
                f"${cost['delayed_launch_range'][0]:,} – ${cost['delayed_launch_range'][1]:,}",
            ],
            [
                f"Manual rework ({cost['rework_hours']} hours/year)",
                f"${cost['rework_cost']:,}",
            ],
            [
                "Total Estimated Annual Cost",
                f"${cost['annual_estimate_low']:,} – ${cost['annual_estimate_high']:,}",
            ],
        ]
        cost_table = Table(cost_data, colWidths=[3.5 * inch, 2.5 * inch])
        cost_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTNAME", (0, 0), (-1, -1), SANS),
            ("FONTNAME", (0, 0), (-1, 0), SANS_BOLD),
            ("FONTNAME", (0, -1), (-1, -1), SANS_BOLD),
            ("BACKGROUND", (0, -1), (-1, -1), SG_SURFACE),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, RULE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, LIGHT_GRAY]),
        ]))
        elements.append(cost_table)

        # Show the assumptions behind the totals so the figures read as
        # adjustable inputs, not asserted facts.
        a = cost.get("assumptions")
        if a:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                "<b>Assumptions used</b> (adjust to your own retailer terms):",
                small_style,
            ))
            assumption_lines = [
                f"Chargeback per invalid item: ${int(a['chargeback_per_item_low']):,}"
                f"–${int(a['chargeback_per_item_high']):,}",
                f"Delayed launch per SKU (per month): "
                f"${int(a['delayed_launch_per_sku_low']):,}"
                f"–${int(a['delayed_launch_per_sku_high']):,}",
                f"Manual rework: ${int(a['rework_rate_per_hour']):,}/hour",
                f"Cost scaling at 2x SKUs: {a['growth_multiplier_low']:g}"
                f"–{a['growth_multiplier_high']:g}x (assumed, not sourced)",
            ]
            for line in assumption_lines:
                elements.append(Paragraph(
                    f"• {line}",
                    ParagraphStyle("AssumptionItem", parent=small_style, leftIndent=12),
                ))

        if cost.get("growth_note"):
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"<i>{cost['growth_note']}</i>", small_style))

    # --- Retailer Checklists ---
    retailer_checklists = validation_data["retailer_checklists"]
    total_gtins = validation_data["summary"]["total_gtins"]
    for idx, (retailer_name, checklist) in enumerate(retailer_checklists.items()):
        elements.append(PageBreak())
        if idx == 0:
            elements.append(Paragraph("Retailer Readiness Checklists", heading_style))
            elements.append(Spacer(1, 12))

        if checklist["ready"]:
            status = "ALL CHECKS PASSED"
        else:
            status = (
                f"{checklist['passed']} of {checklist['total']} GTIN validation checks passed "
                f"(across all {total_gtins} GTINs submitted)"
            )
        status_color = GREEN if checklist["ready"] else RED

        elements.append(Paragraph(
            f'<font color="{status_color.hexval()}">•</font> '
            f'<b>{retailer_name}</b>',
            ParagraphStyle("RetailerName", parent=body_style, fontSize=14, spaceBefore=12),
        ))
        elements.append(Paragraph(
            checklist["profile"]["description"],
            small_style,
        ))
        elements.append(Paragraph(
            f'<b>{status}</b>',
            ParagraphStyle("RetailerStatus", parent=body_style, fontSize=10,
                           textColor=status_color, spaceAfter=8),
        ))

        # List each check
        for check in checklist["checks"]:
            icon = "PASS" if check["passed"] else "FAIL"
            icon_color = GREEN if check["passed"] else RED
            elements.append(Paragraph(
                f'<font color="{icon_color.hexval()}">{icon}</font>  '
                f'{check_name(check)} — <i>{check["detail"]}</i>',
                ParagraphStyle("CheckItem", parent=body_style, fontSize=9, leftIndent=20),
            ))

        # Group failing GTINs by check (issue type)
        failed_checks = [c for c in checklist["checks"] if not c["passed"] and c.get("failing_gtins")]
        if failed_checks:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(
                '<b>Failing GTINs by Issue</b>',
                ParagraphStyle("FailingHeader", parent=body_style, fontSize=11, spaceBefore=8),
            ))

            for check in failed_checks:
                failing = check["failing_gtins"]
                if not failing:
                    continue

                # Try to keep the whole group together
                block = []
                block.append(Paragraph(
                    f'<font color="{RED.hexval()}">FAIL</font> <b>{check_name(check)}</b> — '
                    f'{len(failing)} GTIN(s)',
                    ParagraphStyle("FailGroup", parent=body_style, fontSize=10,
                                   spaceBefore=10, leftIndent=20),
                ))
                for row_num, raw_input in failing:
                    block.append(Paragraph(
                        f'Row {row_num}: {raw_input}',
                        ParagraphStyle("FailItem", parent=small_style, fontSize=8,
                                       leftIndent=40),
                    ))

                # Estimate height: header ~20pt + each row ~14pt
                est_height = 20 + len(failing) * 14
                if est_height <= PAGE_CONTENT_HEIGHT:
                    elements.append(KeepTogether(block))
                else:
                    # Too tall — chunk with continued headers
                    elements.append(block[0])  # header
                    running = 20
                    for j, item_para in enumerate(block[1:]):
                        if running + 14 > PAGE_CONTENT_HEIGHT and j > 0:
                            elements.append(PageBreak())
                            elements.append(Paragraph(
                                f'<font color="{RED.hexval()}">FAIL</font> '
                                f'<b>{check_name(check)} — continued</b>',
                                ParagraphStyle("FailGroupCont", parent=body_style,
                                               fontSize=10, spaceBefore=10, leftIndent=20),
                            ))
                            running = 20
                        elements.append(item_para)
                        running += 14

    # --- Item Detail ---
    elements.append(PageBreak())
    elements.append(Paragraph("Item-Level Detail", heading_style))
    elements.append(Paragraph(
        "Each GTIN analyzed, with issues and recommendations.",
        small_style,
    ))

    # Sort: critical first, then warnings, then clean
    sorted_results = sorted(
        results,
        key=lambda r: (
            0 if r.has_critical else (1 if r.has_warning else 2),
            r.row_number,
        ),
    )

    # Split results by severity
    critical_items = [r for r in sorted_results if r.has_critical]
    warning_items = [r for r in sorted_results if r.has_warning and not r.has_critical]
    info_items = [r for r in sorted_results if r.issues and not r.has_critical and not r.has_warning]

    def render_item_flowables(r, label_color, body_style, small_style):
        """Return a list of flowables for one row (NOT wrapped in KeepTogether)."""
        block = []
        block.append(Paragraph(
            f'<font color="{label_color.hexval()}">•</font> '
            f'Row {r.row_number}: <b>{r.raw_input}</b> '
            f'({r.gtin_type.value if r.gtin_type.value != "Unknown" else "Unknown format"})',
            ParagraphStyle("ItemHeader", parent=body_style, fontSize=10, spaceBefore=10),
        ))
        for issue in r.issues:
            block.append(Paragraph(
                f'<b>[{issue.severity.value}]</b> {issue.message}',
                ParagraphStyle("IssueMsg", parent=body_style, fontSize=9, leftIndent=20),
            ))
            block.append(Paragraph(
                f'<i>Fix: {issue.recommendation}</i>',
                ParagraphStyle("IssueFix", parent=small_style, leftIndent=20),
            ))
        return block

    def render_item_block(r, label_color, body_style, small_style):
        """Return a KeepTogether block for one row."""
        return KeepTogether(render_item_flowables(r, label_color, body_style, small_style))

    def estimate_item_height(r):
        """Rough estimate of how tall one item block will be in points."""
        # Header line ~18pt + each issue ~30pt (message + fix)
        return 18 + len(r.issues) * 30

    def render_item_group(group_label, items, label_color, body_style,
                          small_style, elements, recommendation_text=None):
        """
        Render a group of items with continuation support.
        Keeps header + all items together when they fit on one page;
        otherwise chunks into pages with 'continued' headers.
        """
        header_height = 40 if recommendation_text else 30

        def make_header(continued=False):
            suffix = " — continued" if continued else ""
            after = 4 if recommendation_text else 8
            parts = [Paragraph(
                f'<b>{group_label}{suffix}</b> — {len(items)} item(s)',
                ParagraphStyle("GroupHeader", parent=body_style, fontSize=11,
                               spaceBefore=16, spaceAfter=after, textColor=INK),
            )]
            if recommendation_text and not continued:
                parts.append(Paragraph(
                    f'<i>{recommendation_text}</i>',
                    ParagraphStyle("GroupRec", parent=small_style, leftIndent=20, spaceAfter=8),
                ))
            return parts

        item_heights = [estimate_item_height(r) for r in items]
        total_height = header_height + sum(item_heights)

        if total_height <= PAGE_CONTENT_HEIGHT:
            group_block = make_header(continued=False)
            for r in items:
                group_block.extend(render_item_flowables(r, label_color, body_style, small_style))
            elements.append(KeepTogether(group_block))
        else:
            elements.extend(make_header(continued=False))
            running_height = header_height
            for i, r in enumerate(items):
                h = item_heights[i]
                if running_height + h > PAGE_CONTENT_HEIGHT and i > 0:
                    elements.append(PageBreak())
                    elements.extend(make_header(continued=True))
                    running_height = header_height
                elements.append(render_item_block(r, label_color, body_style, small_style))
                running_height += h

    # --- Render severity sections ---
    CODE_LABELS = {
        "EMPTY": "Empty or Blank GTINs",
        "NON_NUMERIC": "Non-Numeric Characters in GTIN",
        "INVALID_LENGTH": "Invalid GTIN Length",
        "BAD_CHECK_DIGIT": "Incorrect Check Digit",
        "ALL_ZEROS": "Placeholder GTINs (All Zeros)",
        "DUPLICATE": "Duplicate GTINs",
        "PREFIX_MISMATCH": "Company Prefix Mismatch",
        "ORPHAN_CASE_GTIN": "Orphan Case GTINs (no matching unit)",
        "INDICATOR_NINE": "Variable Measure Indicator Digit",
        "UPC_NOT_GTIN13": "UPC-A Format (GTIN-13 may be required)",
        "NO_CASE_GTIN": "Missing Case-Level GTIN-14",
        "INDICATOR_ZERO": "GTIN-14 with Indicator 0 (base unit in 14-digit format)",
        "CASE_LEVEL": "Case/Inner Pack Level GTIN-14",
    }

    severity_sections = [
        (critical_items, Severity.CRITICAL, RED, "Critical Issues — These GTINs will be rejected", False),
        (warning_items, Severity.WARNING, YELLOW, "Warnings — These GTINs may cause problems", True),
        (info_items, Severity.INFO, INFO, "Info — Best practice notes", True),
    ]

    for section_items, severity, label_color, title, page_break in severity_sections:
        if not section_items:
            continue

        if page_break:
            elements.append(PageBreak())

        elements.append(Paragraph(
            f'<font color="{label_color.hexval()}">•</font> <b>{title}</b>',
            ParagraphStyle("SeverityHeader", parent=heading_style, fontSize=14),
        ))
        elements.append(Spacer(1, 8))

        def count_sev(r, sev=severity):
            return len([i for i in r.issues if i.severity == sev])

        single = [r for r in section_items if count_sev(r) == 1]
        multi = [r for r in section_items if count_sev(r) > 1]

        if single:
            groups = defaultdict(list)
            for r in single:
                issue = next((i for i in r.issues if i.severity == severity), r.issues[0])
                groups[issue.code].append(r)

            for code, items in groups.items():
                group_label = CODE_LABELS.get(code, code)
                sample_issue = next((i for i in items[0].issues if i.code == code), items[0].issues[0])
                render_item_group(
                    group_label, items, label_color, body_style,
                    small_style, elements, sample_issue.recommendation,
                )

        if multi:
            multi.sort(key=count_sev, reverse=True)
            multi_label = (
                "Items with Multiple Notes" if severity == Severity.INFO
                else f"Items with Multiple {severity.value}s"
            )
            render_item_group(
                multi_label, multi, label_color, body_style,
                small_style, elements,
            )

    # --- Clean items summary ---
    # Clean = no critical or warning issues (INFO advisories don't disqualify).
    clean_items = [r for r in results if not (r.has_critical or r.has_warning)]
    if clean_items:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            f"{len(clean_items)} GTIN(s) passed all checks with no errors or warnings.",
            ParagraphStyle("CleanSummary", parent=body_style, textColor=GREEN),
        ))

    # --- Footer ---
    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(
        width="100%", thickness=0.5, color=RULE,
        spaceAfter=10,
    ))
    elements.append(Paragraph(
        "This report was generated from sample data by the free GTIN Product "
        "Data Validator. Cost figures are directional and built from the "
        "editable assumptions shown above, not sourced industry data. To get "
        "this report for your own file, see lailarallc.com/kits/gtin-validator.",
        ParagraphStyle("Footer", parent=small_style, alignment=TA_CENTER),
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
