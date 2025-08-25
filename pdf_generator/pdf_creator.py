"""pdf_generator.pdf_creator
================================

Utility helpers for converting scraped problem statements and
editorials into rich, well structured PDF documents.  The goal of this
module is to produce PDF files that are easy for Large Language Models
and OCR systems to consume while still being pleasant for humans to
read.  The :class:`PDFCreator` class exposes a couple of high level
methods used throughout the project to generate PDFs for problems,
editorials or a combination of both.

Key features implemented:

* Text formatting for headers, paragraphs and code blocks.
* Embedding of remote images with automatic caption handling.
* Basic support for mathematical expressions using ``matplotlib``.
* Automatic table of contents generation.
* PDF metadata (source, url, scrape date …).
* Page headers and footers with page numbers.
* Syntax highlighted code snippets via ``pygments``.
* Table rendering for summaries, constraints and examples.
* Bookmarks for easy navigation and separate sections for problems and editorials.
* Configurable base font and size with a dedicated summary page.

The implementation relies solely on `reportlab` which is already a
dependency of the project.  Optional rendering of mathematics requires
``matplotlib`` – if it is not available the raw expression is inserted
as normal text so the resulting document still remains readable.
"""

from __future__ import annotations

import io
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableOfContents,
    TableStyle,
)
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility document template
# ---------------------------------------------------------------------------


class _TOCDocumentTemplate(SimpleDocTemplate):
    """Custom document template that registers headings for the TOC."""

    def afterFlowable(self, flowable):  # type: ignore[override]
        if hasattr(flowable, "_bookmarkName"):
            self.canv.bookmarkPage(flowable._bookmarkName)
            text = getattr(flowable, "_headingText", flowable.getPlainText())
            level = getattr(flowable, "_tocLevel", 0)
            self.notify("TOCEntry", (level, text, self.page))


# ---------------------------------------------------------------------------
# PDF creator
# ---------------------------------------------------------------------------


class PDFCreator:
    """Create well formatted PDF files from scraped content.

    Parameters
    ----------
    output_dir:
        Directory where generated files are saved.  Missing directories
        are created automatically.
    base_font_size:
        Base font size used for normal paragraph text.  Heading and code
        block sizes are derived from this value.
    body_font:
        Name of the font used for regular text.
    """

    def __init__(
        self,
        output_dir: str = "output",
        base_font_size: int = 11,
        body_font: str = "Helvetica",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.base_font_size = base_font_size
        self.body_font = body_font

        # Styles used throughout the document
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

        # Cache directory for downloaded/created images
        self.image_cache_dir = self.output_dir / "images"
        self.image_cache_dir.mkdir(exist_ok=True)

        self._figure_counter = 0

    # ------------------------------------------------------------------
    # Style setup
    # ------------------------------------------------------------------

    def _setup_custom_styles(self) -> None:
        """Create a couple of custom styles used in documents."""

        self.styles.add(
            ParagraphStyle(
                name="TitleCenter",
                parent=self.styles["Title"],
                alignment=TA_CENTER,
                fontSize=20,
                spaceAfter=24,
                textColor=colors.darkblue,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="Heading1",
                parent=self.styles["Heading1"],
                spaceBefore=18,
                spaceAfter=12,
                textColor=colors.darkblue,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="Heading2",
                parent=self.styles["Heading2"],
                spaceBefore=12,
                spaceAfter=6,
                textColor=colors.blue,
            )
        )

        code_size = max(6, self.base_font_size - 1)
        self.styles.add(
            ParagraphStyle(
                name="Code",
                parent=self.styles["Normal"],
                fontName="Courier",
                fontSize=code_size,
                backColor=colors.whitesmoke,
                leftIndent=6,
                rightIndent=6,
                leading=code_size + 2,
                spaceAfter=6,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="ProblemText",
                parent=self.styles["Normal"],
                alignment=TA_JUSTIFY,
                fontName=self.body_font,
                fontSize=self.base_font_size,
                leading=self.base_font_size + 3,
                spaceAfter=6,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="ImageCaption",
                parent=self.styles["Italic"],
                fontSize=9,
                alignment=TA_CENTER,
                spaceAfter=12,
            )
        )

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _header_footer(self, canvas, doc, title: str) -> None:
        """Draw page header and number.

        Parameters
        ----------
        canvas : :class:`reportlab.pdfgen.canvas.Canvas`
            Canvas object used by reportlab.
        doc : :class:`reportlab.platypus.BaseDocTemplate`
            Current document template.
        title : str
            Title displayed in the header.
        """

        canvas.saveState()
        width, height = doc.pagesize
        canvas.setFont("Helvetica", 9)
        canvas.drawString(inch, height - 0.75 * inch, title)
        canvas.drawRightString(width - inch, 0.75 * inch, f"Page {doc.page}")
        canvas.restoreState()

    def _download_image(self, url: str, filename: str) -> Optional[Path]:
        """Download an image and cache it locally."""

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            path = self.image_cache_dir / filename
            path.write_bytes(response.content)
            # Validate that the file is an image
            Image.open(path).verify()
            return path
        except Exception as exc:  # pragma: no cover - network/IO guard
            logger.warning("Failed to download image %s: %s", url, exc)
            return None

    def _render_math(self, expression: str) -> Optional[Path]:
        """Render a LaTeX expression to an image using matplotlib."""

        try:
            import matplotlib.pyplot as plt

            fig = plt.figure()
            fig.patch.set_alpha(0.0)
            text = fig.text(0, 0, f"$${expression}$$", fontsize=12)
            plt.axis("off")
            buffer = io.BytesIO()
            fig.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0.05, dpi=300)
            plt.close(fig)
            buffer.seek(0)

            filename = f"math_{abs(hash(expression))}.png"
            path = self.image_cache_dir / filename
            path.write_bytes(buffer.getvalue())
            return path
        except Exception as exc:  # pragma: no cover - optional feature
            logger.warning("Unable to render math expression %s: %s", expression, exc)
            return None

    def _add_text_with_math(self, story: List[Any], text: str, style: ParagraphStyle) -> None:
        """Add text to the story while rendering math blocks.

        The function looks for ``$...$`` patterns.  Pieces of plain text
        are appended as :class:`Paragraph` objects, while the expressions
        themselves are rendered using :func:`_render_math` and inserted as
        images.  This keeps the surrounding text searchable and
        copy‑able whilst still allowing mathematical notation.
        """

        pattern = re.compile(r"(\$[^$]+\$)")
        parts = pattern.split(text)
        for part in parts:
            if not part:
                continue
            if part.startswith("$") and part.endswith("$"):
                expr = part[1:-1]
                img_path = self._render_math(expr)
                if img_path:
                    story.append(RLImage(str(img_path), width=2 * inch))
            else:
                story.append(Paragraph(part, style))

    def _add_heading(
        self,
        story: List[Any],
        text: str,
        level: int = 0,
        page_break_before: bool = False,
    ) -> None:
        """Create a heading paragraph and register it for the TOC."""

        style_name = "Heading1" if level == 0 else "Heading2"
        para = Paragraph(text, self.styles[style_name])
        if page_break_before:
            para.__dict__["pageBreakBefore"] = True
        bookmark = re.sub(r"[^a-zA-Z0-9]+", "_", text) + f"_{level}"
        para._bookmarkName = bookmark
        para._headingText = text
        para._tocLevel = level
        story.append(para)

    def _add_image(
        self,
        story: List[Any],
        url: str,
        caption: str = "",
        max_width: float = 5 * inch,
    ) -> None:
        """Insert an image with an optional caption."""

        filename = f"img_{abs(hash(url))}.png"
        local_path = self._download_image(url, filename)
        if not local_path:
            return

        img = RLImage(str(local_path), width=max_width, preserveAspectRatio=True)
        img.hAlign = "CENTER"
        story.append(img)

        if caption:
            self._figure_counter += 1
            story.append(
                Paragraph(f"Figure {self._figure_counter}: {caption}", self.styles["ImageCaption"])
            )

    def _add_table(self, story: List[Any], data: Sequence[Sequence[str]]) -> None:
        """Add a simple table to the story."""

        tbl = Table(data, hAlign="LEFT")
        tbl.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        story.append(tbl)

    def _highlight_code(self, code: str, language: Optional[str] = None) -> Any:
        """Return a flowable with syntax highlighted code.

        The implementation uses :mod:`pygments` with inline styling so the
        resulting text remains selectable and searchable in the PDF.  When
        highlighting fails the raw code is inserted instead.
        """

        try:
            lexer = get_lexer_by_name(language) if language else guess_lexer(code)
            formatter = HtmlFormatter(nowrap=True, noclasses=True)
            highlighted = highlight(code, lexer, formatter)
            highlighted = highlighted.replace("<span style=\"", "<font ")
            highlighted = highlighted.replace("color: ", "color=")
            highlighted = highlighted.replace(";\">", ">")
            highlighted = highlighted.replace("</span>", "</font>")
            highlighted = highlighted.replace(" ", "&nbsp;").replace("\n", "<br/>")
            return Paragraph(highlighted, self.styles["Code"])
        except Exception:
            return Preformatted(code, self.styles["Code"])

    def _add_summary(self, story: List[Any], data: Dict[str, Any], page_break: bool = False) -> None:
        """Insert a summary table with problem metadata."""

        tags = data.get("tags")
        if isinstance(tags, (list, tuple)):
            tags = ", ".join(tags)
        summary_data = [
            ["Title", data.get("title", "")],
            ["Source", data.get("platform", "")],
            ["URL", data.get("url", "")],
            ["Difficulty", data.get("difficulty", "")],
            ["Tags", tags or ""],
            ["Scraped on", data.get("scrape_date", "")],
        ]
        self._add_heading(story, "Summary", 0, page_break_before=page_break)
        self._add_table(story, summary_data)

    def _build_content_story(self, data: Dict[str, Any], section_title: str) -> List[Any]:
        """Build the story for either the problem or editorial section."""

        section: List[Any] = []
        self._add_heading(section, section_title, 0, page_break_before=True)

        statement = data.get("statement") or data.get("content") or ""
        if statement:
            for paragraph in statement.split("\n\n"):
                self._add_text_with_math(section, paragraph.strip(), self.styles["ProblemText"])

        input_spec = data.get("input_specification") or data.get("input_format") or ""
        if input_spec:
            self._add_heading(section, "Input", 1)
            self._add_text_with_math(section, input_spec, self.styles["ProblemText"])

        output_spec = data.get("output_specification") or data.get("output_format") or ""
        if output_spec:
            self._add_heading(section, "Output", 1)
            self._add_text_with_math(section, output_spec, self.styles["ProblemText"])

        constraints = data.get("constraints") or ""
        constraints_table = data.get("constraints_table")
        if constraints_table:
            self._add_heading(section, "Constraints", 1)
            self._add_table(section, constraints_table)
        elif constraints:
            self._add_heading(section, "Constraints", 1)
            self._add_text_with_math(section, constraints, self.styles["ProblemText"])

        examples_table = data.get("examples_table")
        if examples_table:
            self._add_heading(section, "Examples", 1)
            self._add_table(section, examples_table)
        else:
            samples = data.get("samples") or data.get("examples") or []
            if samples:
                self._add_heading(section, "Sample Test Cases", 1)
                for idx, sample in enumerate(samples, 1):
                    self._add_heading(section, f"Sample {idx}", 2)
                    inp = sample.get("input") or sample.get("content") or ""
                    out = sample.get("output") or ""
                    if inp:
                        section.append(Paragraph("Input:", self.styles["ProblemText"]))
                        section.append(self._highlight_code(inp, language="text"))
                    if out:
                        section.append(Paragraph("Output:", self.styles["ProblemText"]))
                        section.append(self._highlight_code(out, language="text"))

        # Code snippets
        code_blocks = data.get("code_blocks") or data.get("code") or []
        if isinstance(code_blocks, str):
            code_blocks = [{"code": code_blocks}]
        if isinstance(code_blocks, dict):  # single block as dict
            code_blocks = [code_blocks]
        for block in code_blocks:
            code = block.get("code") or ""
            lang = block.get("language")
            if code:
                self._add_heading(section, block.get("title", "Code"), 1)
                section.append(self._highlight_code(code, lang))

        # Images with captions
        for img in data.get("images", []):
            url = img.get("url")
            caption = img.get("alt", "")
            if url:
                self._add_image(section, url, caption)

        return section

    # ------------------------------------------------------------------
    # PDF generation
    # ------------------------------------------------------------------

    def create_problem_pdf(
        self,
        problem: Dict[str, Any],
        filename: Optional[str] = None,
        section_title: str = "Problem Statement",
    ) -> str:
        """Create a PDF containing a single programming problem.

        Parameters
        ----------
        problem:
            Dictionary produced by the scraper containing all fields for
            the problem statement.
        filename:
            Optional custom filename.  When omitted one is generated from
            the problem title and platform.
        """

        title = problem.get("title", "Problem")
        platform = problem.get("platform", "Unknown")
        url = problem.get("url", "")
        problem.setdefault("scrape_date", datetime.utcnow().isoformat())
        scrape_date = problem.get("scrape_date") or datetime.utcnow().isoformat()
        problem.setdefault("scrape_date", scrape_date)

        if not filename:
            safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)
            filename = f"{platform}_{safe_title}.pdf"

        pdf_path = self.output_dir / filename

        doc = _TOCDocumentTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        # PDF metadata
        doc.title = title
        doc.author = platform
        doc.subject = url
        doc.creator = "OJ Problem Editorial Downloader"

        story: List[Any] = []

        # Table of contents placeholder
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                name="TOCLevel1",
                fontSize=12,
                leftIndent=20,
                firstLineIndent=-20,
                spaceBefore=5,
            ),
            ParagraphStyle(
                name="TOCLevel2",
                fontSize=10,
                leftIndent=40,
                firstLineIndent=-20,
                spaceBefore=2,
            ),
        ]
        story.append(Paragraph("Table of Contents", self.styles["TitleCenter"]))
        story.append(toc)
        story.append(PageBreak())

        # Summary and problem content
        self._add_summary(story, problem)
        story.extend(self._build_content_story(problem, section_title))

        story.append(Spacer(1, 24))
        story.append(
            Paragraph(
                f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                self.styles["ProblemText"],
            )
        )

        doc.build(
            story,
            onFirstPage=lambda c, d: self._header_footer(c, d, title),
            onLaterPages=lambda c, d: self._header_footer(c, d, title),
        )

        logger.info("Problem PDF created: %s", pdf_path)
        return str(pdf_path)

    # ------------------------------------------------------------------
    # The following two helpers are light‑weight wrappers kept for API
    # compatibility with the rest of the project.  They simply forward to
    # :meth:`create_problem_pdf` by merging the problem and editorial
    # sections into a single document.
    # ------------------------------------------------------------------

    def create_editorial_pdf(
        self, editorial: Dict[str, Any], filename: Optional[str] = None
    ) -> str:
        """Generate a PDF for an editorial."""

        return self.create_problem_pdf(
            editorial, filename=filename, section_title="Editorial"
        )

    def create_combined_pdf(
        self,
        problem: Dict[str, Any],
        editorial: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """Create a single PDF containing both the problem and editorial."""

        title = problem.get("title", "Problem")
        platform = problem.get("platform", "Unknown")
        url = problem.get("url", "")

        if not filename:
            safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)
            filename = f"{safe_title}_complete.pdf"

        pdf_path = self.output_dir / filename

        doc = _TOCDocumentTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        doc.title = title
        doc.author = platform
        doc.subject = url
        doc.creator = "OJ Problem Editorial Downloader"

        story: List[Any] = []

        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                name="TOCLevel1",
                fontSize=12,
                leftIndent=20,
                firstLineIndent=-20,
                spaceBefore=5,
            ),
            ParagraphStyle(
                name="TOCLevel2",
                fontSize=10,
                leftIndent=40,
                firstLineIndent=-20,
                spaceBefore=2,
            ),
        ]
        story.append(Paragraph("Table of Contents", self.styles["TitleCenter"]))
        story.append(toc)
        story.append(PageBreak())

        self._add_summary(story, problem)
        story.extend(self._build_content_story(problem, "Problem"))
        story.extend(self._build_content_story(editorial, "Editorial"))

        story.append(Spacer(1, 24))
        story.append(
            Paragraph(
                f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                self.styles["ProblemText"],
            )
        )

        doc.build(
            story,
            onFirstPage=lambda c, d: self._header_footer(c, d, title),
            onLaterPages=lambda c, d: self._header_footer(c, d, title),
        )

        return str(pdf_path)


__all__ = ["PDFCreator"]

