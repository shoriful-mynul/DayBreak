from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
)


def configure_fonts():
    windows_fonts = (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    )

    candidates = [
        (
            windows_fonts / "times.ttf",
            windows_fonts / "timesbd.ttf",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
        ),
    ]

    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            if "DaybreakBody" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(
                    TTFont("DaybreakBody", str(regular))
                )
                pdfmetrics.registerFont(
                    TTFont("DaybreakBold", str(bold))
                )

            return "DaybreakBody", "DaybreakBold"

    return "Times-Roman", "Times-Bold"


BODY_FONT, BOLD_FONT = configure_fonts()


def pdf_text(value):
    text = str(value or "")

    # Built-in Times fonts have a smaller character set.
    if BODY_FONT == "Times-Roman":
        text = text.encode(
            "cp1252", errors="replace"
        ).decode("cp1252")

    # Prevent article text from being interpreted as PDF markup.
    return escape(text)


def create_newspaper_pdf(paper):
    output = BytesIO()

    page_width, page_height = A4

    margin = 36
    gutter = 22
    bottom = 42
    frame_top = page_height - 132

    column_width = (
        page_width - 2 * margin - gutter
    ) / 2

    frame_height = frame_top - bottom

    document = BaseDocTemplate(
        output,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=132,
        bottomMargin=bottom,
        title="Daybreak — Personal Morning Paper",
        author="Daybreak",
    )

    frames = [
        Frame(
            margin,
            bottom,
            column_width,
            frame_height,
            id="left",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        ),
        Frame(
            margin + column_width + gutter,
            bottom,
            column_width,
            frame_height,
            id="right",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        ),
    ]

    created = datetime.fromisoformat(
        paper["created_at"].replace("Z", "+00:00")
    )

    date_label = created.strftime("%d %B %Y")
    time_label = created.strftime("%H:%M UTC")

    topics = paper.get("preferences", {}).get("topics", [])
    topic_label = " / ".join(topics).upper() or "PERSONAL EDITION"

    def draw_page(canvas, doc):
        canvas.saveState()

        canvas.setStrokeColor(colors.HexColor("#242424"))
        canvas.setLineWidth(2)
        canvas.line(
            margin,
            page_height - 30,
            page_width - margin,
            page_height - 30,
        )

        canvas.setFont(BOLD_FONT, 36)
        canvas.drawCentredString(
            page_width / 2,
            page_height - 71,
            "DAYBREAK",
        )

        canvas.setFont(BODY_FONT, 9)
        canvas.drawCentredString(
            page_width / 2,
            page_height - 89,
            f"{date_label} | {time_label} | Your morning, in focus.",
        )

        canvas.setFont(BODY_FONT, 8)
        canvas.drawCentredString(
            page_width / 2,
            page_height - 105,
            topic_label,
        )

        canvas.setLineWidth(0.6)
        canvas.line(
            margin,
            page_height - 116,
            page_width - margin,
            page_height - 116,
        )

        canvas.setStrokeColor(colors.HexColor("#d1cabd"))
        canvas.line(
            page_width / 2,
            bottom,
            page_width / 2,
            frame_top,
        )

        canvas.setFont(BODY_FONT, 8)
        canvas.setFillColor(colors.HexColor("#625e56"))

        canvas.drawString(
            margin,
            24,
            f"Edition {paper['edition_id'][:8]} | Publisher feed excerpts",
        )

        canvas.drawRightString(
            page_width - margin,
            24,
            f"Page {doc.page}",
        )

        canvas.restoreState()

    document.addPageTemplates(
        [
            PageTemplate(
                id="newspaper",
                frames=frames,
                onPage=draw_page,
            )
        ]
    )

    body_style = ParagraphStyle(
        "NewsBody",
        fontName=BODY_FONT,
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=9,
        splitLongWords=True,
    )

    headline_style = ParagraphStyle(
        "NewsHeadline",
        fontName=BOLD_FONT,
        fontSize=17,
        leading=20,
        spaceAfter=8,
        keepWithNext=True,
    )

    lead_style = ParagraphStyle(
        "LeadHeadline",
        parent=headline_style,
        fontSize=21,
        leading=24,
    )

    meta_style = ParagraphStyle(
        "NewsMeta",
        fontName=BODY_FONT,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#625e56"),
        spaceAfter=7,
        keepWithNext=True,
    )

    reason_style = ParagraphStyle(
        "NewsReason",
        parent=body_style,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#625e56"),
    )

    link_style = ParagraphStyle(
        "NewsLink",
        parent=body_style,
        fontSize=9,
        leading=12,
    )

    flowables = []

    for index, article in enumerate(paper["articles"]):
        label = (
            "LEAD STORY"
            if index == 0
            else article["topic"].upper()
        )

        flowables.append(
            Paragraph(
                pdf_text(f"{label} | {article['source']}"),
                meta_style,
            )
        )

        flowables.append(
            Paragraph(
                pdf_text(article["title"]),
                lead_style if index == 0 else headline_style,
            )
        )

        flowables.append(
            Paragraph(
                pdf_text(
                    article.get("excerpt")
                    or "No excerpt supplied by the publisher."
                ),
                body_style,
            )
        )

        flowables.append(
            Paragraph(
                pdf_text(
                    "Why this story? "
                    + article.get("selection_reason", "")
                ),
                reason_style,
            )
        )

        safe_link = escape(article["url"], quote=True)

        flowables.append(
            Paragraph(
                f'<link href="{safe_link}" color="#702b35">'
                f'Read original at {pdf_text(article["source"])}'
                "</link>",
                link_style,
            )
        )

        flowables.append(
            Spacer(1, 8)
        )

        flowables.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#bdb7aa"),
            )
        )

        flowables.append(
            Spacer(1, 14)
        )

    document.build(flowables)

    return output.getvalue()