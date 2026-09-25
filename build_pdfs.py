"""Build the two PDFs from their markdown, with the figures drawn as vectors.

    python build_pdfs.py          # writes cheaper-per-token/article.pdf and quality-before-cost/case-study.pdf

Handles the markdown these two files use: headings, paragraphs, bullet lists, block quotes, tables,
fenced code, images from figures/, and inline bold, italic, code and links. Relative links become
links to the file on GitHub. Output is byte-for-byte reproducible (reportlab's invariant mode).
On Windows the text uses Segoe UI; elsewhere it falls back to Helvetica, which lacks a few symbols.
"""
import os
import re
import sys

from reportlab import rl_config

rl_config.invariant = 1

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, KeepTogether, ListFlowable, ListItem, Paragraph,
                                Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "cheaper-per-token"))
import figures  # noqa: E402  registers the Sans fonts and draws the figures

REPO_URL = "https://github.com/MohanVishe/product-case-studies/blob/main"
DOCS = [("cheaper-per-token/article.md", "cheaper-per-token/article.pdf"),
        ("quality-before-cost/case-study.md", "quality-before-cost/case-study.pdf")]


def _font(name, file, fallback):
    try:
        pdfmetrics.registerFont(TTFont(name, f"C:/Windows/Fonts/{file}.ttf"))
        return name
    except Exception:
        return fallback


ITALIC = _font("Sans-I", "segoeuii", "Helvetica-Oblique")
BOLD_ITALIC = _font("Sans-BI", "segoeuiz", "Helvetica-BoldOblique")
MONO = _font("Mono", "consola", "Courier")
if ITALIC == "Sans-I":
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-B", italic="Sans-I", boldItalic="Sans-BI")
BODY = "Sans" if ITALIC == "Sans-I" else "Helvetica"
BOLD = "Sans-B" if ITALIC == "Sans-I" else "Helvetica-Bold"

INK, MUTED, LINE, PANEL = (colors.HexColor(c) for c in ("#1f2328", "#656d76", "#d0d7de", "#f6f8fa"))
LINK = colors.HexColor("#1f5fa8")
ST = {
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=20, leading=25, textColor=INK, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=14.5, leading=19, textColor=INK, spaceBefore=14, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName=BOLD, fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4),
    "p": ParagraphStyle("p", fontName=BODY, fontSize=10, leading=14.5, textColor=INK, spaceAfter=7, alignment=TA_LEFT),
    "quote": ParagraphStyle("quote", fontName=BODY, fontSize=10, leading=14.5, textColor=INK, leftIndent=12,
                            borderPadding=(6, 8, 6, 8), backColor=PANEL, spaceBefore=4, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName=BODY, fontSize=8.8, leading=11.5, textColor=INK),
    "code": ParagraphStyle("code", fontName=MONO, fontSize=8.8, leading=11.5, textColor=INK, backColor=PANEL,
                           borderPadding=6, leftIndent=6, spaceBefore=4, spaceAfter=10),
}


def inline(text, base_dir):
    """Markdown inline markup to reportlab's paragraph markup."""
    codes = []

    def keep_code(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    t = re.sub(r"`([^`]+)`", keep_code, text)
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def link(m):
        label, url = m.group(1), m.group(2)
        if not re.match(r"[a-z]+://", url) and not url.startswith("#"):
            url = f"{REPO_URL}/{os.path.normpath(os.path.join(base_dir, url)).replace(os.sep, '/')}"
        return f'<a href="{url}" color="#1f5fa8">{label}</a>'

    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    for i, c in enumerate(codes):
        c = c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        t = t.replace(f"\x00{i}\x00", f'<font face="{MONO}" size="9">{c}</font>')
    return t


def figure(src, width):
    name = os.path.splitext(os.path.basename(src))[0]
    d = figures.build(name)
    k = width / d.width
    d.scale(k, k)
    d.width, d.height = d.width * k, d.height * k
    return KeepTogether([Spacer(1, 4), d, Spacer(1, 8)])


def table(rows, base_dir, width):
    cells = [[Paragraph(inline(c.strip(), base_dir), ST["cell"]) for c in r] for r in rows]
    n = len(rows[0])
    t = Table(cells, colWidths=[width / n] * n if n > 2 else [width * 0.42, width * 0.58], repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [t, Spacer(1, 8)]


def flow(md, base_dir, width):
    out, lines, i = [], md.replace("\r\n", "\n").split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            out.append(Preformatted("\n".join(lines[i + 1:j]), ST["code"]))
            i = j + 1
        elif m := re.match(r"(#{1,3}) (.*)", ln):
            out.append(Paragraph(inline(m.group(2), base_dir), ST[f"h{len(m.group(1))}"]))
            i += 1
        elif ln.strip() == "---":
            out.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceBefore=6, spaceAfter=10))
            i += 1
        elif m := re.match(r"!\[[^\]]*\]\(([^)]+)\)", ln):
            out.append(figure(m.group(1), width))
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = lines[i].strip().strip("|").split("|")
                if not all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells):
                    rows.append(cells)
                i += 1
            if all(not c.strip() for c in rows[0]):          # header-less "| | |" tables
                rows = rows[1:]
            out += table(rows, base_dir, width)
        elif ln.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            out.append(Paragraph(inline(" ".join(buf), base_dir), ST["quote"]))
        elif re.match(r"- ", ln):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or (lines[i].startswith("  ") and items)):
                if lines[i].startswith("- "):
                    items.append(lines[i][2:].strip())
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append(ListFlowable([ListItem(Paragraph(inline(t, base_dir), ST["p"]), leftIndent=12)
                                     for t in items], bulletType="bullet", start="•", leftIndent=12,
                                    bulletFontName=BODY, bulletFontSize=9))
        else:
            buf = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(#{1,3} |```|\||> |- |!\[|---$)", lines[i]):
                buf.append(lines[i].strip())
                i += 1
            out.append(Paragraph(inline(" ".join(buf), base_dir), ST["p"]))
    return out


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(BODY, 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 12 * mm, doc.title)
    canvas.drawRightString(A4[0] - doc.rightMargin, 12 * mm, str(doc.page))
    canvas.restoreState()


def build(src, dst):
    md = open(os.path.join(HERE, src), encoding="utf-8").read()
    title = re.search(r"^# (.+)$", md, re.M).group(1)
    doc = SimpleDocTemplate(os.path.join(HERE, dst), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm, title=title,
                            author="Mohan Prakash Vishe", subject="AI engineering")
    doc.build(flow(md, os.path.dirname(src), doc.width), onFirstPage=footer, onLaterPages=footer)
    print("wrote", dst)


if __name__ == "__main__":
    for src, dst in DOCS:
        build(src, dst)
