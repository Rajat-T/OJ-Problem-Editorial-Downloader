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
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
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
            from matplotlib import rc

            # Configure matplotlib to use LaTeX for rendering
            rc("text", usetex=True)
            rc("font", family="serif")

            # Create a figure for the math expression
            fig = plt.figure(figsize=(len(expression) * 0.2, 0.5))
            fig.patch.set_alpha(0.0)

            # Render the LaTeX expression
            text = fig.text(0.5, 0.5, f"${expression}$", fontsize=14, ha="center", va="center")
            plt.axis("off")

            # Save the rendered image to a buffer
            buffer = io.BytesIO()
            fig.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0.1, dpi=300, transparent=True)
            plt.close(fig)
            buffer.seek(0)

            # Save the buffer to a file in the image cache
            filename = f"math_{abs(hash(expression))}.png"
            path = self.image_cache_dir / filename
            path.write_bytes(buffer.getvalue())
            return path

        except Exception as exc:
            logger.warning("Unable to render math expression %s: %s", expression, exc)
            return None

    def _render_html_to_pdf(self, html_content: str, output_path: Path, base_url: str = None, 
                            css_styles: str = None) -> None:
        """Render HTML content to a PDF file using WeasyPrint with enhanced features.
        
        Args:
            html_content (str): HTML content to render
            output_path (Path): Path where PDF should be saved
            base_url (str, optional): Base URL for resolving relative links/images
            css_styles (str, optional): Additional CSS styles to apply
        """
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration

            # Create font configuration for better Unicode support
            font_config = FontConfiguration()
            
            # Default CSS for PDF optimization
            default_css = """
            @page {
                margin: 2cm;
                size: A4;
            }
            body {
                font-family: 'DejaVu Sans', Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.4;
                color: #000;
            }
            pre, code {
                font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
                background: #f5f5f5;
                padding: 0.5em;
                border: 1px solid #ddd;
            }
            """
            
            # Combine default and custom CSS
            combined_css = default_css
            if css_styles:
                combined_css += "\n" + css_styles
                
            css_objects = [CSS(string=combined_css)]
            
            # Create HTML object with optional base URL
            html_obj = HTML(string=html_content, base_url=base_url)
            
            # Generate PDF with optimizations
            html_obj.write_pdf(
                target=str(output_path),
                stylesheets=css_objects,
                font_config=font_config,
                presentational_hints=True,
                optimize_images=True
            )
            
            logger.info(f"Successfully rendered HTML to PDF: {output_path}")

        except ImportError:
            logger.error("WeasyPrint is not installed. Please install it to enable HTML-to-PDF rendering.")
            raise PDFGenerationError("WeasyPrint dependency not available", 
                                   original_exception=ImportError("WeasyPrint not installed"))
        except Exception as e:
            logger.error(f"Failed to render HTML to PDF: {e}")
            raise PDFGenerationError(f"HTML to PDF conversion failed: {str(e)}", original_exception=e)
    
    def create_webpage_pdf(self, url: str, output_filename: str = None, 
                          use_selenium: bool = False, custom_css: str = None) -> str:
        """
        Create a PDF directly from a webpage URL.
        
        This method fetches the webpage and converts it to PDF using WeasyPrint,
        preserving the original layout and styling.
        
        Args:
            url (str): URL of the webpage to convert
            output_filename (str, optional): Custom filename for the PDF. 
                                           If None, generates from URL
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            custom_css (str, optional): Additional CSS styles for PDF optimization
            
        Returns:
            str: Path to the generated PDF file
            
        Raises:
            PDFGenerationError: If PDF generation fails
            NetworkError: If webpage cannot be fetched
        """
        try:
            # Import scraper functionality
            from scraper.codeforces_scraper import CodeforcesScraper
            from scraper.atcoder_scraper import AtCoderScraper
            from scraper.spoj_scraper import SPOJScraper
            
            # Determine which scraper to use based on URL
            scraper = None
            if 'codeforces.com' in url.lower():
                scraper = CodeforcesScraper()
            elif 'atcoder.jp' in url.lower():
                scraper = AtCoderScraper()
            elif 'spoj.com' in url.lower():
                scraper = SPOJScraper()
            else:
                # Use Codeforces scraper as default (it has the most robust PDF download)
                scraper = CodeforcesScraper()
            
            # Generate output filename if not provided
            if output_filename is None:
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace('.', '_')
                path_part = parsed_url.path.replace('/', '_').strip('_')
                if path_part:
                    output_filename = f"{domain}_{path_part}.pdf"
                else:
                    output_filename = f"{domain}.pdf"
            
            # Ensure .pdf extension
            if not output_filename.endswith('.pdf'):
                output_filename += '.pdf'
            
            output_path = self.output_dir / output_filename
            
            # Use the base scraper's webpage-to-PDF functionality
            success = scraper.download_webpage_as_pdf(
                url=url,
                output_path=str(output_path),
                use_selenium=use_selenium,
                css_styles=custom_css
            )
            
            if not success:
                raise PDFGenerationError(f"Failed to generate PDF from webpage: {url}")
            
            return str(output_path)
            
        except Exception as e:
            if isinstance(e, PDFGenerationError):
                raise
            logger.error(f"Error creating webpage PDF from {url}: {e}")
            raise PDFGenerationError(f"Webpage PDF creation failed: {str(e)}", original_exception=e)

    def _convert_latex_symbols(self, text: str) -> str:
        """Convert LaTeX mathematical symbols to Unicode equivalents with enhanced coverage.
        
        This method provides comprehensive conversion of LaTeX commands to Unicode symbols,
        handling mathematical notation commonly found in competitive programming problems.
        Enhanced to preserve visual layout and mathematical meaning.
        """
        if not text:
            return text
            
        # Comprehensive dictionary of LaTeX commands to Unicode symbols
        # Organized by category for better maintainability
        latex_to_unicode = {
            # Comparison and relation operators
            r'\leq': '≤', r'\le': '≤', r'\leqslant': '≤',
            r'\geq': '≥', r'\ge': '≥', r'\geqslant': '≥',
            r'\neq': '≠', r'\ne': '≠', r'\not=': '≠',
            r'\approx': '≈', r'\thickapprox': '≈',
            r'\equiv': '≡', r'\cong': '≅', r'\sim': '∼', r'\simeq': '≃',
            r'\propto': '∝', r'\varpropto': '∝',
            r'\prec': '≺', r'\succ': '≻', r'\preceq': '⪯', r'\succeq': '⪰',
            r'\ll': '≪', r'\gg': '≫',
            
            # Arithmetic and binary operations
            r'\times': '×', r'\div': '÷', r'\pm': '±', r'\mp': '∓',
            r'\cdot': '⋅', r'\bullet': '•', r'\ast': '∗', r'\star': '⋆',
            r'\oplus': '⊕', r'\ominus': '⊖', r'\otimes': '⊗', r'\oslash': '⊘',
            r'\odot': '⊙', r'\circ': '∘', r'\bigcirc': '○',
            r'\dagger': '†', r'\ddagger': '‡', r'\amalg': '⨿',
            
            # Dots, ellipses and spacing
            r'\vdots': '⋮', r'\hdots': '⋯', r'\ddots': '⋱', r'\iddots': '⋰',
            r'\ldots': '…', r'\cdots': '⋯', r'\dots': '…',
            
            # Set theory and logic symbols  
            r'\cap': '∩', r'\cup': '∪', r'\bigcap': '⋂', r'\bigcup': '⋃',
            r'\subset': '⊂', r'\supset': '⊃', r'\subseteq': '⊆', r'\supseteq': '⊇',
            r'\subsetneq': '⊊', r'\supsetneq': '⊋', r'\varsubsetneq': '⊊', r'\varsupsetneq': '⊋',
            r'\in': '∈', r'\notin': '∉', r'\ni': '∋', r'\not\ni': '∌',
            r'\emptyset': '∅', r'\varnothing': '∅',
            r'\land': '∧', r'\wedge': '∧', r'\lor': '∨', r'\vee': '∨',
            r'\lnot': '¬', r'\neg': '¬', r'\top': '⊤', r'\bot': '⊥',
            r'\forall': '∀', r'\exists': '∃', r'\nexists': '∄',
            r'\models': '⊨', r'\vdash': '⊢', r'\dashv': '⊣',
            
            # Mathematical operators and functions
            r'\infty': '∞', r'\partial': '∂', r'\nabla': '∇',
            r'\sum': '∑', r'\prod': '∏', r'\coprod': '∐',
            r'\int': '∫', r'\iint': '∬', r'\iiint': '∭', r'\oint': '∮',
            r'\sqrt': '√', r'\angle': '∠', r'\measuredangle': '∡', r'\sphericalangle': '∢',
            r'\perp': '⊥', r'\parallel': '∥', r'\nparallel': '∦',
            r'\triangle': '△', r'\square': '□', r'\diamond': '⋄',
            r'\Box': '□', r'\Diamond': '◊', r'\clubsuit': '♣',
            r'\diamondsuit': '♢', r'\heartsuit': '♡', r'\spadesuit': '♠',
            
            # Greek lowercase letters (comprehensive)
            r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
            r'\epsilon': 'ε', r'\varepsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η',
            r'\theta': 'θ', r'\vartheta': 'ϑ', r'\iota': 'ι',
            r'\kappa': 'κ', r'\varkappa': 'ϰ', r'\lambda': 'λ', r'\mu': 'μ',
            r'\nu': 'ν', r'\xi': 'ξ', r'\pi': 'π', r'\varpi': 'ϖ',
            r'\rho': 'ρ', r'\varrho': 'ϱ', r'\sigma': 'σ', r'\varsigma': 'ς',
            r'\tau': 'τ', r'\upsilon': 'υ', r'\phi': 'φ', r'\varphi': 'ϕ',
            r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
            
            # Greek uppercase letters
            r'\Alpha': 'Α', r'\Beta': 'Β', r'\Gamma': 'Γ', r'\Delta': 'Δ',
            r'\Epsilon': 'Ε', r'\Zeta': 'Ζ', r'\Eta': 'Η', r'\Theta': 'Θ',
            r'\Iota': 'Ι', r'\Kappa': 'Κ', r'\Lambda': 'Λ', r'\Mu': 'Μ',
            r'\Nu': 'Ν', r'\Xi': 'Ξ', r'\Pi': 'Ο', r'\Rho': 'Ρ',
            r'\Sigma': 'Σ', r'\Tau': 'Τ', r'\Upsilon': 'Υ', r'\Phi': 'Φ',
            r'\Chi': 'Χ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
            
            # Arrows (comprehensive collection)
            r'\rightarrow': '→', r'\to': '→', r'\longrightarrow': '⟶',
            r'\leftarrow': '←', r'\gets': '←', r'\longleftarrow': '⟵',
            r'\leftrightarrow': '↔', r'\longleftrightarrow': '⟷',
            r'\uparrow': '↑', r'\downarrow': '↓', r'\updownarrow': '↕',
            r'\nearrow': '↗', r'\searrow': '↘', r'\swarrow': '↙', r'\nwarrow': '↖',
            r'\Rightarrow': '⇒', r'\Leftarrow': '⇐', r'\Leftrightarrow': '⇔',
            r'\Uparrow': '⇑', r'\Downarrow': '⇓', r'\Updownarrow': '⇕',
            r'\mapsto': '↦', r'\longmapsto': '⟼', r'\hookrightarrow': '↪',
            r'\hookleftarrow': '↩', r'\rightharpoonup': '⇀', r'\rightharpoondown': '⇁',
            r'\leftharpoonup': '↼', r'\leftharpoondown': '↽',
            
            # Brackets and delimiters
            r'\lfloor': '⌊', r'\rfloor': '⌋', r'\lceil': '⌈', r'\rceil': '⌉',
            r'\langle': '⟨', r'\rangle': '⟩', r'\llbracket': '⟦', r'\rrbracket': '⟧',
            r'\{': '{', r'\}': '}', r'\|': '∥',
            
            # Miscellaneous mathematical symbols
            r'\mid': '∣', r'\nmid': '∤', r'\shortmid': '∣',
            r'\hbar': 'ℏ', r'\ell': 'ℓ', r'\wp': '℘',
            r'\Re': 'ℜ', r'\Im': 'ℑ', r'\aleph': 'ℵ',
            r'\beth': 'ℶ', r'\gimel': 'ℷ', r'\daleth': 'ℸ',
            r'\prime': '′', r'\backprime': '‵', r'\sharp': '♯', r'\flat': '♭',
            r'\natural': '♮', r'\surd': '√',
            
            # Blackboard bold (double-struck) letters
            r'\mathbb{N}': 'ℕ', r'\mathbb{Z}': 'ℤ', r'\mathbb{Q}': 'ℚ',
            r'\mathbb{R}': 'ℝ', r'\mathbb{C}': 'ℂ', r'\mathbb{P}': 'ℙ',
            r'\mathbb{H}': 'ℍ', r'\mathbb{F}': '𝔽',
            
            # Additional operators and symbols
            r'\bigwedge': '⋀', r'\bigvee': '⋁', r'\biguplus': '⨄',
            r'\bigsqcup': '⨆', r'\bigotimes': '⨂', r'\bigoplus': '⨁',
            r'\bigodot': '⨀', r'\coprod': '∐',
            
            # Miscellaneous symbols for competitive programming
            r'\checkmark': '✓', r'\times': '×', r'\div': '÷',
            r'\deg': '°', r'\celsius': '℃', r'\ohm': 'Ω',
        }
        
        # Enhanced LaTeX command processing with proper word boundaries
        # Use negative lookbehind to avoid double-processing escaped backslashes
        for latex_cmd, unicode_char in latex_to_unicode.items():
            # Escape special regex characters in the LaTeX command
            escaped_cmd = re.escape(latex_cmd)
            # Use word boundaries and negative lookbehind for proper matching
            pattern = r'(?<!\\)' + escaped_cmd + r'(?![a-zA-Z])'
            text = re.sub(pattern, unicode_char, text)
        
        # Handle mathematical expressions and environments
        # Preserve equation environments but convert content
        equation_patterns = [
            (r'\\begin{equation}(.*?)\\end{equation}', r'\\1'),
            (r'\\begin{align}(.*?)\\end{align}', r'\\1'),
            (r'\\begin{eqnarray}(.*?)\\end{eqnarray}', r'\\1'),
            (r'\\[(.*?)\\]', r'\\1'),  # Display math \[...\]
            (r'\$\$(.*?)\$\$', r'\\1'),  # Display math $$...$$
        ]
        
        for pattern, replacement in equation_patterns:
            text = re.sub(pattern, replacement, text, flags=re.DOTALL)
        
        # Enhanced subscript and superscript handling for competitive programming
        # Handle complex subscripts with braces: A_{max} -> A[max], x_{i,j} -> x[i,j]
        text = re.sub(r'([A-Za-z0-9])_\{([^}]+)\}', r'\1[\2]', text)
        text = re.sub(r'([A-Za-z0-9])_([A-Za-z0-9]+)', r'\1[\2]', text)
        
        # Handle superscripts: A^{n} -> A^n, x^2 -> x^2  
        text = re.sub(r'([A-Za-z0-9])\^\{([^}]+)\}', r'\1^\2', text)
        text = re.sub(r'([A-Za-z0-9])\^([A-Za-z0-9]+)', r'\1^\2', text)
        
        # Clean up LaTeX text formatting commands
        text_formatting_commands = {
            r'\\text\{([^}]+)\}': r'\1',  # \text{something} -> something
            r'\\mathrm\{([^}]+)\}': r'\1',  # \mathrm{something} -> something  
            r'\\mathbf\{([^}]+)\}': r'\1',  # \mathbf{something} -> something
            r'\\textbf\{([^}]+)\}': r'\1',  # \textbf{something} -> something
            r'\\textit\{([^}]+)\}': r'\1',  # \textit{something} -> something
            r'\\emph\{([^}]+)\}': r'\1',   # \emph{something} -> something
            r'\\mathit\{([^}]+)\}': r'\1', # \mathit{something} -> something
            r'\\mathcal\{([^}]+)\}': r'\1', # \mathcal{something} -> something
            r'\\mathfrak\{([^}]+)\}': r'\1', # \mathfrak{something} -> something
            r'\\mathbb\{([^}]+)\}': r'\1',  # \mathbb{something} -> something (if not handled above)
        }
        
        for pattern, replacement in text_formatting_commands.items():
            text = re.sub(pattern, replacement, text)
        
        # Handle fractions with proper formatting for readability
        # \frac{a}{b} -> (a)/(b) for simple cases, or a/b for single characters
        def format_fraction(match):
            numerator, denominator = match.groups()
            # Simple single character fractions
            if len(numerator.strip()) == 1 and len(denominator.strip()) == 1:
                return f"{numerator}/{denominator}"
            # Complex fractions with parentheses
            else:
                return f"({numerator})/({denominator})"
        
        text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', format_fraction, text)
        
        # Handle roots and other mathematical functions
        text = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', text)  # √(content)
        text = re.sub(r'\\sqrt\[([^\]]+)\]\{([^}]+)\}', r'\1√(\2)', text)  # n√(content)
        
        # Handle binomial coefficients
        text = re.sub(r'\\binom\{([^}]+)\}\{([^}]+)\}', r'C(\1,\2)', text)
        
        # Handle spacing commands with appropriate Unicode spacing
        spacing_commands = {
            r'\\,': '\u2009',        # thin space
            r'\\:': '\u2005',        # medium space  
            r'\\;': '\u2004',        # thick space
            r'\\quad': '\u2003',     # em space
            r'\\qquad': '\u2003\u2003', # double em space
            r'\\!': '',             # negative thin space (remove)
            r'\\ ': ' ',            # normal space
        }
        
        for pattern, replacement in spacing_commands.items():
            text = re.sub(pattern, replacement, text)
        
        # Clean up remaining unrecognized LaTeX commands
        # First preserve common function names
        function_names = [
            'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
            'sinh', 'cosh', 'tanh', 'coth', 'sech', 'csch',
            'arcsin', 'arccos', 'arctan', 'arccot', 'arcsec', 'arccsc',
            'log', 'ln', 'lg', 'exp', 'max', 'min', 'sup', 'inf',
            'lim', 'limsup', 'liminf', 'det', 'gcd', 'lcm', 'mod'
        ]
        
        # Convert function commands to readable form
        for func in function_names:
            text = re.sub(f'\\\\{func}\\b', func, text)
        
        # Remove backslashes from unrecognized commands (but preserve the content)
        text = re.sub(r'\\([a-zA-Z]+)\b', r'\1', text)  # \command -> command
        
        return text

    def _sanitize_html_content(self, text: str) -> str:
        """Sanitize HTML content to fix malformed attributes and tags that cause ReportLab parsing errors."""
        if not text:
            return text
        
        # Remove malformed HTML content that contains invalid attributes
        # This prevents ReportLab paragraph parser errors
        
        # First, handle common AtCoder/competitive programming HTML patterns
        # Convert <pre> tags to properly formatted text blocks
        def replace_pre_tag(match):
            content = match.group(1)
            # Clean the content but preserve structure
            lines = content.split('\n')
            cleaned_lines = []
            for line in lines:
                # Remove excessive whitespace but preserve some indentation
                cleaned_line = re.sub(r'[ \t]+', ' ', line.rstrip())
                if cleaned_line.strip():  # Only add non-empty lines
                    cleaned_lines.append(cleaned_line)
            return '\n\n' + '\n'.join(cleaned_lines) + '\n\n'
        
        text = re.sub(r'<pre[^>]*>(.*?)</pre>', replace_pre_tag, text, flags=re.DOTALL)
        
        # Handle <var> tags - these should be converted to variable notation
        text = re.sub(r'<var[^>]*>(.*?)</var>', r'\1', text, flags=re.DOTALL)
        
        # Handle mathematical expressions and code formatting
        text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)
        
        # Convert line breaks to proper newlines BEFORE removing other tags
        text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
        
        # First, try to identify and remove problematic HTML tags entirely
        # Look for tags with invalid attribute syntax (spaces around =)
        text = re.sub(r'<[^>]*class\s*=\s*"[^"]*"[^>]*>', '', text)
        text = re.sub(r'<span[^>]*class\s*=\s*"[^"]*"[^>]*>', '', text)
        text = re.sub(r'</span>', '', text)
        
        # Remove any remaining malformed HTML tags with spaces around equals
        text = re.sub(r'<[^>]*\s=\s[^>]*>', '', text)
        
        # Clean up common problematic HTML patterns
        problematic_patterns = [
            r'<div[^>]*class\s*=\s*"[^"]*"[^>]*>',  # Malformed div tags
            r'<p[^>]*class\s*=\s*"[^"]*"[^>]*>',    # Malformed p tags
            r'<h[1-6][^>]*class\s*=\s*"[^"]*"[^>]*>', # Malformed heading tags
            r'<h\[\d+\]>[^<]*</h\[\d+\]>',          # Malformed heading tags like <h[3]>
            r'<h\[\d+\]>',                          # Opening malformed headings
            r'</h\[\d+\]>',                         # Closing malformed headings
            r'<section[^>]*>',  # Remove section tags
            r'</section>',
            r'<div[^>]*>',      # Remove all div tags for safety
            r'</div>',
            r'<hr\s*/?\s*>',   # Remove hr tags
        ]
        
        for pattern in problematic_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Convert remaining valid HTML elements to safe equivalents
        # Handle basic formatting that we want to preserve
        html_conversions = {
            r'<var>([^<]*)</var>': r'\1',  # Remove var tags but keep content
            r'<var>([^<]*)< / var>': r'\1',  # Handle broken var tags with spaces
            r'<var>([^<]*)<\s*/\s*var>': r'\1',  # Handle var tags with spaced closing
            r'<code>([^<]*)</code>': r'`\1`',  # Convert code tags to backticks
            r'<strong>([^<]*)</strong>': r'**\1**',  # Convert strong to markdown-style
            r'<b>([^<]*)</b>': r'**\1**',  # Convert bold to markdown-style
            r'<em>([^<]*)</em>': r'*\1*',  # Convert emphasis to markdown-style
            r'<i>([^<]*)</i>': r'*\1*',  # Convert italic to markdown-style
            r'<u>([^<]*)</u>': r'\1',  # Remove underline tags
            r'<h[1-6][^>]*>([^<]*)</h[1-6]>': r'\n\n=== \1 ===\n',  # Convert headings
            r'<p[^>]*>([^<]*)</p>': r'\1\n\n',  # Convert p tags to double newlines
            r'<li[^>]*>([^<]*)</li>': r'• \1\n',  # Convert list items to bullet points
            r'<ul[^>]*>': '',  # Remove ul tags
            r'</ul>': '\n',
            r'<ol[^>]*>': '',  # Remove ol tags
            r'</ol>': '\n',
        }
        
        for pattern, replacement in html_conversions.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove any remaining HTML tags that might cause issues
        text = re.sub(r'<[^>]+>', '', text)
        
        # Fix specific issues seen in competitive programming content
        # Handle LaTeX-like expressions that might appear
        text = re.sub(r'\\vdots', '⋮', text)  # Vertical dots
        text = re.sub(r'\\ldots', '…', text)  # Horizontal dots
        text = re.sub(r'\\cdots', '⋯', text)  # Centered dots
        
        # Clean up multiple newlines and spaces
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        return text.strip()

    def _improve_text_formatting(self, text: str) -> str:
        """Improve text formatting for better readability in PDFs."""
        if not text:
            return text
        
        # First sanitize HTML content to prevent ReportLab parsing errors
        text = self._sanitize_html_content(text)
        
        # Decode HTML entities first
        text = html.unescape(text)
        
        # Handle Unicode subscripts and superscripts first (before black square handling)
        unicode_subscripts = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4', '₅': '5', 
            '₆': '6', '₇': '7', '₈': '8', '₉': '9', 
            'ₐ': 'a', 'ₑ': 'e', 'ᵢ': 'i', 'ⱼ': 'j', 'ₖ': 'k', 'ₗ': 'l', 
            'ₘ': 'm', 'ₙ': 'n', 'ₒ': 'o', 'ₚ': 'p', 'ᵣ': 'r', 'ₛ': 's', 
            'ₜ': 't', 'ᵤ': 'u', 'ᵥ': 'v', 'ₓ': 'x', 'ᵧ': 'y', 'ᵦ': 'β'
        }
        
        unicode_superscripts = {
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
            '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', 
            'ᵃ': 'a', 'ᵇ': 'b', 'ᶜ': 'c', 'ᵈ': 'd', 'ᵉ': 'e', 'ᶠ': 'f',
            'ᵍ': 'g', 'ʰ': 'h', 'ⁱ': 'i', 'ʲ': 'j', 'ᵏ': 'k', 'ˡ': 'l',
            'ᵐ': 'm', 'ⁿ': 'n', 'ᵒ': 'o', 'ᵖ': 'p', 'ʳ': 'r', 'ˢ': 's',
            'ᵗ': 't', 'ᵘ': 'u', 'ᵛ': 'v', 'ʷ': 'w', 'ˣ': 'x', 'ʸ': 'y', 'ᶻ': 'z'
        }
        
        # Convert Unicode subscripts to bracket notation for better PDF compatibility
        for unicode_sub, ascii_sub in unicode_subscripts.items():
            # Look for patterns like A₁, case₁, etc.
            text = re.sub(r'([A-Za-z]+)' + re.escape(unicode_sub), r'\1[' + ascii_sub + ']', text)
            # Also handle standalone subscripts
            text = text.replace(unicode_sub, ascii_sub)
        
        # Convert Unicode superscripts to caret notation
        for unicode_sup, ascii_sup in unicode_superscripts.items():
            text = re.sub(r'([A-Za-z0-9]+)' + re.escape(unicode_sup), r'\1^' + ascii_sup, text)
            text = text.replace(unicode_sup, ascii_sup)
        
        # Handle black square characters with intelligent replacement
        # Pattern: case■1■ → case[1], A■i■ → A[i]
        text = re.sub(r'([A-Za-z]+)■([0-9A-Za-z]+)■', r'\1[\2]', text)
        text = re.sub(r'([A-Za-z])■([A-Za-z])■', r'\1[\2]', text)
        
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
        
        # Fix common patterns from competitive programming problems with enhanced intelligence
        # Handle case subscripts properly - be more conservative to avoid false positives
        text = re.sub(r'\bcase([0-9]+)\b', r'case_\1', text)  # case1 → case_1
        text = re.sub(r'\boutput([0-9]+)\b', r'output_\1', text)  # output1 → output_1
        text = re.sub(r'\binput([0-9]+)\b', r'input_\1', text)  # input1 → input_1
        text = re.sub(r'\btest([0-9]+)\b', r'test_\1', text)  # test1 → test_1
        text = re.sub(r'\bsample([0-9]+)\b', r'sample_\1', text)  # sample1 → sample_1
        
        # Handle variable subscripts - but be careful about valid words
        # Only apply to standalone mathematical variables (single letters)
        text = re.sub(r'\b([A-Za-z])([0-9]+)\b(?![a-zA-Z])', r'\1_\2', text)  # A1 → A_1 (but not for words like "A1B2")
        
        # Enhanced handling of corrupted concatenated patterns from web scraping
        # These patterns occur when text gets mangled during HTML parsing
        corruption_patterns = [
            (r'\b([a-z]+)n([A-Z])n\b', r'\1_\2'),  # casenTn → case_T
            (r'\b([A-Z])n([A-Z])n\b', r'\1_\2'),  # AnNn → A_N  
            (r'\b([A-Z])n([a-z]+)n\b', r'\1_\2'), # Anin → A_i
            (r'\b([a-z]+)n([a-z]+)n\b', r'\1_\2'), # outputnin → output_i
            (r'\b([A-Za-z]+)([0-9])([A-Za-z]+)([0-9])\b', r'\1\2_\3\4'), # case1T1 → case1_T1
        ]
        
        for pattern, replacement in corruption_patterns:
            text = re.sub(pattern, replacement, text)
        
        # Clean up multiple underscores and trailing underscores
        text = re.sub(r'_+', '_', text)  # Multiple underscores to single
        text = re.sub(r'([a-zA-Z]+)_([0-9]+)_+', r'\1_\2', text)  # Remove trailing underscores
        
        # For PDF compatibility, convert to bracket notation (better rendering)
        # Pattern: Letter_X → Letter[X] for better PDF compatibility and readability
        text = re.sub(r'\b([A-Za-z]+)_([0-9]+)\b', r'\1[\2]', text)  # case_1 → case[1]
        text = re.sub(r'\b([A-Za-z])_([a-zA-Z]+)\b', r'\1[\2]', text)  # A_max → A[max]
        text = re.sub(r'\b([A-Za-z])_([a-zA-Z])\b', r'\1[\2]', text)  # A_i → A[i]
        
        # Handle standalone subscript patterns
        text = re.sub(r'\b_([0-9]+)_\b', r'[\1]', text)  # _1_ → [1]
        text = re.sub(r'\b_([a-zA-Z]+)_\b', r'[\1]', text)  # _max_ → [max]
        
        # Enhanced mathematical notation cleanup
        # Handle mathematical ranges and constraints properly
        constraint_patterns = [
            (r'([0-9]+)\s*≤\s*([A-Za-z_\[\]]+)\s*≤\s*([0-9]+)', r'\1 ≤ \2 ≤ \3'),
            (r'([0-9]+)\s*≥\s*([A-Za-z_\[\]]+)\s*≥\s*([0-9]+)', r'\1 ≥ \2 ≥ \3'),
            (r'([0-9]+)\s*<\s*([A-Za-z_\[\]]+)\s*<\s*([0-9]+)', r'\1 < \2 < \3'),
            (r'([0-9]+)\s*>\s*([A-Za-z_\[\]]+)\s*>\s*([0-9]+)', r'\1 > \2 > \3'),
        ]
        
        for pattern, replacement in constraint_patterns:
            text = re.sub(pattern, replacement, text)
        
        # Fix spacing around mathematical operators
        operator_spacing = [
            (r'([A-Za-z0-9])\+([A-Za-z0-9])', r'\1 + \2'),
            (r'([A-Za-z0-9])-([A-Za-z0-9])', r'\1 - \2'),
            (r'([A-Za-z0-9])\*([A-Za-z0-9])', r'\1 × \2'),
            (r'([A-Za-z0-9])/([A-Za-z0-9])', r'\1 / \2'),
            (r'([A-Za-z0-9])=([A-Za-z0-9])', r'\1 = \2'),
        ]
        
        for pattern, replacement in operator_spacing:
            text = re.sub(pattern, replacement, text)
        
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

    def _process_text_content(self, text: str, preserve_lines: bool = False) -> List[str]:
        """Split text into paragraphs and detect format blocks with enhanced AtCoder pattern recognition.

        Parameters
        ----------
        text:
            Raw text content that may contain embedded newline characters.
        preserve_lines:
            If ``True`` single newlines are retained inside paragraphs.  When
            ``False`` (the default) single newlines are converted to spaces so
            that paragraphs flow naturally, matching the formatting on the
            original problem webpage.
        """
        if not text:
            return []

        text = text.strip()
        
        # Enhanced format block detection for AtCoder patterns
        if self._should_extract_format_blocks(text):
            return self._extract_format_blocks(text)
        
        if not preserve_lines:
            # Replace single newlines with spaces while keeping paragraph breaks
            text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

        # Split paragraphs on double newlines
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paragraphs
    
    def _should_extract_format_blocks(self, text: str) -> bool:
        """Determine if text contains format blocks that should be specially processed."""
        # Look for format indicators
        format_indicators = [
            'following format:', 'given from standard input', 'format:',
            'standard input in the following', 'input is given'
        ]
        
        text_lower = text.lower()
        has_format_indicator = any(indicator in text_lower for indicator in format_indicators)
        
        # Look for typical format patterns
        has_format_pattern = bool(re.search(r'\b(case[0-9T]+|output[0-9T]+)\b', text, re.IGNORECASE))
        
        # Look for variable definitions like "T\ncase1\ncase2"
        has_variable_sequence = bool(re.search(r'\n[A-Z]\n.*\ncase[0-9T]', text))
        
        return has_format_indicator or has_format_pattern or has_variable_sequence
    
    def _extract_format_blocks(self, text: str) -> List[str]:
        """Extract and process format blocks from AtCoder-style text."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return []
        
        result = []
        current_paragraph = []
        format_block = []
        in_format_block = False
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Check if this line indicates start of format specification
            if any(indicator in line_lower for indicator in 
                   ['following format:', 'format:', 'given from standard input']):
                # Save current paragraph if exists
                if current_paragraph:
                    result.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                # Add the format indicator line
                result.append(line)
                in_format_block = True
                continue
            
            # Check if we're in a format block
            if in_format_block:
                # Check if this looks like a format specification line
                if self._is_format_spec_line(line):
                    format_block.append(line)
                    continue
                else:
                    # End of format block
                    if format_block:
                        result.append(f"FORMAT_BLOCK:{chr(10).join(format_block)}")
                        format_block = []
                    in_format_block = False
                    # Continue processing this line as regular text
            
            # Regular text processing
            current_paragraph.append(line)
        
        # Handle remaining content
        if format_block:
            result.append(f"FORMAT_BLOCK:{chr(10).join(format_block)}")
        elif current_paragraph:
            result.append(' '.join(current_paragraph))
        
        return [item for item in result if item.strip()]
    
    def _is_format_spec_line(self, line: str) -> bool:
        """Determine if a line looks like a format specification."""
        line = line.strip()
        
        # Empty lines in format blocks
        if not line:
            return True
            
        # Single uppercase letters (T, N, M, etc.)
        if re.match(r'^[A-Z]$', line):
            return True
            
        # Format variables like case1, caseT, output1, outputT
        if re.match(r'^[a-z]+[0-9T]+$', line, re.IGNORECASE):
            return True
            
        # Mathematical notation like A₁, A₂, etc.
        if re.match(r'^[A-Z][₀-₉ᵢⱼₖₗₘₙₚᵣₛₜᵤᵥwₓᵧᵧ]+$', line):
            return True
            
        # Simple variable sequences like "A B C", "A₁ A₂ ... Aₙ"
        if re.match(r'^[A-Z][₀-₉ᵢⱼₖₗₘₙₚᵣₛₜᵤᵥwₓᵧᵧ]*\s+[A-Z][₀-₉ᵢⱼₖₗₘₙₚᵣₛₜᵤᵥwₓᵧᵧ]*', line):
            return True
            
        # Special symbols commonly used in format specs
        if line in [':', '...', '⋮', '⋯']:
            return True
            
        # Short lines with limited words (likely format specs)
        if len(line.split()) <= 3 and len(line) <= 20:
            # But exclude obvious sentences
            if not any(word in line.lower() for word in 
                      ['the', 'and', 'or', 'is', 'are', 'will', 'should', 'must']):
                return True
        
        return False

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

        # Apply text improvements first, then convert LaTeX symbols
        text = self._improve_text_formatting(text)
        text = self._convert_latex_symbols(text)
        
        # Preserve line breaks during formatting
        newline_placeholder = "<<<BR>>>"
        text = text.replace("\n", newline_placeholder)
        text = text.replace(newline_placeholder, '<br/>')
        
        # Enhanced format variable detection
        is_single_variable = re.match(r'^[A-Z]$', text.strip())  # Single letters like 'T', 'N'
        is_format_line = self._is_format_variable_line(text.strip())
        
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
            try:
                story.append(Paragraph(text, style))
                story.append(Spacer(1, 4))  # Add consistent spacing between paragraphs
                return
            except Exception as e:
                logger.error(f"ReportLab paragraph parsing error: {e}")
                logger.error(f"Problematic text: {text[:200]}...")
                
                # Fallback: try with further sanitized text
                try:
                    # Remove all HTML-like content as emergency fallback
                    fallback_text = re.sub(r'<[^>]*>', '', text)
                    fallback_text = html.unescape(fallback_text)
                    fallback_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', fallback_text)  # Remove control characters
                    story.append(Paragraph(fallback_text, style))
                    story.append(Spacer(1, 4))
                    return
                except Exception as e2:
                    logger.error(f"Fallback paragraph creation also failed: {e2}")
                    # Last resort: add as preformatted text
                    try:
                        story.append(Preformatted(text, self.styles.get("Code", style)))
                        story.append(Spacer(1, 4))
                        return
                    except Exception as e3:
                        logger.error(f"Preformatted text creation failed: {e3}")
                        # Skip this text entirely rather than crash
                        story.append(Paragraph("[Content could not be rendered due to formatting issues]", style))
                        story.append(Spacer(1, 4))
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
                    try:
                        story.append(Paragraph(part, style))
                    except Exception as e:
                        logger.warning(f"Failed to create paragraph for invalid math text: {e}")
                        try:
                            # Sanitize the text and try again
                            clean_part = re.sub(r'<[^>]*>', '', part)
                            clean_part = html.unescape(clean_part)
                            story.append(Paragraph(clean_part, style))
                        except Exception as e2:
                            logger.warning(f"Fallback paragraph for invalid math failed: {e2}")
                            # Use preformatted text
                            try:
                                story.append(Preformatted(part, self.styles.get("Code", style)))
                            except Exception as e3:
                                logger.warning(f"Preformatted text for invalid math failed: {e3}")
                                continue
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
                    try:
                        story.append(Paragraph(f"[Math: {converted_expr}]", style))
                    except Exception as e:
                        logger.warning(f"Failed to create math fallback paragraph: {e}")
                        try:
                            # Clean the math expression and try again
                            clean_expr = re.sub(r'<[^>]*>', '', converted_expr)
                            clean_expr = html.unescape(clean_expr)
                            story.append(Paragraph(f"[Math: {clean_expr}]", style))
                        except Exception as e2:
                            logger.warning(f"Math fallback paragraph creation failed: {e2}")
                            # Use preformatted text for math expressions that can't be rendered
                            try:
                                story.append(Preformatted(f"[Math: {expr}]", self.styles.get("Code", style)))
                            except Exception as e3:
                                logger.warning(f"Math preformatted text creation failed: {e3}")
                                # Skip problematic math content
                                continue
            else:
                # Regular text - make sure it's clean
                if part.strip():
                    try:
                        story.append(Paragraph(part, style))
                    except Exception as e:
                        logger.warning(f"Failed to create paragraph for text part: {e}")
                        logger.warning(f"Problematic text part: {part[:100]}...")
                        try:
                            # Try with sanitized content
                            clean_part = re.sub(r'<[^>]*>', '', part)
                            clean_part = html.unescape(clean_part)
                            clean_part = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_part)  # Remove control characters
                            story.append(Paragraph(clean_part, style))
                        except Exception as e2:
                            logger.warning(f"Fallback paragraph creation failed: {e2}")
                            # Use preformatted text as last resort
                            try:
                                story.append(Preformatted(part, self.styles.get("Code", style)))
                            except Exception as e3:
                                logger.warning(f"Preformatted text creation failed: {e3}")
                                # Skip problematic content rather than crash
                                story.append(Paragraph("[Text content could not be rendered]", style))
        
        # Add spacing after the whole block
        story.append(Spacer(1, 4))
        
    def _is_format_variable_line(self, text: str) -> bool:
        """Enhanced detection of format variable lines."""
        if not text:
            return False
            
        # Remove HTML tags for checking
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        
        # Check various format patterns
        patterns = [
            r'^[a-z]+[0-9]+$',                    # case1, output1, input1
            r'^[a-z]+[A-Z]$',                     # caseT, outputT, inputT  
            r'^[A-Z][\[\]][0-9A-Za-z]+[\[\]]$',   # A[1], A[i], etc.
            r'^[A-Z]\^[0-9A-Za-z]+$',             # A^1, A^i, etc.
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_text):
                return True
        
        # Check for short lines with limited complexity
        word_count = len(clean_text.split())
        if word_count <= 3 and len(clean_text) <= 20:
            # Special symbols
            if clean_text in [':', '...', '\u22ee', '\u22ef', '\u22f1']:
                return True
            # Simple variable combinations like "A B C", "X Y"
            if re.match(r'^[A-Z](\\s+[A-Z])*$', clean_text):
                return True
            # Avoid classifying obvious sentences
            if not any(word in clean_text.lower() for word in 
                      ['the', 'and', 'or', 'is', 'are', 'will', 'should', 'must', 'given', 'print']):
                return True
                
        return False
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
            problem.setdefault("scrape_date", datetime.now(timezone.utc).isoformat())
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
                            f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
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
                f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
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
