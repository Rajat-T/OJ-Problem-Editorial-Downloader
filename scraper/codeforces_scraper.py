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

            # Retain the original HTML structure for rendering
            problem_statement_html = str(statement_elem)

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
                problem_statement=problem_statement_html,  # Pass HTML content
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
