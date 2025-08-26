"""
Codeforces scraper for OJ Problem Editorial Downloader
Handles scraping of Codeforces problems and editorials
"""

import re
from typing import Dict, Any, List
from urllib.parse import urljoin
import logging

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class CodeforcesScraper(BaseScraper):
    """Scraper for Codeforces platform"""

    BASE_URL = "https://codeforces.com"
    PROBLEM_PATTERN = r"https://codeforces\.com/(?:contest|problemset/problem)/(\d+)/([A-Za-z0-9]+)"
    BLOG_PATTERN = r"https://codeforces\.com/blog/entry/(\d+)"

    def __init__(self, headless: bool = True, timeout: int = 30):
        super().__init__(headless=headless, timeout=timeout)
        self.platform = "Codeforces"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _replace_math_expressions(self, container) -> None:
        """Replace math related tags with LaTeX style strings.

        Codeforces uses a mixture of tags (`img.tex`, `span.math-tex`, `script`
        with `type="math/tex"`, etc.) to represent mathematical formulas. For a
        textual representation we replace these with their LaTeX contents so the
        generated PDFs retain the formula information.
        """
        if not container:
            return
        try:
            # Images containing formulas
            for img in container.find_all("img"):
                classes = " ".join(img.get("class", []))
                if "tex" in classes or "math" in classes:
                    latex = img.get("alt") or img.get("data-latex") or ""
                    if latex:
                        img.replace_with(f"${latex}$")
                    else:
                        # Try to extract from src if available
                        src = img.get("src", "")
                        if "tex" in src or "math" in src:
                            # Extract potential LaTeX from URL
                            import urllib.parse
                            decoded = urllib.parse.unquote(src)
                            # Look for common LaTeX patterns in the URL
                            if any(cmd in decoded for cmd in ['leq', 'geq', 'times', 'sum', 'int']):
                                img.replace_with(f"[math: {decoded}]")
                            else:
                                img.replace_with("[math formula]")
                        else:
                            img.replace_with("[math formula]")

            # Spans with LaTeX content
            for span in container.find_all("span"):
                classes = " ".join(span.get("class", []))
                if "tex" in classes or "math" in classes:
                    latex = span.get("data-latex") or span.get_text(strip=True)
                    if latex:
                        # Clean up the LaTeX content
                        latex = latex.strip()
                        if not latex.startswith('$') and not latex.endswith('$'):
                            span.replace_with(f"${latex}$")
                        else:
                            span.replace_with(latex)
                    else:
                        span.replace_with("[math]")

            # MathJax script tags
            for script in container.find_all("script", {"type": "math/tex"}):
                if script.string:
                    latex_content = script.string.strip()
                    script.replace_with(f"${latex_content}$")
                else:
                    script.replace_with("[math expression]")
                    
            # Handle inline math that might be in different formats
            for script in container.find_all("script", {"type": "math/tex; mode=display"}):
                if script.string:
                    latex_content = script.string.strip()
                    script.replace_with(f"$${latex_content}$$")
                else:
                    script.replace_with("[math expression]")
                    
            # Handle any remaining scripts that might contain math
            for script in container.find_all("script"):
                script_type = script.get("type", "")
                if "math" in script_type.lower() and script.string:
                    latex_content = script.string.strip()
                    script.replace_with(f"${latex_content}$")
                elif "math" in script_type.lower():
                    script.replace_with("[math]")
                    
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug(f"Error processing math expressions: {exc}")

    def _process_image(self, img_tag, base_url: str):  # type: ignore[override]
        """Override image processing to support theme specific attributes."""
        src = (
            img_tag.get("src")
            or img_tag.get("data-src")
            or img_tag.get("data-original")
            or img_tag.get("data-dark-src")
            or img_tag.get("data-light-src")
        )
        if not src and img_tag.get("srcset"):
            # take first item from srcset
            src = img_tag.get("srcset").split(",")[0].split()[0]

        if not src:
            return None

        if src.startswith("//"):
            img_url = "https:" + src
        else:
            img_url = urljoin(base_url, src)

        alt_text = img_tag.get("alt", "")
        title = img_tag.get("title", "")
        width = img_tag.get("width")
        height = img_tag.get("height")

        return {
            "url": img_url,
            "alt": self.clean_and_format_text(alt_text),
            "title": self.clean_and_format_text(title),
            "original_width": width,
            "original_height": height,
            "format": self._get_image_format(img_url),
        }

    # ------------------------------------------------------------------
    # Interface implementations
    # ------------------------------------------------------------------
    def is_valid_url(self, url: str) -> bool:
        problem_match = re.match(self.PROBLEM_PATTERN, url)
        blog_match = re.match(self.BLOG_PATTERN, url)
        return bool(problem_match or blog_match)

    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """Extract problem statement from Codeforces problem URL."""
        try:
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid Codeforces problem URL: {url}")

            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch problem page")

            statement_elem = soup.find("div", class_="problem-statement")
            if not statement_elem:
                raise Exception("Problem statement not found")

            self._replace_math_expressions(statement_elem)

            # Title
            title_elem = statement_elem.find("div", class_="title")
            title = title_elem.get_text(strip=True) if title_elem else match.group(2)
            title = re.sub(r"^[A-Za-z0-9]+\.\s*", "", title)

            # Time and memory limits
            time_limit = ""
            memory_limit = ""
            header_elem = statement_elem.find("div", class_="header")
            if header_elem:
                time_div = header_elem.find("div", class_="time-limit")
                mem_div = header_elem.find("div", class_="memory-limit")
                if time_div:
                    time_limit = re.sub(r"time limit per test", "", time_div.get_text(strip=True)).strip()
                if mem_div:
                    memory_limit = re.sub(r"memory limit per test", "", mem_div.get_text(strip=True)).strip()
                header_elem.decompose()

            # Input/output/notes/sample sections
            input_elem = statement_elem.find("div", class_="input-specification")
            output_elem = statement_elem.find("div", class_="output-specification")
            notes_elem = statement_elem.find("div", class_="note")
            sample_elem = statement_elem.find("div", class_="sample-tests")

            input_format = input_elem.get_text("\n", strip=True) if input_elem else ""
            output_format = output_elem.get_text("\n", strip=True) if output_elem else ""
            constraints = notes_elem.get_text("\n", strip=True) if notes_elem else ""

            # Remove sections from main statement
            for elem in [input_elem, output_elem, sample_elem, notes_elem]:
                if elem:
                    elem.decompose()

            # Process the statement content to clean HTML
            problem_statement_text = self._process_codeforces_content(statement_elem)
            
            # Sample tests
            examples: List[Dict[str, str]] = []
            if sample_elem:
                self._replace_math_expressions(sample_elem)
                inputs = sample_elem.find_all("div", class_="input")
                outputs = sample_elem.find_all("div", class_="output")
                for inp_div, out_div in zip(inputs, outputs):
                    inp_pre = inp_div.find("pre")
                    out_pre = out_div.find("pre")
                    inp_text = inp_pre.get_text("\n", strip=True) if inp_pre else ""
                    out_text = out_pre.get_text("\n", strip=True) if out_pre else ""
                    examples.append({"input": inp_text, "output": out_text, "explanation": ""})

            images = self.handle_images_for_pdf(statement_elem, url)

            return self.create_standard_format(
                title=title,
                problem_statement=problem_statement_text,  # Use processed text
                input_format=input_format,
                output_format=output_format,
                constraints=constraints,
                examples=examples,
                time_limit=time_limit,
                memory_limit=memory_limit,
                images=images,
            )

        except Exception as exc:
            logger.error(f"Failed to extract problem statement from {url}: {exc}")
            return self.create_standard_format(title=f"Error: {str(exc)}")

    def get_editorial(self, url: str) -> Dict[str, Any]:
        """Extract editorial information from Codeforces blog URL."""
        try:
            match = re.match(self.BLOG_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid Codeforces blog URL: {url}")

            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch editorial page")

            title_elem = soup.find("div", class_="title")
            title = title_elem.get_text(strip=True) if title_elem else f"Editorial {match.group(1)}"

            content_elem = soup.find("div", class_="ttypography") or soup
            self._replace_math_expressions(content_elem)

            for tag in content_elem.find_all(["script", "style"]):
                tag.decompose()

            editorial_content = content_elem.get_text("\n", strip=True)
            images = self.handle_images_for_pdf(content_elem, url)

            return self.create_standard_format(
                title=title,
                problem_statement=editorial_content,
                images=images,
            )

        except Exception as exc:
            logger.error(f"Failed to extract editorial from {url}: {exc}")
            return self.create_standard_format(title=f"Error: {str(exc)}")

    def download_problem_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download a Codeforces problem page directly as a PDF.
        
        This method downloads the webpage and converts it directly to PDF format,
        preserving the original layout and styling without scraping content.
        
        Args:
            url (str): Codeforces problem URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            ValueError: If URL is not a valid Codeforces problem URL
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid Codeforces problem URL: {url}")
        
        # Extract problem identifier for title
        match = re.match(self.PROBLEM_PATTERN, url)
        title = f"Codeforces Problem"
        if match:
            contest_id, problem_letter = match.groups()
            title = f"Codeforces Contest {contest_id} Problem {problem_letter}"
        
        # Codeforces-specific CSS for better PDF rendering
        codeforces_css = """
        /* Codeforces-specific PDF optimizations */
        .lang-chooser, .lang-dropdown,
        .roundbox .header .right,
        .second-level-menu, .header .menu,
        .footer, #footer,
        .sidebar, .right-sidebar,
        .social, .sharing,
        .contest-nav, .contest-header,
        .datatable .top, .datatable .bottom,
        .pagination, .page-index {
            display: none !important;
        }
        
        /* Improve problem statement readability */
        .problem-statement .header {
            border-bottom: 2px solid #333;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        .problem-statement .title {
            font-size: 1.5em;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .time-limit, .memory-limit,
        .input-file, .output-file {
            font-style: italic;
            color: #666;
            margin: 0.2em 0;
        }
        
        .section-title {
            font-weight: bold;
            color: #34495e;
            margin-top: 1em;
            margin-bottom: 0.5em;
        }
        
        .sample-tests .section-title {
            background: #ecf0f1;
            padding: 0.3em;
            border-left: 4px solid #3498db;
        }
        
        .input, .output {
            margin-bottom: 1em;
        }
        
        .input .title, .output .title {
            font-weight: bold;
            margin-bottom: 0.3em;
        }
        
        pre {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.25rem;
            padding: 0.75rem;
            margin: 0.5em 0;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }
        
        /* Math rendering improvements */
        .MathJax, .math, .tex {
            font-size: 1em;
        }
        
        /* Remove ratings and user-specific content */
        .user-rating, .rating,
        .contest-rating, .contribution,
        .user-info, .user-box {
            display: none !important;
        }
        """
        
        return self.download_webpage_as_pdf(
            url=url,
            output_path=output_path,
            title=title,
            use_selenium=use_selenium,
            css_styles=codeforces_css
        )
    
    def download_editorial_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download a Codeforces editorial/blog page directly as a PDF.
        
        Args:
            url (str): Codeforces blog/editorial URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            ValueError: If URL is not a valid Codeforces blog URL
        """
        match = re.match(self.BLOG_PATTERN, url)
        if not match:
            raise ValueError(f"Invalid Codeforces blog URL: {url}")
        
        # Extract blog ID for title
        blog_id = match.group(1)
        title = f"Codeforces Editorial {blog_id}"
        
        # Codeforces blog-specific CSS
        blog_css = """
        /* Codeforces blog-specific PDF optimizations */
        .lang-chooser, .second-level-menu,
        .header .menu, .footer,
        .sidebar, .right-sidebar,
        .social, .sharing, .vote,
        .comment-table, #comments,
        .blog-entry .info .right,
        .contribution, .rating {
            display: none !important;
        }
        
        /* Improve blog content readability */
        .blog-entry .title {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        .blog-entry .content {
            line-height: 1.6;
        }
        
        .blog-entry .content h1,
        .blog-entry .content h2,
        .blog-entry .content h3 {
            color: #34495e;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }
        
        /* Code blocks in editorials */
        .blog-entry .content pre,
        .blog-entry .content code {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.25rem;
            padding: 0.5rem;
            font-family: 'Courier New', monospace;
            font-size: 9pt;
        }
        
        /* Mathematical expressions */
        .MathJax, .math, .tex {
            font-family: 'Latin Modern Math', serif;
        }
        
        /* Remove user avatars and profile info */
        .user-link, .user-avatar,
        .handle, .user-rating {
            display: none !important;
        }
        """
        
        return self.download_webpage_as_pdf(
            url=url,
            output_path=output_path,
            title=title,
            use_selenium=use_selenium,
            css_styles=blog_css
        )
    
    def _process_codeforces_content(self, content_elem) -> str:
        """
        Process Codeforces HTML content and convert to clean text while preserving structure.
        
        Args:
            content_elem: BeautifulSoup element containing the content
            
        Returns:
            str: Cleaned and formatted text content
        """
        try:
            if not content_elem:
                return ""
            
            # Create a copy to avoid modifying the original
            from bs4 import BeautifulSoup
            content_copy = BeautifulSoup(str(content_elem), 'html.parser')
            
            # Remove script and style tags
            for tag in content_copy.find_all(['script', 'style']):
                tag.decompose()
            
            # Process math expressions first
            self._replace_math_expressions(content_copy)
            
            # Process different HTML elements appropriately
            self._process_html_elements_cf(content_copy)
            
            # Get the text content with proper spacing
            text_content = content_copy.get_text(separator='\n', strip=True)
            
            # Apply text processing and cleaning
            cleaned_text = self.clean_and_format_text(text_content)
            
            return cleaned_text
            
        except Exception as e:
            logger.error(f"Error processing Codeforces content: {e}")
            # Fallback to simple text extraction
            return content_elem.get_text(separator='\n', strip=True) if content_elem else ""
    
    def _process_html_elements_cf(self, soup) -> None:
        """
        Process HTML elements specific to Codeforces to improve text extraction.
        
        Args:
            soup: BeautifulSoup object to process
        """
        try:
            # Handle <div> tags with specific classes
            for div_tag in soup.find_all('div'):
                if div_tag.get('class'):
                    class_names = ' '.join(div_tag.get('class', []))
                    if any(cls in class_names for cls in ['problem-statement', 'header', 'title']):
                        # Keep these but remove the div wrapper
                        div_tag.unwrap()
            
            # Handle <pre> tags - preserve formatting but clean content
            for pre_tag in soup.find_all('pre'):
                pre_text = pre_tag.get_text(strip=False)  # Preserve internal spacing
                if pre_text:
                    pre_tag.replace_with(f"\n\n{pre_text.strip()}\n\n")
            
            # Handle headings - add emphasis
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                heading_text = heading.get_text(strip=True)
                if heading_text:
                    heading.replace_with(f"\n\n=== {heading_text} ===\n")
            
            # Handle paragraphs - ensure proper spacing
            for p_tag in soup.find_all('p'):
                p_text = p_tag.get_text(strip=True)
                if p_text:
                    p_tag.replace_with(f"\n{p_text}\n")
            
            # Handle line breaks
            for br_tag in soup.find_all('br'):
                br_tag.replace_with('\n')
            
            # Handle emphasis tags
            for em_tag in soup.find_all(['em', 'i']):
                em_text = em_tag.get_text(strip=True)
                if em_text:
                    em_tag.replace_with(f"*{em_text}*")
            
            for strong_tag in soup.find_all(['strong', 'b']):
                strong_text = strong_tag.get_text(strip=True)
                if strong_text:
                    strong_tag.replace_with(f"**{strong_text}**")
                    
        except Exception as e:
            logger.warning(f"Error processing Codeforces HTML elements: {e}")
