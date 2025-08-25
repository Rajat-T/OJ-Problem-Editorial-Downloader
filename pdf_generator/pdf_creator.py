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

import html
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

    def _convert_latex_symbols(self, text: str) -> str:
        """Convert common LaTeX mathematical symbols to Unicode equivalents or proper LaTeX format.
        
        This handles cases where LaTeX commands appear in plain text without proper $...$ wrapping.
        """
        if not text:
            return text
            
        # Dictionary of LaTeX commands to Unicode symbols
        latex_to_unicode = {
            # Comparison operators
            r'\\leq': '≤',
            r'\\geq': '≥',
            r'\\neq': '≠',
            r'\\le': '≤',
            r'\\ge': '≥',
            r'\\ne': '≠',
            r'\\approx': '≈',
            r'\\equiv': '≡',
            r'\\cong': '≅',
            r'\\sim': '∼',
            r'\\propto': '∝',
            # Arithmetic symbols
            r'\\times': '×',
            r'\\div': '÷',
            r'\\pm': '±',
            r'\\mp': '∓',
            r'\\cdot': '⋅',
            r'\\bullet': '•',
            r'\\ast': '∗',
            r'\\star': '⋆',
            r'\\oplus': '⊕',
            r'\\ominus': '⊖',
            r'\\otimes': '⊗',
            r'\\oslash': '⊘',
            # Dots and ellipses
            r'\\vdots': '⋮',
            r'\\hdots': '⋯',
            r'\\ddots': '⋱',
            r'\\ldots': '…',
            r'\\cdots': '⋯',
            # Set theory symbols
            r'\\cap': '∩',
            r'\\cup': '∪',
            r'\\subset': '⊂',
            r'\\supset': '⊃',
            r'\\subseteq': '⊆',
            r'\\supseteq': '⊇',
            r'\\subsetneq': '⊊',
            r'\\supsetneq': '⊋',
            r'\\in': '∈',
            r'\\notin': '∉',
            r'\\ni': '∋',
            r'\\emptyset': '∅',
            r'\\varnothing': '∅',
            # Mathematical symbols
            r'\\infty': '∞',
            r'\\partial': '∂',
            r'\\nabla': '∇',
            r'\\sum': '∑',
            r'\\prod': '∏',
            r'\\int': '∫',
            r'\\oint': '∮',
            r'\\sqrt': '√',
            r'\\angle': '∠',
            r'\\perp': '⊥',
            r'\\parallel': '∥',
            r'\\triangle': '△',
            r'\\square': '□',
            r'\\diamond': '⋄',
            r'\\circ': '∘',
            r'\\bigcirc': '○',
            # Greek lowercase letters
            r'\\alpha': 'α',
            r'\\beta': 'β',
            r'\\gamma': 'γ',
            r'\\delta': 'δ',
            r'\\epsilon': 'ε',
            r'\\varepsilon': 'ε',
            r'\\zeta': 'ζ',
            r'\\eta': 'η',
            r'\\theta': 'θ',
            r'\\vartheta': 'ϑ',
            r'\\iota': 'ι',
            r'\\kappa': 'κ',
            r'\\lambda': 'λ',
            r'\\mu': 'μ',
            r'\\nu': 'ν',
            r'\\xi': 'ξ',
            r'\\pi': 'π',
            r'\\varpi': 'ϖ',
            r'\\rho': 'ρ',
            r'\\varrho': 'ϱ',
            r'\\sigma': 'σ',
            r'\\varsigma': 'ς',
            r'\\tau': 'τ',
            r'\\upsilon': 'υ',
            r'\\phi': 'φ',
            r'\\varphi': 'φ',
            r'\\chi': 'χ',
            r'\\psi': 'ψ',
            r'\\omega': 'ω',
            # Greek uppercase letters
            r'\\Alpha': 'Α',
            r'\\Beta': 'Β',
            r'\\Gamma': 'Γ',
            r'\\Delta': 'Δ',
            r'\\Epsilon': 'Ε',
            r'\\Zeta': 'Ζ',
            r'\\Eta': 'Η',
            r'\\Theta': 'Θ',
            r'\\Iota': 'Ι',
            r'\\Kappa': 'Κ',
            r'\\Lambda': 'Λ',
            r'\\Mu': 'Μ',
            r'\\Nu': 'Ν',
            r'\\Xi': 'Ξ',
            r'\\Pi': 'Π',
            r'\\Rho': 'Ρ',
            r'\\Sigma': 'Σ',
            r'\\Tau': 'Τ',
            r'\\Upsilon': 'Υ',
            r'\\Phi': 'Φ',
            r'\\Chi': 'Χ',
            r'\\Psi': 'Ψ',
            r'\\Omega': 'Ω',
            # Arrows
            r'\\rightarrow': '→',
            r'\\to': '→',
            r'\\leftarrow': '←',
            r'\\gets': '←',
            r'\\leftrightarrow': '↔',
            r'\\uparrow': '↑',
            r'\\downarrow': '↓',
            r'\\updownarrow': '↕',
            r'\\nearrow': '↗',
            r'\\searrow': '↘',
            r'\\swarrow': '↙',
            r'\\nwarrow': '↖',
            r'\\Rightarrow': '⇒',
            r'\\Leftarrow': '⇐',
            r'\\Leftrightarrow': '⇔',
            r'\\Uparrow': '⇑',
            r'\\Downarrow': '⇓',
            r'\\Updownarrow': '⇕',
            r'\\mapsto': '↦',
            r'\\longmapsto': '⟼',
            r'\\longrightarrow': '⟶',
            r'\\longleftarrow': '⟵',
            r'\\longleftrightarrow': '⟷',
            # Logic symbols
            r'\\land': '∧',
            r'\\wedge': '∧',
            r'\\lor': '∨',
            r'\\vee': '∨',
            r'\\lnot': '¬',
            r'\\neg': '¬',
            r'\\forall': '∀',
            r'\\exists': '∃',
            r'\\nexists': '∄',
            r'\\top': '⊤',
            r'\\bot': '⊥',
            r'\\models': '⊨',
            r'\\vdash': '⊢',
            r'\\dashv': '⊣',
            # Brackets and parentheses  
            r'\\lfloor': '⌊',
            r'\\rfloor': '⌋',
            r'\\lceil': '⌈',
            r'\\rceil': '⌉',
            r'\\langle': '⟨',
            r'\\rangle': '⟩',
            r'\\llbracket': '⟦',
            r'\\rrbracket': '⟧',
            # Miscellaneous symbols
            r'\\mid': '∣',
            r'\\parallel': '∥',
            r'\\nmid': '∤',
            r'\\nparallel': '∦',
            r'\\hbar': 'ℏ',
            r'\\ell': 'ℓ',
            r'\\wp': '℘',
            r'\\Re': 'ℜ',
            r'\\Im': 'ℑ',
            r'\\aleph': 'ℵ',
            r'\\beth': 'ℶ',
            r'\\gimel': 'ℷ',
            r'\\daleth': 'ℸ',
            r'\\clubsuit': '♣',
            r'\\diamondsuit': '♢',
            r'\\heartsuit': '♡',
            r'\\spadesuit': '♠',
        }
        
        # Replace LaTeX commands with Unicode symbols
        for latex_cmd, unicode_char in latex_to_unicode.items():
            text = re.sub(latex_cmd, unicode_char, text)
        
        # Handle common mathematical formatting patterns
        # Convert subscripts and superscripts to more readable format
        text = re.sub(r'([A-Za-z0-9])_\{([^}]+)\}', r'\1₍\2₎', text)  # A_{i} -> A₍i₎
        text = re.sub(r'([A-Za-z0-9])_([A-Za-z0-9])', r'\1₍\2₎', text)  # A_i -> A₍i₎
        text = re.sub(r'([A-Za-z0-9])\^\{([^}]+)\}', r'\1⁽\2⁾', text)  # A^{i} -> A⁽i⁾
        text = re.sub(r'([A-Za-z0-9])\^([A-Za-z0-9])', r'\1⁽\2⁾', text)  # A^i -> A⁽i⁾
        
        # Clean up common LaTeX formatting issues
        text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)  # \text{something} -> something
        text = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', text)  # \mathrm{something} -> something
        text = re.sub(r'\\textbf\{([^}]+)\}', r'**\1**', text)  # \textbf{something} -> **something**
        text = re.sub(r'\\textit\{([^}]+)\}', r'*\1*', text)  # \textit{something} -> *something*
        
        # Handle fractions in a more readable way
        text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', text)  # \frac{a}{b} -> (a)/(b)
        
        # Handle common spacing commands
        text = re.sub(r'\\,', ' ', text)  # thin space
        text = re.sub(r'\\;', '  ', text)  # medium space
        text = re.sub(r'\\quad', '    ', text)  # quad space
        text = re.sub(r'\\qquad', '        ', text)  # double quad space
        
        # Clean up remaining backslashes from LaTeX commands
        text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)  # Remove backslash from unrecognized commands
        
        return text

    def _improve_text_formatting(self, text: str) -> str:
        """Improve text formatting for better readability in PDFs."""
        if not text:
            return text
        
        # Decode HTML entities first
        text = html.unescape(text)
        
        # Handle common HTML/XML entities that might not be decoded
        html_entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&#39;': "'",
            '&rsquo;': "'",
            '&lsquo;': "'",
            '&rdquo;': '"',
            '&ldquo;': '"',
            '&mdash;': '—',
            '&ndash;': '–',
            '&hellip;': '…',
        }
        
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)
            
        # Fix common spacing issues
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = re.sub(r'\s*,\s*', ', ', text)  # Fix comma spacing
        text = re.sub(r'\s*\.\s*', '. ', text)  # Fix period spacing
        text = re.sub(r'\s*;\s*', '; ', text)  # Fix semicolon spacing
        text = re.sub(r'\s*:\s*', ': ', text)  # Fix colon spacing
        
        # Improve parentheses spacing
        text = re.sub(r'\s*\(\s*', ' (', text)
        text = re.sub(r'\s*\)\s*', ') ', text)
        
        # Fix spacing around mathematical operators
        text = re.sub(r'\s*=\s*', ' = ', text)
        text = re.sub(r'\s*\+\s*', ' + ', text)
        text = re.sub(r'\s*-\s*', ' - ', text)
        text = re.sub(r'\s*\*\s*', ' × ', text)  # Replace * with proper multiplication
        text = re.sub(r'\s*/\s*', ' / ', text)
        
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    def _add_text_with_math(self, story: List[Any], text: str, style: ParagraphStyle) -> None:
        """Add text to the story while rendering math blocks.

        The function looks for ``$...$`` patterns.  Pieces of plain text
        are appended as :class:`Paragraph` objects, while the expressions
        themselves are rendered using :func:`_render_math` and inserted as
        images.  This keeps the surrounding text searchable and
        copy‑able whilst still allowing mathematical notation.
        """
        
        # First convert LaTeX symbols to Unicode or proper format
        text = self._convert_latex_symbols(text)
        
        # Improve spacing and formatting for better readability
        text = self._improve_text_formatting(text)
        
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
                    # Fallback to text if math rendering fails
                    # Apply LaTeX symbol conversion to the expression as well
                    converted_expr = self._convert_latex_symbols(expr)
                    story.append(Paragraph(converted_expr, style))
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

        if page_break_before:
            story.append(PageBreak())
            
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

        try:
            # Get image dimensions to preserve aspect ratio
            with Image.open(local_path) as pil_img:
                original_width, original_height = pil_img.size
                
            # Calculate dimensions while preserving aspect ratio
            if original_width > max_width:
                # Scale down proportionally
                aspect_ratio = original_height / original_width
                img_width = max_width
                img_height = max_width * aspect_ratio
            else:
                # Use original size if smaller than max_width
                img_width = original_width
                img_height = original_height
            
            img = RLImage(str(local_path), width=img_width, height=img_height)
            img.hAlign = "CENTER"
            story.append(img)

            if caption:
                self._figure_counter += 1
                story.append(
                    Paragraph(f"Figure {self._figure_counter}: {caption}", self.styles["ImageCaption"])
                )
                
        except Exception as e:
            logger.warning(f"Error processing image {url}: {e}")
            # Add a placeholder text instead of failing
            story.append(
                Paragraph(f"[Image could not be loaded: {url}]", self.styles["ImageCaption"])
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

        # Use the correct field names that come from the scrapers
        statement = data.get("problem_statement") or data.get("statement") or data.get("content") or ""
        if statement:
            for paragraph in statement.split("\n\n"):
                self._add_text_with_math(section, paragraph.strip(), self.styles["ProblemText"])

        input_spec = data.get("input_format") or data.get("input_specification") or ""
        if input_spec:
            self._add_heading(section, "Input", 1)
            self._add_text_with_math(section, input_spec, self.styles["ProblemText"])

        output_spec = data.get("output_format") or data.get("output_specification") or ""
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
            samples = data.get("examples") or data.get("samples") or []
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
                    content_story = self._build_content_story(problem, section_title)
                    logger.debug(f"Content story built successfully, type: {type(content_story)}, length: {len(content_story)}")
                    
                    # Validate content_story before extending
                    if not isinstance(content_story, list):
                        logger.error(f"Content story is not a list: {type(content_story)}")
                        raise PDFGenerationError(f"Content story validation failed: expected list, got {type(content_story)}")
                    
                    # Check each item in content_story
                    for i, item in enumerate(content_story):
                        if hasattr(item, 'insert') and not isinstance(item, list):
                            logger.warning(f"Item {i} has insert method but is not a list: {type(item)}")
                    
                    logger.debug(f"Extending story with {len(content_story)} items")
                    story.extend(content_story)
                    logger.debug(f"Story extended successfully, new length: {len(story)}")
                    
                except Exception as e:
                    logger.error(f"Failed to build main content: {e}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
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

