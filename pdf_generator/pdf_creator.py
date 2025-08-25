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
from typing import Any, Dict, List, Optional

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
    TableOfContents,
)

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
    """

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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

        self.styles.add(
            ParagraphStyle(
                name="Code",
                parent=self.styles["Normal"],
                fontName="Courier",
                fontSize=10,
                backColor=colors.whitesmoke,
                leftIndent=6,
                rightIndent=6,
                leading=12,
                spaceAfter=6,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="ProblemText",
                parent=self.styles["Normal"],
                alignment=TA_JUSTIFY,
                fontSize=11,
                leading=14,
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

    def _add_heading(self, story: List[Any], text: str, level: int = 0) -> None:
        """Create a heading paragraph and register it for the TOC."""

        style_name = "Heading1" if level == 0 else "Heading2"
        para = Paragraph(text, self.styles[style_name])
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

    # ------------------------------------------------------------------
    # PDF generation
    # ------------------------------------------------------------------

    def create_problem_pdf(self, problem: Dict[str, Any], filename: Optional[str] = None) -> str:
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
        scrape_date = problem.get("scrape_date") or datetime.utcnow().isoformat()

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

        # Title and metadata
        self._add_heading(story, title, level=0)
        story.append(Paragraph(f"Source: {platform}", self.styles["ProblemText"]))
        if url:
            story.append(
                Paragraph(
                    f"URL: <link href='{url}' color='blue'>{url}</link>",
                    self.styles["ProblemText"],
                )
            )
        story.append(Paragraph(f"Scraped on: {scrape_date}", self.styles["ProblemText"]))
        story.append(Spacer(1, 12))

        # Problem statement and sections
        statement = problem.get("statement") or ""
        if statement:
            self._add_heading(story, "Problem Statement", 0)
            for paragraph in statement.split("\n\n"):
                self._add_text_with_math(story, paragraph.strip(), self.styles["ProblemText"])

        input_spec = problem.get("input_specification") or problem.get("input_format") or ""
        if input_spec:
            self._add_heading(story, "Input", 0)
            self._add_text_with_math(story, input_spec, self.styles["ProblemText"])

        output_spec = problem.get("output_specification") or problem.get("output_format") or ""
        if output_spec:
            self._add_heading(story, "Output", 0)
            self._add_text_with_math(story, output_spec, self.styles["ProblemText"])

        constraints = problem.get("constraints") or ""
        if constraints:
            self._add_heading(story, "Constraints", 0)
            self._add_text_with_math(story, constraints, self.styles["ProblemText"])

        # Sample test cases
        samples = problem.get("samples") or []
        if samples:
            self._add_heading(story, "Sample Test Cases", 0)
            for idx, sample in enumerate(samples, 1):
                self._add_heading(story, f"Sample {idx}", 1)
                inp = sample.get("input") or sample.get("content") or ""
                out = sample.get("output") or ""
                if inp:
                    story.append(Paragraph("Input:", self.styles["ProblemText"]))
                    story.append(Preformatted(inp, self.styles["Code"]))
                if out:
                    story.append(Paragraph("Output:", self.styles["ProblemText"]))
                    story.append(Preformatted(out, self.styles["Code"]))

        # Images with captions
        for img in problem.get("images", []):
            url = img.get("url")
            caption = img.get("alt", "")
            if url:
                self._add_image(story, url, caption)

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

    def create_editorial_pdf(self, editorial: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Generate a PDF for an editorial.

        Editorial data uses the same structure as problems for the
        purposes of PDF generation; therefore we reuse
        :meth:`create_problem_pdf`.
        """

        return self.create_problem_pdf(editorial, filename=filename)

    def create_combined_pdf(
        self,
        problem: Dict[str, Any],
        editorial: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """Create a single PDF containing both the problem and editorial.

        The implementation simply generates two separate PDFs and merges
        them together.  This keeps the code small while still providing
        the combined artefact expected by the UI.
        """

        if not filename:
            title = problem.get("title", "problem")
            safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)
            filename = f"{safe_title}_complete.pdf"

        pdf_path = self.output_dir / filename

        # Generate temporary PDFs
        tmp_problem = self.create_problem_pdf(problem, filename="_tmp_problem.pdf")
        tmp_editorial = self.create_problem_pdf(editorial, filename="_tmp_editorial.pdf")

        try:
            from PyPDF2 import PdfMerger

            merger = PdfMerger()
            for p in [tmp_problem, tmp_editorial]:
                merger.append(p)
            with open(pdf_path, "wb") as fh:
                merger.write(fh)
            merger.close()
        finally:
            for tmp in [tmp_problem, tmp_editorial]:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

        return str(pdf_path)


__all__ = ["PDFCreator"]

