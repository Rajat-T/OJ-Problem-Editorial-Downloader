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
* PDF metadata (source, url, scrape date ...).
* Page headers and footers with page numbers.
* Syntax highlighted code snippets via ``pygments``.
* Table rendering for summaries, constraints and examples.
* Bookmarks for easy navigation and separate sections for problems and editorials.
* Configurable base font and size with a dedicated summary page.

The implementation relies solely on `reportlab` which is already a
dependency of the project.  Optional rendering of mathematics requires
``matplotlib`` - if it is not available the raw expression is inserted
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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
            
            # Try to register better fonts that support mathematical symbols
            self._register_math_fonts()
            
            # Check if the requested font is available, fallback to a better one if not
            if not body_font or not isinstance(body_font, str):
                logger.warning(f"Invalid body font '{body_font}', using DejaVu")
                body_font = "DejaVu"
            
            # Check if font is available, if not try to fallback to a better option
            if body_font not in ("Helvetica", "Times-Roman", "Courier"):
                # Try to use a font with better Unicode support
                try:
                    from reportlab.pdfbase.pdfmetrics import getRegisteredFontNames
                    registered_fonts = getRegisteredFontNames()
                    if body_font not in registered_fonts:
                        # Try DejaVu which has better Unicode support
                        if "DejaVu" in registered_fonts:
                            body_font = "DejaVu"
                        else:
                            body_font = "Helvetica"  # Fallback to default
                except:
                    body_font = "Helvetica"  # Safe fallback
            
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
            
            logger.info(f"PDFCreator initialized successfully. Output: {self.output_dir}, Font: {self.body_font}")
            
        except (FileSystemError, PDFGenerationError):
            raise
        except Exception as e:
            logger.error(f"Failed to initialize PDFCreator: {e}")
            raise PDFGenerationError(f"Initialization failed: {str(e)}", e)

    # ------------------------------------------------------------------
    # Font handling
    # ------------------------------------------------------------------
    
    def _register_math_fonts(self) -> None:
        """Register fonts with better Unicode and mathematical symbol support."""
        try:
            # Try to register DejaVu fonts which have excellent Unicode support
            import reportlab.rl_config as rl_config
            rl_config.TTFSearchPath.append('/usr/share/fonts/truetype/dejavu')
            rl_config.TTFSearchPath.append('/usr/share/fonts/TTF')
            rl_config.TTFSearchPath.append('/System/Library/Fonts')
            rl_config.TTFSearchPath.append('/Library/Fonts')
            
            # Try common paths for DejaVu fonts
            possible_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/TTF/DejaVuSans.ttf',
                '/System/Library/Fonts/Arial Unicode.ttf',
                '/Library/Fonts/Arial Unicode.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                '/Library/Fonts/Helvetica.ttc'
            ]
            
            # Try to register DejaVu font if available
            for font_path in possible_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
                        logger.info(f"Registered DejaVu font from {font_path}")
                        break
                    except Exception as e:
                        logger.debug(f"Failed to register font from {font_path}: {e}")
                        continue
            
        except Exception as e:
            logger.debug(f"Font registration failed (not critical): {e}")

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
        # Use a font with better Unicode support for mathematical symbols
        problem_font = self.body_font
        if "DejaVu" in [self.body_font, "DejaVu"]:
            problem_font = "DejaVu"
        
        if "ProblemText" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="ProblemText",
                    parent=self.styles["Normal"],
                    alignment=TA_JUSTIFY,
                    fontName=problem_font,
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
            import matplotlib.font_manager as fm

            # Try to use a font with better mathematical symbol support
            try:
                # Try DejaVu Sans which has good Unicode support
                plt.rcParams['font.family'] = 'DejaVu Sans'
            except:
                # Fallback to default
                plt.rcParams['font.family'] = 'sans-serif'

            fig = plt.figure(figsize=(len(expression) * 0.2, 0.5))  # Dynamic sizing
            fig.patch.set_alpha(0.0)
            
            # Use a larger font size for better clarity
            text = fig.text(0.5, 0.5, f"${expression}$", fontsize=14, ha='center', va='center')
            plt.axis("off")
            
            # Create a buffer to save the image
            buffer = io.BytesIO()
            
            # Save with high DPI for better quality
            fig.savefig(buffer, format="png", bbox_inches="tight", 
                       pad_inches=0.1, dpi=300, 
                       transparent=True,  # Transparent background
                       facecolor='none',  # No face color
                       edgecolor='none')  # No edge color
            
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
            r'\leq': '≤',
            r'\geq': '≥',
            r'\neq': '≠',
            r'\le': '≤',
            r'\ge': '≥',
            r'\ne': '≠',
            r'\approx': '≈',
            r'\equiv': '≡',
            r'\cong': '≅',
            r'\sim': '∼',
            r'\propto': '∝',
            # Arithmetic symbols
            r'\times': '×',
            r'\div': '÷',
            r'\pm': '±',
            r'\mp': '∓',
            r'\cdot': '⋅',
            r'\bullet': '•',
            r'\ast': '∗',
            r'\star': '⋆',
            r'\oplus': '⊕',
            r'\ominus': '⊖',
            r'\otimes': '⊗',
            r'\oslash': '⊘',
            # Dots and ellipses
            r'\vdots': '⋮',
            r'\hdots': '⋯',
            r'\ddots': '⋱',
            r'\ldots': '...',
            r'\cdots': '⋯',
            # Set theory symbols
            r'\cap': '∩',
            r'\cup': '∪',
            r'\subset': '⊂',
            r'\supset': '⊃',
            r'\subseteq': '⊆',
            r'\supseteq': '⊇',
            r'\subsetneq': '⊊',
            r'\supsetneq': '⊋',
            r'\in': '∈',
            r'\notin': '∉',
            r'\ni': '∋',
            r'\emptyset': '∅',
            r'\varnothing': '∅',
            # Mathematical symbols
            r'\infty': '∞',
            r'\partial': '∂',
            r'\nabla': '∇',
            r'\sum': '∑',
            r'\prod': '∏',
            r'\int': '∫',
            r'\oint': '∮',
            r'\sqrt': '√',
            r'\angle': '∠',
            r'\perp': '⊥',
            r'\parallel': '∥',
            r'\triangle': '△',
            r'\square': '□',
            r'\diamond': '⋄',
            r'\circ': '∘',
            r'\bigcirc': '○',
            # Greek lowercase letters
            r'\alpha': 'α',
            r'\beta': 'β',
            r'\gamma': 'γ',
            r'\delta': 'δ',
            r'\epsilon': 'ε',
            r'\varepsilon': 'ε',
            r'\zeta': 'ζ',
            r'\eta': 'η',
            r'\theta': 'θ',
            r'\vartheta': 'ϑ',
            r'\iota': 'ι',
            r'\kappa': 'κ',
            r'\lambda': 'λ',
            r'\mu': 'μ',
            r'\nu': 'ν',
            r'\xi': 'ξ',
            r'\pi': 'π',
            r'\varpi': 'ϖ',
            r'\rho': 'ρ',
            r'\varrho': 'ϱ',
            r'\sigma': 'σ',
            r'\varsigma': 'ς',
            r'\tau': 'τ',
            r'\upsilon': 'υ',
            r'\phi': 'φ',
            r'\varphi': 'φ',
            r'\chi': 'χ',
            r'\psi': 'ψ',
            r'\omega': 'ω',
            # Greek uppercase letters
            r'\Alpha': 'Α',
            r'\Beta': 'Β',
            r'\Gamma': 'Γ',
            r'\Delta': 'Δ',
            r'\Epsilon': 'Ε',
            r'\Zeta': 'Ζ',
            r'\Eta': 'Η',
            r'\Theta': 'Θ',
            r'\Iota': 'Ι',
            r'\Kappa': 'Κ',
            r'\Lambda': 'Λ',
            r'\Mu': 'Μ',
            r'\Nu': 'Ν',
            r'\Xi': 'Ξ',
            r'\Pi': 'Π',
            r'\Rho': 'Ρ',
            r'\Sigma': 'Σ',
            r'\Tau': 'Τ',
            r'\Upsilon': 'Υ',
            r'\Phi': 'Φ',
            r'\Chi': 'Χ',
            r'\Psi': 'Ψ',
            r'\Omega': 'Ω',
            # Arrows
            r'\rightarrow': '→',
            r'\to': '→',
            r'\leftarrow': '←',
            r'\gets': '←',
            r'\leftrightarrow': '↔',
            r'\uparrow': '↑',
            r'\downarrow': '↓',
            r'\updownarrow': '↕',
            r'\nearrow': '↗',
            r'\searrow': '↘',
            r'\swarrow': '↙',
            r'\nwarrow': '↖',
            r'\Rightarrow': '⇒',
            r'\Leftarrow': '⇐',
            r'\Leftrightarrow': '⇔',
            r'\Uparrow': '⇑',
            r'\Downarrow': '⇓',
            r'\Updownarrow': '⇕',
            r'\mapsto': '↦',
            r'\longmapsto': '⟼',
            r'\longrightarrow': '⟶',
            r'\longleftarrow': '⟵',
            r'\longleftrightarrow': '⟷',
            # Logic symbols
            r'\land': '∧',
            r'\wedge': '∧',
            r'\lor': '∨',
            r'\vee': '∨',
            r'\lnot': '¬',
            r'\neg': '¬',
            r'\forall': '∀',
            r'\exists': '∃',
            r'\nexists': '∄',
            r'\top': '⊤',
            r'\bot': '⊥',
            r'\models': '⊨',
            r'\vdash': '⊢',
            r'\dashv': '⊣',
            # Brackets and parentheses  
            r'\lfloor': '⌊',
            r'\rfloor': '⌋',
            r'\lceil': '⌈',
            r'\rceil': '⌉',
            r'\langle': '⟨',
            r'\rangle': '⟩',
            r'\llbracket': '⟦',
            r'\rrbracket': '⟧',
            # Miscellaneous symbols
            r'\mid': '∣',
            r'\parallel': '∥',
            r'\nmid': '∤',
            r'\nparallel': '∦',
            r'\hbar': 'ℏ',
            r'\ell': 'ℓ',
            r'\wp': '℘',
            r'\Re': 'ℜ',
            r'\Im': 'ℑ',
            r'\aleph': 'ℵ',
            r'\beth': 'ℶ',
            r'\gimel': 'ℷ',
            r'\daleth': 'ℸ',
            r'\clubsuit': '♣',
            r'\diamondsuit': '♢',
            r'\heartsuit': '♡',
            r'\spadesuit': '♠',
        }
        
        # Replace LaTeX commands with Unicode symbols
        for latex_cmd, unicode_char in latex_to_unicode.items():
            # Use word boundaries to avoid partial matches
            # Escape special regex characters in the LaTeX command
            escaped_cmd = re.escape(latex_cmd)
            text = re.sub(r'(?<!\\)' + escaped_cmd, unicode_char, text)
        
        # Handle common mathematical formatting patterns
        # Convert subscripts and superscripts to more readable format
        text = re.sub(r'([A-Za-z0-9])_\{([^}]+)\}', r'\1\2', text)  # A_{i} -> Ai (simpler for PDF)
        text = re.sub(r'([A-Za-z0-9])_([A-Za-z0-9])', r'\1\2', text)  # A_i -> Ai (simpler for PDF)
        text = re.sub(r'([A-Za-z0-9])\^\{([^}]+)\}', r'\1^\2', text)  # A^{i} -> A^i
        text = re.sub(r'([A-Za-z0-9])\^([A-Za-z0-9])', r'\1^\2', text)  # A^i -> A^i
        
        # Clean up common LaTeX formatting issues
        text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)  # \text{something} -> something
        text = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', text)  # \mathrm{something} -> something
        text = re.sub(r'\\textbf\{([^}]+)\}', r'\1', text)  # \textbf{something} -> something
        text = re.sub(r'\\textit\{([^}]+)\}', r'\1', text)  # \textit{something} -> something
        
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
        
        # Handle problematic Unicode characters that appear as black squares
        # Extended list of problematic characters
        problematic_chars = {
            '\u25A0': ' ',  # Black Large Square
            '\u25A1': ' ',  # White Large Square
            '\u25AA': ' ',  # Black Small Square
            '\u25AB': ' ',  # White Small Square
            '\u2588': ' ',  # Full Block
            '\u2589': ' ',  # Left Seven Eighths Block
            '\u258A': ' ',  # Left Three Quarters Block
            '\u258B': ' ',  # Left Five Eighths Block
            '\u258C': ' ',  # Left Half Block
            '\u258D': ' ',  # Left Three Eighths Block
            '\u258E': ' ',  # Left One Quarter Block
            '\u258F': ' ',  # Left One Eighth Block
            '\u2590': ' ',  # Right Half Block
            '\u2591': ' ',  # Light Shade
            '\u2592': ' ',  # Medium Shade
            '\u2593': ' ',  # Dark Shade
            '\uFFFD': ' ',  # Replacement Character
            '\u00A0': ' ',  # Non-breaking space
            '\u2000': ' ',  # En quad
            '\u2001': ' ',  # Em quad
            '\u2002': ' ',  # En space
            '\u2003': ' ',  # Em space
            '\u2004': ' ',  # Three-per-em space
            '\u2005': ' ',  # Four-per-em space
            '\u2006': ' ',  # Six-per-em space
            '\u2007': ' ',  # Figure space
            '\u2008': ' ',  # Punctuation space
            '\u2009': ' ',  # Thin space
            '\u200A': ' ',  # Hair space
            '\u2028': ' ',  # Line separator
            '\u2029': ' ',  # Paragraph separator
            '\u202F': ' ',  # Narrow no-break space
            '\u205F': ' ',  # Medium mathematical space
            '\u3000': ' ',  # Ideographic space
        }
        
        for char, replacement in problematic_chars.items():
            text = text.replace(char, replacement)
        
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
            '&ndash;': '-',
            '&hellip;': '...',
            '&bull;': '•',
            '&middot;': '·',
            '&copy;': '©',
            '&reg;': '®',
            '&trade;': '™',
            '&deg;': '°',
            '&plusmn;': '±',
            '&times;': '×',
            '&divide;': '÷',
            '&sup2;': '²',
            '&sup3;': '³',
        }
        
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)
        
        # Fix common patterns from competitive programming problems
        # Handle case subscripts properly
        text = re.sub(r'\bcase([0-9]+)\b', r'case_\1', text)  # case1 → case_1
        text = re.sub(r'\boutput([0-9]+)\b', r'output_\1', text)  # output1 → output_1
        text = re.sub(r'\binput([0-9]+)\b', r'input_\1', text)  # input1 → input_1
        
        # Handle variable subscripts  
        text = re.sub(r'\b([A-Za-z])([0-9]+)\b', r'\1_\2', text)  # A1 → A_1 (but only standalone)
        
        # First handle patterns where letters get concatenated incorrectly
        # Be more specific to avoid false positives
        text = re.sub(r'\b([a-z]+)n([A-Z])n\b', r'\1_\2', text)  # casenTn → case_T
        text = re.sub(r'\b([A-Z])n([A-Z])n\b', r'\1_\2', text)  # AnNn → A_N  
        text = re.sub(r'\b([A-Z])n([a-z])n\b', r'\1_\2', text)  # Anin → A_i
        text = re.sub(r'\b([a-z]+)n([a-z])n\b', r'\1_\2', text)  # outputnin → output_i
        
        # Pattern: word_number_ → word_number (remove trailing underscore)
        text = re.sub(r'([a-zA-Z]+)_([0-9]+)_', r'\1_\2', text)
        
        # For PDF compatibility, use bracket notation for subscripts
        # Pattern: Letter_X_ → Letter[X] for better PDF compatibility
        text = re.sub(r'\b([A-Za-z]+)_([0-9]+)\b', r'\1[\2]', text)  # case_1 → case[1]
        text = re.sub(r'\b([A-Za-z])_([a-zA-Z])\b', r'\1[\2]', text)  # A_i → A[i]
        
        # Pattern: standalone _X_ → [X] (but not for words)
        text = re.sub(r'\b_([0-9]+)_\b', r'[\1]', text)
        text = re.sub(r'\b_([a-zA-Z])_\b', r'[\1]', text)
        
        # Fix double underscores
        text = re.sub(r'__+', '_', text)
        
        # Clean up leading/trailing underscores around spaces
        text = re.sub(r'_\s+', ' ', text)
        text = re.sub(r'\s+_+', ' ', text)
        
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

    def _process_text_content(self, text: str) -> List[str]:
        """Process text content to handle line breaks and formatting exactly like the original website."""
        if not text:
            return []
        
        # Clean up the text first
        text = text.strip()
        
        # Split the text into lines and analyze each line
        lines = text.split('\n')
        
        # Clean and filter lines
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line:  # Only keep non-empty lines
                clean_lines.append(line)
        
        if not clean_lines:
            return []
        
        # If we have very few lines, just return them as separate paragraphs
        if len(clean_lines) <= 3:
            return clean_lines
        
        # Advanced processing for complex content
        paragraphs = []
        current_paragraph = []
        
        i = 0
        while i < len(clean_lines):
            line = clean_lines[i]
            
            # Check if this line should be its own paragraph
            is_standalone = (
                # Format indicators
                line.lower().endswith(':') or
                line.lower().startswith('the input is given') or
                line.lower().startswith('output the answers') or
                line.lower().startswith('each case is given') or
                line.lower().startswith('here,') or
                # Single variables or short format lines
                re.match(r'^[A-Z]$', line.strip()) or  # Single letter like 'T'
                re.match(r'^[a-z]+[0-9]+$', line.strip()) or  # case1, output1
                re.match(r'^[a-z]+[A-Z]$', line.strip()) or  # caseT, outputT
                line.strip() in [':', '...', '⋮'] or
                # Mathematical or symbolic lines
                len(line.split()) == 1 and line.strip() in ['T', 'H', 'W', 'L', 'N', 'M', 'r', 'c']
            )
            
            # Check if this starts a format specification block
            is_format_start = any(indicator in line.lower() for indicator in [
                'following format:', 'given from standard input', 'answers in the following'
            ])
            
            if is_format_start:
                # Finish current paragraph
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                # Add the format description line
                paragraphs.append(line)
                
                # Look ahead for format specification lines
                j = i + 1
                format_lines = []
                while j < len(clean_lines):
                    next_line = clean_lines[j]
                    # Check if this looks like a format specification
                    if (len(next_line.split()) <= 6 and  # Short lines
                        (re.match(r'^[A-Z]+[0-9]*$', next_line.strip()) or  # T, case1, etc.
                         next_line.strip() in [':', '...', '⋮'] or
                         re.match(r'^[a-z]+[0-9]+$', next_line.strip()) or  # case1, output1
                         re.match(r'^[a-z]+[A-Z]$', next_line.strip()))):
                        format_lines.append(next_line)
                        j += 1
                    else:
                        break
                
                # Add format lines as a single code block content
                if format_lines:
                    paragraphs.append('FORMAT_BLOCK:' + '\n'.join(format_lines))
                    i = j - 1  # Continue from where we left off
                
            elif is_standalone:
                # Finish current paragraph
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                # Add this line as its own paragraph
                paragraphs.append(line)
                
            else:
                # Check if this line should start a new paragraph based on content change
                should_break = (
                    current_paragraph and  # We have existing content
                    (len(current_paragraph) >= 2 or  # Current paragraph is getting long
                     (line.lower().startswith(('for each', 'more precisely', 'note that', 
                                              'if it is', 'let (', 'output integer')) and
                      len(current_paragraph) >= 1))  # Semantic break indicators
                )
                
                if should_break:
                    # Finish current paragraph
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = [line]
                else:
                    # Add to current paragraph
                    current_paragraph.append(line)
            
            i += 1
        
        # Don't forget the last paragraph
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        # Clean up and validate paragraphs
        result = []
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:
                result.append(paragraph)
        
        return result

    def _add_text_with_math(self, story: List[Any], text: str, style: ParagraphStyle) -> None:
        """Add text to the story while rendering math blocks and handling format blocks.

        The function looks for ``$...$`` or ``$$...$$`` patterns.  Pieces of plain text
        are appended as :class:`Paragraph` objects, while the expressions
        themselves are rendered using :func:`_render_math` and inserted as
        images.  This keeps the surrounding text searchable and
        copy-able whilst still allowing mathematical notation.
        """
        
        # Check if this is a format block
        if text.startswith('FORMAT_BLOCK:'):
            format_content = text[13:]  # Remove 'FORMAT_BLOCK:' prefix
            # Render as code block with better formatting
            story.append(Spacer(1, 6))
            story.append(self._highlight_code(format_content, language="text"))
            story.append(Spacer(1, 6))
            return
        
        # First convert LaTeX symbols to Unicode or proper format
        text = self._convert_latex_symbols(text)
        
        # Improve spacing and formatting for better readability
        text = self._improve_text_formatting(text)
        
        # Handle special cases for mathematical content in PDFs
        # Replace problematic subscripts/superscripts with readable alternatives
        # This helps with font rendering issues
        text = re.sub(r'([A-Za-z])_(\d+)', r'\1[\2]', text)  # A_1 -> A[1]
        text = re.sub(r'([A-Za-z])_([a-zA-Z])', r'\1[\2]', text)  # A_i -> A[i]
        
        # Check if this is a single line that should be formatted specially
        is_single_variable = re.match(r'^[A-Z]$', text.strip())  # Single letters like 'T'
        is_format_line = (len(text.split()) <= 3 and 
                         (re.match(r'^[a-z]+[0-9]+$', text.strip()) or  # case1, output1
                          re.match(r'^[a-z]+[A-Z]$', text.strip()) or   # caseT, outputT
                          text.strip() in [':', '...', '⋮']))
        
        if is_single_variable or is_format_line:
            # Format as a centered, code-like element
            story.append(Spacer(1, 3))
            code_style = ParagraphStyle(
                name='FormatVariable',
                parent=self.styles['Code'],
                alignment=1,  # Center alignment
                fontSize=self.base_font_size + 1,
                spaceBefore=3,
                spaceAfter=3,
            )
            story.append(Paragraph(text, code_style))
            story.append(Spacer(1, 3))
            return
        
        pattern = re.compile(r"(\$\$?[^$]+\$\$?)")  # Match both $...$ and $$...$$
        parts = pattern.split(text)
        
        # If no math expressions, just add as paragraph with proper spacing
        if len(parts) == 1:
            story.append(Paragraph(text, style))
            story.append(Spacer(1, 4))  # Add consistent spacing between paragraphs
            return
        
        # Process text with math expressions
        for part in parts:
            if not part:
                continue
            if (part.startswith("$") and part.endswith("$")) or (part.startswith("$$") and part.endswith("$$")):
                # Extract expression, handling both $...$ and $$...$$
                if part.startswith("$$") and part.endswith("$$") and len(part) > 4:
                    expr = part[2:-2]
                elif part.startswith("$") and part.endswith("$") and len(part) > 2:
                    expr = part[1:-1]
                else:
                    # Not a valid math expression, treat as regular text
                    story.append(Paragraph(part, style))
                    continue
                    
                # Try to render math expression
                img_path = self._render_math(expr)
                if img_path and img_path.exists():
                    try:
                        # Get image dimensions for proper sizing
                        with Image.open(img_path) as pil_img:
                            width, height = pil_img.size
                        
                        # Scale image appropriately
                        max_width = 4 * inch
                        if width > max_width:
                            scale = max_width / width
                            display_width = max_width
                            display_height = height * scale
                        else:
                            display_width = width
                            display_height = height
                            
                        img = RLImage(str(img_path), width=display_width, height=display_height)
                        img.hAlign = "CENTER"
                        story.append(img)
                    except Exception as e:
                        logger.warning(f"Failed to add math image {img_path}: {e}")
                        # Fallback to text if image handling fails
                        story.append(Paragraph(f"[Math: {expr}]", style))
                else:
                    # Fallback to text if math rendering fails
                    # Apply LaTeX symbol conversion to the expression as well
                    converted_expr = self._convert_latex_symbols(expr)
                    story.append(Paragraph(f"[Math: {converted_expr}]", style))
            else:
                # Regular text - clean it up before adding
                clean_text = self._convert_latex_symbols(part)
                clean_text = self._improve_text_formatting(clean_text)
                if clean_text.strip():
                    story.append(Paragraph(clean_text, style))
        
        # Add spacing after the whole block
        story.append(Spacer(1, 4))
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
            # Use the new text processing method for better formatting
            paragraphs = self._process_text_content(statement)
            
            for paragraph in paragraphs:
                self._add_text_with_math(section, paragraph, self.styles["ProblemText"])

        input_spec = data.get("input_format") or data.get("input_specification") or ""
        if input_spec:
            self._add_heading(section, "Input", 1)
            # Check if this looks like a code block format
            if any(keyword in input_spec.lower() for keyword in ["format:", "given from", "following format"]):
                # Split description and format examples
                lines = [line.strip() for line in input_spec.split("\n") if line.strip()]
                format_started = False
                description_lines = []
                format_lines = []
                
                for line in lines:
                    # Look for format indicators
                    if any(indicator in line.lower() for indicator in ["format:", "given from", "following format"]):
                        format_started = True
                        description_lines.append(line)
                    elif format_started and (line.startswith(" ") or 
                                            len(line.split()) <= 5 or  # Short lines are likely format
                                            re.match(r'^[A-Z_][0-9]*$', line.strip()) or  # Variables like T, N, case1
                                            ':' in line or  # Lines with colons like ":" 
                                            line.strip() in ['...', ':', '⋮']):
                        # This looks like a format specification
                        format_lines.append(line)
                    else:
                        if format_started and format_lines:
                            # We've moved past the format section
                            format_started = False
                        description_lines.append(line)
                
                # Add description
                if description_lines:
                    description = "\n".join(description_lines)
                    paragraphs = self._process_text_content(description)
                    for paragraph in paragraphs:
                        self._add_text_with_math(section, paragraph, self.styles["ProblemText"])
                
                # Add format as code block
                if format_lines:
                    format_text = "\n".join(format_lines)
                    section.append(self._highlight_code(format_text, language="text"))
            else:
                # Regular text processing
                paragraphs = self._process_text_content(input_spec)
                
                for paragraph in paragraphs:
                    self._add_text_with_math(section, paragraph, self.styles["ProblemText"])

        output_spec = data.get("output_format") or data.get("output_specification") or ""
        if output_spec:
            self._add_heading(section, "Output", 1)
            # Check if this looks like a code block format
            if any(keyword in output_spec.lower() for keyword in ["format:", "answers in", "following format"]):
                # Split description and format examples
                lines = [line.strip() for line in output_spec.split("\n") if line.strip()]
                format_started = False
                description_lines = []
                format_lines = []
                
                for line in lines:
                    # Look for format indicators
                    if any(indicator in line.lower() for indicator in ["format:", "answers in", "following format"]):
                        format_started = True
                        description_lines.append(line)
                    elif format_started and (line.startswith(" ") or 
                                            len(line.split()) <= 5 or  # Short lines are likely format
                                            re.match(r'^[A-Z_][0-9]*$', line.strip()) or  # Variables like output1, outputT
                                            ':' in line or  # Lines with colons like ":" 
                                            line.strip() in ['...', ':', '⋮']):
                        # This looks like a format specification
                        format_lines.append(line)
                    else:
                        if format_started and format_lines:
                            # We've moved past the format section
                            format_started = False
                        description_lines.append(line)
                
                # Add description
                if description_lines:
                    description = "\n".join(description_lines)
                    paragraphs = self._process_text_content(description)
                    for paragraph in paragraphs:
                        self._add_text_with_math(section, paragraph, self.styles["ProblemText"])
                
                # Add format as code block
                if format_lines:
                    format_text = "\n".join(format_lines)
                    section.append(self._highlight_code(format_text, language="text"))
            else:
                # Regular text processing
                paragraphs = self._process_text_content(output_spec)
                
                for paragraph in paragraphs:
                    self._add_text_with_math(section, paragraph, self.styles["ProblemText"])

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
    # The following two helpers are light-weight wrappers kept for API
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
        # Implementation here

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