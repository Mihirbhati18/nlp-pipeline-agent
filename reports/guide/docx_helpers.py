"""Small helpers for building the guide documents with python-docx."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BLUE = RGBColor(0x1D, 0x4E, 0xD8)
INK = RGBColor(0x1E, 0x29, 0x3B)
GREY = RGBColor(0x47, 0x55, 0x69)
CONTENT_WIDTH = Cm(16.6)


def _shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    props.append(shd)


class Builder:
    """A thin wrapper so guide scripts read as content, not formatting."""

    def __init__(self) -> None:
        self.doc = Document()
        for section in self.doc.sections:
            section.top_margin = section.bottom_margin = Cm(2)
            section.left_margin = section.right_margin = Cm(2.2)
        normal = self.doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)
        normal.paragraph_format.space_after = Pt(6)
        for name, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12)):
            style = self.doc.styles[name]
            style.font.name = "Calibri"
            style.font.size = Pt(size)
            style.font.color.rgb = INK if name == "Heading 3" else BLUE

    # -- text --------------------------------------------------------------

    @staticmethod
    def runs(paragraph, text: str, size: float | None = None, colour=None):
        """Add text with **bold** and `code` markup."""
        for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
            if not part:
                continue
            if part.startswith("**"):
                run = paragraph.add_run(part[2:-2])
                run.bold = True
                if size:
                    run.font.size = Pt(size)
            elif part.startswith("`"):
                run = paragraph.add_run(part[1:-1])
                run.font.name = "Consolas"
                run.font.size = Pt((size or 11) - 1)
            else:
                run = paragraph.add_run(part)
                if size:
                    run.font.size = Pt(size)
            if colour is not None:
                run.font.color.rgb = colour
        return paragraph

    def p(self, text: str = "", size: float | None = None, colour=None, center: bool = False):
        para = self.doc.add_paragraph()
        self.runs(para, text, size, colour)
        if center:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return para

    def h(self, text: str, level: int = 1):
        return self.doc.add_heading(text, level=level)

    def bullets(self, items, style: str = "List Bullet"):
        for item in items:
            self.runs(self.doc.add_paragraph(style=style), item)

    def numbered(self, items):
        self.bullets(items, style="List Number")

    def checklist(self, items):
        for item in items:
            self.runs(self.doc.add_paragraph(style="List Bullet"), "☐  " + item)

    # -- blocks ------------------------------------------------------------

    def table(self, header, rows, widths_cm, font: float = 9.5, bold_first_col: bool = False):
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, text in enumerate(header):
            cell = t.rows[0].cells[i]
            cell.text = ""
            self.runs(cell.paragraphs[0], f"**{text}**", font)
            _shade(cell, "DBEAFE")
        for row in rows:
            cells = t.add_row().cells
            for i, text in enumerate(row):
                cells[i].text = ""
                self.runs(cells[i].paragraphs[0], f"**{text}**" if bold_first_col and i == 0 else str(text), font)
        for row in t.rows:
            for i, width in enumerate(widths_cm):
                row.cells[i].width = Cm(width)
        self.doc.add_paragraph()
        return t

    def callout(self, text: str, fill: str = "EFF6FF"):
        t = self.doc.add_table(rows=1, cols=1)
        t.style = "Table Grid"
        cell = t.rows[0].cells[0]
        cell.text = ""
        for i, line in enumerate(text.split("\n")):
            para = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            self.runs(para, line, 10.5)
        _shade(cell, fill)
        cell.width = CONTENT_WIDTH
        self.doc.add_paragraph()

    def code(self, text: str):
        """A dark block for commands or code; one line of text per line of input."""
        t = self.doc.add_table(rows=1, cols=1)
        cell = t.rows[0].cells[0]
        cell.text = ""
        for i, line in enumerate(text.split("\n")):
            para = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            para.paragraph_format.space_after = Pt(0)
            run = para.add_run(line if line else " ")
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
        _shade(cell, "0F172A")
        cell.width = CONTENT_WIDTH
        self.doc.add_paragraph().paragraph_format.space_after = Pt(0)

    def image(self, path: Path, caption: str, width_cm: float = 16.6):
        self.doc.add_picture(str(path), width=Cm(width_cm))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = self.p(caption, size=9, colour=GREY, center=True)
        cap.paragraph_format.space_after = Pt(12)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def title(self, text: str, subtitle: str, lines: list[str]):
        para = self.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(24)
        run.font.color.rgb = BLUE
        self.p(subtitle, size=13, colour=INK, center=True)
        for line in lines:
            self.p(line, size=10.5, colour=GREY, center=True)

    def save(self, path: Path):
        self.doc.save(path)
