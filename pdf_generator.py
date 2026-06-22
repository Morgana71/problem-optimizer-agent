"""
pdf_generator.py

PDF 生成工具。
不依赖外部字体文件，使用 ReportLab 内置 CID 中文字体 STSong-Light。
生成效果偏“报告文档”，适合课程提交和演示。
"""

from __future__ import annotations

from io import BytesIO
from datetime import datetime
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


FONT_NAME = "STSong-Light"
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 22 * mm
RIGHT_MARGIN = 20 * mm
TOP_MARGIN = 20 * mm
BOTTOM_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


# 注册中文字体。ReportLab 内置 CID 字体，不需要额外上传字体文件。
pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))


def _clean_markdown_inline(text: str) -> str:
    """移除常见 Markdown 行内标记，保留可读文本。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text.strip()


def _wrap_text(text: str, font_name: str, font_size: int, max_width: float) -> list[str]:
    """按 PDF 宽度自动换行，兼容中文无空格文本。"""
    if not text:
        return [""]

    lines: list[str] = []
    current = ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        test = current + char
        if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def _draw_footer(c: canvas.Canvas, page_number: int) -> None:
    c.setFont(FONT_NAME, 9)
    c.drawCentredString(PAGE_WIDTH / 2, 10 * mm, f"第 {page_number} 页")


def markdown_to_pdf_bytes(markdown_text: str, title: str = "问题优化智能体求解报告") -> bytes:
    """将 Markdown 文本转换为 PDF bytes。"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_number = 1

    def new_page() -> None:
        nonlocal page_number, y
        _draw_footer(c, page_number)
        c.showPage()
        page_number += 1
        y = PAGE_HEIGHT - TOP_MARGIN

    def ensure_space(needed_height: float) -> None:
        if y - needed_height < BOTTOM_MARGIN:
            new_page()

    y = PAGE_HEIGHT - TOP_MARGIN

    # 封面 / 标题
    c.setFont(FONT_NAME, 22)
    title_lines = _wrap_text(title, FONT_NAME, 22, CONTENT_WIDTH)
    for line in title_lines:
        ensure_space(12 * mm)
        c.drawCentredString(PAGE_WIDTH / 2, y, line)
        y -= 12 * mm

    y -= 5 * mm
    c.setFont(FONT_NAME, 11)
    c.drawCentredString(PAGE_WIDTH / 2, y, f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 12 * mm

    # 正文
    in_code_block = False
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if not stripped:
            y -= 4 * mm
            if y < BOTTOM_MARGIN:
                new_page()
            continue

        # Markdown 标题处理
        header_level = 0
        header_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if header_match:
            header_level = len(header_match.group(1))
            text = _clean_markdown_inline(header_match.group(2))
            if header_level == 1:
                font_size = 18
                leading = 9 * mm
                y -= 2 * mm
            elif header_level == 2:
                font_size = 15
                leading = 8 * mm
                y -= 2 * mm
            else:
                font_size = 13
                leading = 7 * mm
        else:
            text = _clean_markdown_inline(stripped)
            font_size = 10 if in_code_block else 11
            leading = 6 * mm

        if stripped.startswith(("- ", "* ")):
            text = "• " + _clean_markdown_inline(stripped[2:])
        elif re.match(r"^\d+[\.、]\s*", stripped):
            text = _clean_markdown_inline(stripped)
        elif stripped.startswith(">"):
            text = "说明：" + _clean_markdown_inline(stripped.lstrip(">"))

        c.setFont(FONT_NAME, font_size)
        wrapped_lines = _wrap_text(text, FONT_NAME, font_size, CONTENT_WIDTH)
        ensure_space(max(leading * len(wrapped_lines), leading))
        for wrapped in wrapped_lines:
            c.drawString(LEFT_MARGIN, y, wrapped)
            y -= leading
        if header_level:
            y -= 1.5 * mm

    _draw_footer(c, page_number)
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def safe_filename_from_question(question: str, suffix: str = "pdf") -> str:
    """根据问题生成一个安全文件名。"""
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "_", question.strip())
    cleaned = cleaned[:30] or "问题优化报告"
    return f"问题优化报告_{cleaned}.{suffix}"
