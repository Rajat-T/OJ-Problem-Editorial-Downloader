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
import shutil
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
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer

# Import our comprehensive error handling
from utils.error_handler import (
    PDFGenerationError, FileSystemError, NetworkError, 
    handle_exception, ErrorDetector, error_reporter
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
        try:
            self.output_dir = Path(output_dir)
            
            # Validate and create output directory with error handling
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                raise FileSystemError(f"Permission denied creating output directory: {output_dir}", 
                                    str(output_dir), e)
            except OSError as e:
                raise FileSystemError(f"Failed to create output directory: {output_dir}", 
                                    str(output_dir), e)
            
            # Validate parameters
            if not (6 <= base_font_size <= 24):
                logger.warning(f"Font size {base_font_size} outside recommended range 6-24, using 11")
                base_font_size = 11
            
            if not body_font or not isinstance(body_font, str):
                logger.warning(f"Invalid body font '{body_font}', using Helvetica")
                body_font = "Helvetica"
            
            self.base_font_size = base_font_size
            self.body_font = body_font
            
            # Check disk space
            if not ErrorDetector.check_disk_space(str(self.output_dir), required_mb=100):
                logger.warning("Low disk space detected, PDF generation might fail")
            
            # Styles used throughout the document
            try:
                self.styles = getSampleStyleSheet()
                self._setup_custom_styles()
            except Exception as e:
                logger.error(f"Failed to setup PDF styles: {e}")
                raise PDFGenerationError(f"Style setup failed: {str(e)}", e)
            
            # Cache directory for downloaded/created images
            self.image_cache_dir = self.output_dir / "images"
            try:
                self.image_cache_dir.mkdir(exist_ok=True)
            except Exception as e:
                logger.warning(f"Failed to create image cache directory: {e}")
                # Use temp directory as fallback
                import tempfile
                self.image_cache_dir = Path(tempfile.mkdtemp(prefix="oj_pdf_images_"))
                logger.info(f"Using temporary image cache: {self.image_cache_dir}")
            
            self._figure_counter = 0
            
            logger.info(f"PDFCreator initialized successfully. Output: {self.output_dir}")
            
        except (FileSystemError, PDFGenerationError):
            raise
        except Exception as e:
            logger.error(f"Failed to initialize PDFCreator: {e}")
            raise PDFGenerationError(f"Initialization failed: {str(e)}", e)

    # ------------------------------------------------------------------
    # Style setup
    # ------------------------------------------------------------------

    def _setup_custom_styles(self) -> None:
        """Create a couple of custom styles used in documents."""

        # Add TitleCenter if it doesn't exist
        if "TitleCenter" not in self.styles:
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

        # Update existing Heading1 or create custom one
        if "Heading1" in self.styles:
            heading1 = self.styles["Heading1"]
            heading1.spaceBefore = 18
            heading1.spaceAfter = 12
            heading1.textColor = colors.darkblue
        else:
            self.styles.add(
                ParagraphStyle(
                    name="Heading1",
                    parent=self.styles["Normal"],
                    fontSize=16,
                    spaceBefore=18,
                    spaceAfter=12,
                    textColor=colors.darkblue,
                )
            )

        # Update existing Heading2 or create custom one
        if "Heading2" in self.styles:
            heading2 = self.styles["Heading2"]
            heading2.spaceBefore = 12
            heading2.spaceAfter = 6
            heading2.textColor = colors.blue
        else:
            self.styles.add(
                ParagraphStyle(
                    name="Heading2",
                    parent=self.styles["Normal"],
                    fontSize=14,
                    spaceBefore=12,
                    spaceAfter=6,
                    textColor=colors.blue,
                )
            )

        # Add Code style if it doesn't exist
        code_size = max(6, self.base_font_size - 1)
        if "Code" not in self.styles:
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

        # Add ProblemText style if it doesn't exist
        if "ProblemText" not in self.styles:
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

        # Add ImageCaption style if it doesn't exist
        if "ImageCaption" not in self.styles:
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
        """Download an image and cache it locally with comprehensive error handling."""
        
        if not url or not url.strip():
            logger.warning("Empty image URL provided")
            return None
        
        if not filename or not filename.strip():
            logger.warning("Empty filename provided for image download")
            return None
        
        try:
            # Validate URL format
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Invalid image URL format: {url}")
                return None
            
            # Check if file already exists
            file_path = self.image_cache_dir / filename
            if file_path.exists():
                try:
                    # Verify existing file is valid
                    Image.open(file_path).verify()
                    logger.debug(f"Using cached image: {filename}")
                    return file_path
                except Exception as e:
                    logger.warning(f"Cached image is corrupted, re-downloading: {e}")
                    try:
                        file_path.unlink()
                    except Exception:
                        pass
            
            # Download with timeout and retry logic
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Downloading image: {url} (attempt {attempt + 1}/{max_attempts})")
                    
                    response = requests.get(
                        url, 
                        timeout=30, 
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        },
                        stream=True
                    )
                    response.raise_for_status()
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    if not any(img_type in content_type for img_type in ['image/', 'application/octet-stream']):
                        logger.warning(f"Unexpected content type for image {url}: {content_type}")
                    
                    # Check content length
                    content_length = response.headers.get('content-length')
                    if content_length:
                        size_mb = int(content_length) / (1024 * 1024)
                        if size_mb > 10:  # 10MB limit
                            logger.warning(f"Image too large ({size_mb:.1f}MB): {url}")
                            return None
                    
                    # Download and validate content
                    content = response.content
                    if len(content) < 100:  # Very small file, likely not a real image
                        logger.warning(f"Image file too small ({len(content)} bytes): {url}")
                        continue
                    
                    # Save to temporary file first
                    temp_path = file_path.with_suffix('.tmp')
                    try:
                        temp_path.write_bytes(content)
                        
                        # Verify it's a valid image
                        with Image.open(temp_path) as img:
                            img.verify()
                        
                        # If verification succeeds, move to final location
                        shutil.move(str(temp_path), str(file_path))
                        
                        logger.info(f"Successfully downloaded image: {filename}")
                        return file_path
                        
                    except Exception as img_error:
                        logger.warning(f"Invalid image content from {url}: {img_error}")
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
                        if attempt == max_attempts - 1:
                            return None
                        continue
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Network error downloading image {url} (attempt {attempt + 1}): {e}")
                    if attempt == max_attempts - 1:
                        return None
                    import time
                    time.sleep(1 * (attempt + 1))  # Progressive delay
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error downloading image {url}: {e}")
                    if attempt == max_attempts - 1:
                        return None
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
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

    @handle_exception
    def create_problem_pdf(
        self,
        problem: Dict[str, Any],
        filename: Optional[str] = None,
        section_title: str = "Problem Statement",
    ) -> str:
        """
        Create a PDF containing a single programming problem with comprehensive error handling.

        Parameters
        ----------
        problem:
            Dictionary produced by the scraper containing all fields for
            the problem statement.
        filename:
            Optional custom filename.  When omitted one is generated from
            the problem title and platform.
        section_title:
            Title for the main section
            
        Returns
        -------
        str:
            Path to the created PDF file
            
        Raises
        ------
        PDFGenerationError:
            If PDF generation fails
        FileSystemError:
            If file system operations fail
        """
        
        try:
            # Validate input data
            if not problem or not isinstance(problem, dict):
                raise PDFGenerationError("Invalid problem data: empty or not a dictionary")
            
            # Sanitize and validate problem data
            from utils.error_handler import ErrorRecovery
            problem = ErrorRecovery.sanitize_content(problem)
            
            title = problem.get("title", "Problem").strip() or "Untitled Problem"
            platform = problem.get("platform", "Unknown").strip() or "Unknown"
            url = problem.get("url", "").strip()
            
            # Ensure required fields exist
            problem.setdefault("scrape_date", datetime.utcnow().isoformat())
            scrape_date = problem.get("scrape_date") or datetime.utcnow().isoformat()
            problem.setdefault("scrape_date", scrape_date)
            
            # Generate safe filename
            if not filename:
                try:
                    safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)
                    safe_title = safe_title[:50]  # Limit length
                    filename = f"{platform}_{safe_title}.pdf"
                except Exception as e:
                    logger.warning(f"Error generating filename: {e}")
                    filename = f"problem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Ensure filename is safe and has .pdf extension
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
            
            pdf_path = self.output_dir / filename
            
            # Check output directory permissions and disk space
            if not ErrorDetector.check_disk_space(str(self.output_dir), required_mb=50):
                raise FileSystemError("Insufficient disk space for PDF generation", str(self.output_dir))
            
            try:
                # Test write permissions
                test_file = pdf_path.with_suffix('.test')
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                raise FileSystemError(f"No write permission in output directory: {self.output_dir}", 
                                    str(self.output_dir), e)
            
            # Create document template with error handling
            try:
                doc = _TOCDocumentTemplate(
                    str(pdf_path),
                    pagesize=A4,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=72,
                )
                
                # Set PDF metadata safely
                try:
                    doc.title = title[:100]  # Limit metadata length
                    doc.author = platform[:50]
                    doc.subject = url[:200] if url else "Problem Statement"
                    doc.creator = "OJ Problem Editorial Downloader"
                except Exception as e:
                    logger.warning(f"Error setting PDF metadata: {e}")
                
            except Exception as e:
                raise PDFGenerationError(f"Failed to create PDF document template: {str(e)}", e, str(pdf_path))
            
            # Build PDF content with error handling
            try:
                story: List[Any] = []
                
                # Table of contents
                try:
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
                except Exception as e:
                    logger.warning(f"Failed to add table of contents: {e}")
                    # Continue without TOC
                
                # Add content sections with error handling
                try:
                    self._add_summary(story, problem)
                except Exception as e:
                    logger.warning(f"Failed to add summary section: {e}")
                
                try:
                    story.extend(self._build_content_story(problem, section_title))
                except Exception as e:
                    logger.error(f"Failed to build main content: {e}")
                    # Add error information to PDF
                    story.append(Paragraph("Content Generation Error", self.styles["Heading1"]))
                    story.append(Paragraph(f"An error occurred while generating the PDF content: {str(e)}", 
                                          self.styles["ProblemText"]))
                
                # Add timestamp
                try:
                    story.append(Spacer(1, 24))
                    story.append(
                        Paragraph(
                            f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                            self.styles["ProblemText"],
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to add timestamp: {e}")
                
            except Exception as e:
                raise PDFGenerationError(f"Failed to build PDF content: {str(e)}", e, str(pdf_path))
            
            # Generate the PDF
            try:
                doc.build(
                    story,
                    onFirstPage=lambda c, d: self._header_footer(c, d, title),
                    onLaterPages=lambda c, d: self._header_footer(c, d, title),
                )
                
                # Verify the PDF was created and is valid
                if not pdf_path.exists():
                    raise PDFGenerationError("PDF file was not created", output_path=str(pdf_path))
                
                file_size = pdf_path.stat().st_size
                if file_size < 1000:  # Less than 1KB is likely an error
                    raise PDFGenerationError(f"PDF file is too small ({file_size} bytes), generation likely failed", 
                                           output_path=str(pdf_path))
                
                logger.info(f"Problem PDF created successfully: {pdf_path} ({file_size} bytes)")
                return str(pdf_path)
                
            except Exception as e:
                # Clean up partial file
                try:
                    if pdf_path.exists():
                        pdf_path.unlink()
                except Exception:
                    pass
                raise PDFGenerationError(f"Failed to generate PDF: {str(e)}", e, str(pdf_path))
            
        except (PDFGenerationError, FileSystemError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in PDF generation: {e}")
            raise PDFGenerationError(f"Unexpected error: {str(e)}", e)

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

