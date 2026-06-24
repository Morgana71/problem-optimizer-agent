"""
pdf_generator.py

PDF 生成工具。
使用 ReportLab 的文档流布局生成更接近正式报告的中文 PDF：
- 自动提取报告标题
- 支持 Markdown 标题、段落、列表、引用和简单表格
- 使用更稳定的页眉页脚、段落间距和表格样式
"""

from __future__ import annotations

from io import BytesIO
from datetime import datetime
import html
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


FONT_NAME = "STSong-Light"
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 22 * mm
RIGHT_MARGIN = 20 * mm
TOP_MARGIN = 22 * mm
BOTTOM_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))


def _clean_markdown_inline(text: str) -> str:
    """移除/转换常见 Markdown 行内标记，输出 ReportLab Paragraph 可用文本。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = html.escape(text, quote=False)
    text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    return text.strip()


def extract_report_title(markdown_text: str, fallback: str = "软件需求工程分析报告") -> str:
    """从 Markdown 正文中提取正式标题。"""
    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        header_match = re.match(r"^#\s+(.+)$", stripped)
        if header_match:
            return _plain_text(header_match.group(1))[:60] or fallback
        if stripped.startswith(">"):
            continue
        if len(stripped) <= 60 and any(word in stripped for word in ["需求", "报告", "说明书", "文档"]):
            return _plain_text(stripped)[:60] or fallback
    return fallback


def _plain_text(text: str) -> str:
    text = re.sub(r"[#>*`]", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _safe_filename(text: str) -> str:
    cleaned = _plain_text(text)
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "_", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned[:42] or "软件需求工程分析报告"


def safe_filename_from_report(markdown_text: str, suffix: str = "pdf") -> str:
    """根据报告标题生成稳定、正式的文件名。"""
    title = extract_report_title(markdown_text)
    return f"{_safe_filename(title)}.{suffix}"


def safe_filename_from_question(question: str, suffix: str = "pdf") -> str:
    """兼容旧调用：根据问题生成一个安全文件名。"""
    cleaned = _safe_filename(question)
    if not any(word in cleaned for word in ["需求", "报告", "说明书", "文档"]):
        cleaned = f"软件需求工程分析报告_{cleaned}"
    return f"{cleaned[:48]}.{suffix}"


def _build_styles() -> dict[str, ParagraphStyle]:
    getSampleStyleSheet()
    base = ParagraphStyle(
        "BaseChinese",
        fontName=FONT_NAME,
        fontSize=10.8,
        leading=18,
        textColor=colors.HexColor("#2f3340"),
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    return {
        "title": ParagraphStyle(
            "TitleChinese",
            parent=base,
            fontSize=22,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1f2430"),
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleChinese",
            parent=base,
            fontSize=10,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6f7480"),
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "Heading1Chinese",
            parent=base,
            fontSize=17,
            leading=24,
            textColor=colors.HexColor("#1f2430"),
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "Heading2Chinese",
            parent=base,
            fontSize=14,
            leading=21,
            textColor=colors.HexColor("#2b3040"),
            spaceBefore=9,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "Heading3Chinese",
            parent=base,
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#343a48"),
            spaceBefore=7,
            spaceAfter=4,
        ),
        "body": base,
        "quote": ParagraphStyle(
            "QuoteChinese",
            parent=base,
            leftIndent=8 * mm,
            rightIndent=4 * mm,
            textColor=colors.HexColor("#666b76"),
            borderColor=colors.HexColor("#d9dce3"),
            borderWidth=0,
            borderPadding=5,
            backColor=colors.HexColor("#f7f8fa"),
            spaceBefore=4,
            spaceAfter=8,
        ),
        "small": ParagraphStyle(
            "SmallChinese",
            parent=base,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#6f7480"),
        ),
        "table": ParagraphStyle(
            "TableChinese",
            parent=base,
            fontSize=8.8,
            leading=12,
            wordWrap="CJK",
        ),
        "list": ParagraphStyle(
            "ListChinese",
            parent=base,
            leftIndent=4 * mm,
            firstLineIndent=0,
        ),
    }


def _is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _is_table_line(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|") and line.count("|") >= 2


def _flush_paragraph(buffer: list[str], story: list, styles: dict[str, ParagraphStyle]) -> None:
    if not buffer:
        return
    text = " ".join(part.strip() for part in buffer if part.strip())
    if text:
        story.append(Paragraph(_clean_markdown_inline(text), styles["body"]))
    buffer.clear()


def _table_from_lines(lines: list[str], styles: dict[str, ParagraphStyle]) -> Table | None:
    rows: list[list[str]] = []
    for line in lines:
        if _is_table_separator(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells:
            rows.append(cells)
    if not rows:
        return None

    col_count = max(len(row) for row in rows)
    normalized_rows = []
    for row in rows:
        padded = row + [""] * (col_count - len(row))
        normalized_rows.append([Paragraph(_clean_markdown_inline(cell), styles["table"]) for cell in padded])

    col_width = CONTENT_WIDTH / col_count
    table = Table(normalized_rows, colWidths=[col_width] * col_count, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2430")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7dbe3")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7ccd6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfcfe")]),
            ]
        )
    )
    return table


def _markdown_to_story(markdown_text: str, styles: dict[str, ParagraphStyle]) -> list:
    story: list = []
    paragraph_buffer: list[str] = []
    bullet_items: list[ListItem] = []
    table_lines: list[str] = []
    in_code_block = False

    def flush_bullets() -> None:
        nonlocal bullet_items
        if bullet_items:
            story.append(ListFlowable(bullet_items, bulletType="bullet", leftIndent=14, bulletFontName=FONT_NAME))
            bullet_items = []

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            table = _table_from_lines(table_lines, styles)
            if table is not None:
                story.append(table)
                story.append(Spacer(1, 6))
            table_lines = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if not stripped:
            flush_table()
            flush_bullets()
            _flush_paragraph(paragraph_buffer, story, styles)
            story.append(Spacer(1, 4))
            continue

        if _is_table_line(stripped):
            flush_bullets()
            _flush_paragraph(paragraph_buffer, story, styles)
            table_lines.append(stripped)
            continue
        flush_table()

        header_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if header_match:
            flush_bullets()
            _flush_paragraph(paragraph_buffer, story, styles)
            level = len(header_match.group(1))
            text = _clean_markdown_inline(header_match.group(2))
            style = styles["h1"] if level == 1 else styles["h2"] if level == 2 else styles["h3"]
            story.append(Paragraph(text, style))
            continue

        if stripped.startswith(("---", "***")) and len(stripped) <= 6:
            flush_bullets()
            _flush_paragraph(paragraph_buffer, story, styles)
            story.append(Spacer(1, 4))
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet_match:
            _flush_paragraph(paragraph_buffer, story, styles)
            bullet_items.append(ListItem(Paragraph(_clean_markdown_inline(bullet_match.group(1)), styles["list"])))
            continue

        numbered_match = re.match(r"^\d+[\.、]\s+(.+)$", stripped)
        if numbered_match:
            flush_bullets()
            _flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(_clean_markdown_inline(stripped), styles["body"]))
            continue

        if stripped.startswith(">"):
            flush_bullets()
            _flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(_clean_markdown_inline(stripped.lstrip("> ")), styles["quote"]))
            continue

        if in_code_block:
            flush_bullets()
            _flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(_clean_markdown_inline(stripped), styles["quote"]))
            continue

        paragraph_buffer.append(stripped)

    flush_table()
    flush_bullets()
    _flush_paragraph(paragraph_buffer, story, styles)
    return story


class NumberedCanvasDocTemplate(BaseDocTemplate):
    """带页脚的 ReportLab 文档模板。"""


def _draw_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 8.5)
    canvas.setFillColor(colors.HexColor("#8a8f99"))
    canvas.drawCentredString(PAGE_WIDTH / 2, 10 * mm, f"第 {doc.page} 页")
    canvas.setStrokeColor(colors.HexColor("#e3e6ec"))
    canvas.line(LEFT_MARGIN, 15 * mm, PAGE_WIDTH - RIGHT_MARGIN, 15 * mm)
    canvas.restoreState()


def markdown_to_pdf_bytes(markdown_text: str, title: str | None = None) -> bytes:
    """将 Markdown 文本转换为排版更正式的 PDF bytes。"""
    styles = _build_styles()
    report_title = title or extract_report_title(markdown_text)
    buffer = BytesIO()
    doc = NumberedCanvasDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=report_title,
        author="软件需求工程分析智能体",
    )
    frame = Frame(LEFT_MARGIN, BOTTOM_MARGIN, CONTENT_WIDTH, PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_draw_page)])

    story = [
        Spacer(1, 20 * mm),
        Paragraph(_clean_markdown_inline(report_title), styles["title"]),
        Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["subtitle"]),
        Spacer(1, 8 * mm),
        Paragraph("本报告由软件需求工程分析智能体根据对话内容自动生成。", styles["quote"]),
        PageBreak(),
    ]
    story.extend(_markdown_to_story(markdown_text, styles))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
