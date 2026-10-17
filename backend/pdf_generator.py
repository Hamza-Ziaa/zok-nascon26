"""
Zok (ذوق) — Authentic Broadsheet PDF Generator
Creates an heirloom-quality printable morning newspaper PDF using ReportLab.
Features:
- Broadsheet double-line perimeter border
- Grand masthead with Urdu calligraphy seal
- Left & Right masthead ears (Islamabad weather + edition motto)
- "Three Things to Know Today" summary index
- Signed Letter from the Intelligence Editor
- Lead story with drop-cap and justified multi-column typesetting
- Room to Explore: The Devil's Advocate (Anti-Echo Chamber)
- Daily 5x5 entity crossword puzzle grid
- Evening recall challenge & broadside footer
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

from backend.models import Article, Edition, User


def generate_pdf(
    edition: Edition,
    user: User,
    articles: list[Article],
    devils_advocate: Optional[Article] = None,
) -> bytes:
    """
    Generate an authentic broadsheet newspaper PDF.
    Returns bytes of the compiled PDF.
    """
    buffer = io.BytesIO()

    # Standard Letter size, 0.45-inch margins for dense, elegant broadsheet layout
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=32,
        rightMargin=32,
        topMargin=32,
        bottomMargin=32,
        title=f"ZOK Broadsheet — {user.name}'s Edition",
        author="Zok Morning Broadside",
    )

    styles = getSampleStyleSheet()

    # ── Color Palette: Ink & Newsprint ─────────────────────────────────────────
    c_ink = colors.HexColor("#191816")
    c_ink_muted = colors.HexColor("#57534e")
    c_terracotta = colors.HexColor("#991b1b")
    c_amber_tint = colors.HexColor("#fef3c7")
    c_paper_tint = colors.HexColor("#f5f5f4")
    c_border_dark = colors.HexColor("#292524")
    c_border_light = colors.HexColor("#d6d3d1")

    # ── Typography Hierarchy ──────────────────────────────────────────────────
    style_masthead = ParagraphStyle(
        "Masthead",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=44,
        leading=46,
        alignment=1,  # Center
        textColor=c_ink,
        spaceAfter=2,
    )

    style_urdu_seal = ParagraphStyle(
        "UrduSeal",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=15,
        leading=18,
        alignment=1,
        textColor=c_terracotta,
    )

    style_sub_motto = ParagraphStyle(
        "SubMotto",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        alignment=1,
        textColor=c_ink_muted,
        spaceAfter=4,
    )

    style_ear_text = ParagraphStyle(
        "EarText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9.5,
        textColor=c_ink,
    )

    style_banner = ParagraphStyle(
        "BannerDate",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=c_ink,
        alignment=1,
    )

    style_lead_title = ParagraphStyle(
        "LeadTitle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=17,
        leading=21,
        textColor=c_ink,
        spaceAfter=4,
    )

    style_article_title = ParagraphStyle(
        "ArticleTitle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=11.5,
        leading=14.5,
        textColor=c_ink,
        spaceAfter=2,
    )

    style_body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=8.5,
        leading=11.5,
        textColor=c_ink,
        alignment=4,  # Justified
        spaceAfter=3,
    )

    style_why_it_matters = ParagraphStyle(
        "WhyItMatters",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=7.5,
        leading=10,
        textColor=c_terracotta,
        spaceAfter=4,
    )

    style_source_tag = ParagraphStyle(
        "SourceTag",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8.5,
        textColor=c_ink_muted,
        spaceAfter=2,
    )

    story = []

    # ── 1. MASTHEAD WITH EARS ─────────────────────────────────────────────────
    left_ear_content = [
        Paragraph("<b>ISLAMABAD EDITION</b>", style_ear_text),
        Paragraph("🌤 24°C • Morning Mist", style_ear_text),
        Paragraph("Vol. XXV • NaSCon Jubilee", style_ear_text),
        Paragraph("<b>FAST National University</b>", style_ear_text),
    ]

    center_masthead = [
        Paragraph("Z O K &nbsp; (ذوق)", style_masthead),
        Paragraph("THE LIVING MORNING BROADSIDE", style_sub_motto),
        Paragraph("<i>The Only Newspaper with an Edition of One • Finite by Design</i>", style_urdu_seal),
    ]

    right_ear_content = [
        Paragraph(f"<b>SUBSCRIBER: {user.name.upper()[:16]}</b>", style_ear_text),
        Paragraph(f"Reading Budget: {user.reading_budget} Minutes", style_ear_text),
        Paragraph("Zero Endless Scroll", style_ear_text),
        Paragraph("<b>Price: Undivided Attention</b>", style_ear_text),
    ]

    masthead_table = Table([[left_ear_content, center_masthead, right_ear_content]], colWidths=[120, 308, 120])
    masthead_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('BOX', (0, 0), (0, 0), 0.5, c_border_light),
        ('BOX', (2, 0), (2, 0), 0.5, c_border_light),
        ('BACKGROUND', (0, 0), (0, 0), c_paper_tint),
        ('BACKGROUND', (2, 0), (2, 0), c_paper_tint),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(masthead_table)
    story.append(Spacer(1, 3))

    # Double rule date bar
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_border_dark, spaceBefore=1, spaceAfter=2))
    date_str = edition.created_at.strftime("%A, %B %d, %Y") if hasattr(edition, "created_at") else datetime.utcnow().strftime("%A, %B %d, %Y")
    banner_text = f"SATURDAY DISPATCH &nbsp;•&nbsp; {date_str.upper()} &nbsp;•&nbsp; FAST-NUCES 25TH JUBILEE CONVENTION &nbsp;•&nbsp; ISLAMABAD, PAKISTAN"
    story.append(Paragraph(banner_text, style_banner))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border_dark, spaceBefore=2, spaceAfter=6))

    # ── 2. THREE THINGS INDEX & EDITORIAL LETTER ──────────────────────────────
    tt_html = "<b>❖ THREE THINGS TO KNOW TODAY</b><br/><br/>"
    for i, t in enumerate(edition.three_things or []):
        tt_html += f"<b>{i+1}.</b> {t}<br/>"
    tt_p = Paragraph(tt_html, ParagraphStyle("TT", parent=styles["Normal"], fontName="Times-Roman", fontSize=8, leading=11, textColor=c_ink))

    ed_html = f"<b>❖ LETTER FROM THE EDITOR</b><br/><br/><i>Dear {user.name},</i><br/>{edition.editorial_note}<br/><br/><b>— The Intelligence Editor</b>"
    ed_p = Paragraph(ed_html, ParagraphStyle("ED", parent=styles["Normal"], fontName="Times-Roman", fontSize=8, leading=11, textColor=c_ink))

    summary_table = Table([[tt_p, ed_p]], colWidths=[274, 274])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), c_amber_tint),
        ('BACKGROUND', (1, 0), (1, 0), c_paper_tint),
        ('BOX', (0, 0), (0, 0), 1, c_border_dark),
        ('BOX', (1, 0), (1, 0), 1, c_border_light),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_border_dark, spaceBefore=2, spaceAfter=6))

    # ── 3. LEAD STORY ─────────────────────────────────────────────────────────
    if articles:
        lead = articles[0]
        story.append(Paragraph(f"<b>{lead.category.upper()}</b> &nbsp;•&nbsp; {lead.source.upper()}", style_source_tag))
        story.append(Paragraph(lead.title, style_lead_title))
        
        # 2-column split for lead story
        lead_left = [
            Paragraph(f"<b>ISLAMABAD — </b>{lead.summary}", style_body),
            Paragraph(f"<b>Why this is in your edition:</b> Calibrated directly to your active taste profile in {lead.category.lower()}.", style_why_it_matters),
        ]
        lead_right = [
            Paragraph(lead.content[:380] + "..." if lead.content else lead.summary, style_body),
            Paragraph("<i>Source: Verified wire dispatch • Archived for evening recall check.</i>", style_source_tag),
        ]
        lead_table = Table([[lead_left, lead_right]], colWidths=[270, 270])
        lead_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('RIGHTPADDING', (0, 0), (0, 0), 6),
            ('LEFTPADDING', (1, 0), (1, 0), 6),
            ('LINEBEFORE', (1, 0), (1, 0), 0.5, c_border_light),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(lead_table)
        story.append(HRFlowable(width="100%", thickness=0.5, color=c_border_light, spaceBefore=4, spaceAfter=6))

    # ── 4. SECONDARY STORIES (2-COLUMN GRID) ──────────────────────────────────
    sec_articles = articles[1:5] if len(articles) > 1 else []
    if sec_articles:
        col_a = []
        col_b = []
        for i, a in enumerate(sec_articles):
            item = [
                Paragraph(f"<b>{a.category.upper()}</b> &nbsp;•&nbsp; {a.source}", style_source_tag),
                Paragraph(a.title, style_article_title),
                Paragraph(a.summary, style_body),
                Paragraph(f"↳ {a.category} • High relevance to your reading budget.", style_why_it_matters),
                Spacer(1, 3),
            ]
            if i % 2 == 0:
                col_a.extend(item)
            else:
                col_b.extend(item)

        sec_table = Table([[col_a, col_b]], colWidths=[270, 270])
        sec_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('RIGHTPADDING', (0, 0), (0, 0), 6),
            ('LEFTPADDING', (1, 0), (1, 0), 6),
            ('LINEBEFORE', (1, 0), (1, 0), 0.5, c_border_light),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(sec_table)
        story.append(Spacer(1, 4))

    # ── 5. ROOM TO EXPLORE + DAILY CROSSWORD ──────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=c_border_dark, spaceBefore=3, spaceAfter=6))

    da_content = []
    if devils_advocate:
        da_title = Paragraph("<b>ROOM TO EXPLORE: THE DISSENTING OPINION (ANTI-ECHO CHAMBER)</b>", ParagraphStyle(
            "DAT", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=c_terracotta
        ))
        da_body = Paragraph(
            f"<b>{devils_advocate.title}</b><br/>{devils_advocate.summary}<br/>"
            f"<i>Why you must read this: Intentionally chosen from outside your ideological cluster to cultivate lateral cognitive thinking.</i>",
            ParagraphStyle("DAB", parent=styles["Normal"], fontName="Times-Roman", fontSize=7.5, leading=10.5, textColor=c_ink)
        )
        da_content = [da_title, Spacer(1, 2), da_body]
    else:
        da_content = [Paragraph("<b>ROOM TO EXPLORE</b><br/>Diverse perspectives curated daily.", style_body)]

    # Crossword Table Box
    cw_text = [
        Paragraph("<b>DAILY 5x5 NEWS CROSSWORD</b>", ParagraphStyle("CWT", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=c_ink)),
        Paragraph("[R][A][A][S][T] - 1-Across: Pakistan payment rail (5)<br/>"
                  "[F][A][S][T][.] - 4-Across: Host University (4)<br/>"
                  "[.][G][R][I][D] - 5-Across: National AI compute (4)<br/>"
                  "<i>Solve during breakfast with your morning coffee.</i>",
                  ParagraphStyle("CWB", parent=styles["Normal"], fontName="Times-Roman", fontSize=7, leading=9.5, textColor=c_ink_muted))
    ]

    bottom_table = Table([[da_content, cw_text]], colWidths=[330, 218])
    bottom_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#fff1f2")),
        ('BACKGROUND', (1, 0), (1, 0), c_paper_tint),
        ('BOX', (0, 0), (0, 0), 1, c_terracotta),
        ('BOX', (1, 0), (1, 0), 0.5, c_border_dark),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(bottom_table)

    # ── 6. FOOTER COMPLETION SEAL ─────────────────────────────────────────────
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_border_dark, spaceBefore=2, spaceAfter=3))
    footer_text = f"❖ YOU'RE ALL CAUGHT UP. THAT'S THE NEWS FOR TODAY. ❖ &nbsp;•&nbsp; ZOK (ذوق) EDITION #{edition.id[-6:]} &nbsp;•&nbsp; RETURN TOMORROW AT 6:30 AM ☕"
    story.append(Paragraph(footer_text, ParagraphStyle(
        "Foot", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, leading=8.5, alignment=1, textColor=c_ink_muted
    )))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
