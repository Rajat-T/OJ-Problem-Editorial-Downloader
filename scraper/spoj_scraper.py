"""SPOJ scraper for OJ Problem Editorial Downloader."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SPOJScraper(BaseScraper):
    """Scraper implementation for the SPOJ platform."""

    BASE_URL = "https://www.spoj.com"
    PROBLEM_PATTERN = r"https://www\.spoj\.com/problems/([A-Za-z0-9_]+)/?"

    def __init__(self, headless: bool = True, timeout: int = 30) -> None:
        super().__init__(headless=headless, timeout=timeout)
        self.platform = "SPOJ"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def is_valid_url(self, url: str) -> bool:
        """Return ``True`` if *url* looks like a SPOJ problem URL."""

        return bool(re.match(self.PROBLEM_PATTERN, url))

    def _find_statement_container(self, soup) -> Any:
        """Locate the element containing the main problem statement."""

        selectors = [
            "div#problem-body",
            "div.prob-content",
            "div.problem-statement",
            "div#content",
            "table tr td",
        ]
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                return elem
        return soup

    # ------------------------------------------------------------------
    # Interface implementations
    # ------------------------------------------------------------------
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """Extract problem information from a SPOJ problem page."""

        try:
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid SPOJ problem URL: {url}")
            problem_code = match.group(1)

            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch problem page")

            # Title ---------------------------------------------------------
            title_elem = soup.find("h1")
            title = ""
            if title_elem:
                title = title_elem.get_text(strip=True)
                title = re.sub(rf"^{problem_code}\s*-\s*", "", title)
            if not title:
                title = f"Problem {problem_code}"

            # Main content --------------------------------------------------
            container = self._find_statement_container(soup)
            for tag in container.find_all(["script", "style"]):
                tag.decompose()

            # Retain the original HTML structure for rendering
            problem_statement_html = str(container)

            # Sections ------------------------------------------------------
            input_format = ""
            output_format = ""
            constraints = ""
            examples: List[Dict[str, str]] = []

            for heading in container.find_all(["h2", "h3", "h4", "b", "strong", "p"]):
                text = heading.get_text(strip=True).lower()
                next_tag = heading.find_next_sibling()
                if not next_tag:
                    continue
                if "input" in text and not input_format:
                    input_format = next_tag.get_text("\n", strip=True)
                elif "output" in text and not output_format:
                    output_format = next_tag.get_text("\n", strip=True)
                elif ("constraint" in text or "limit" in text) and not constraints:
                    constraints = next_tag.get_text("\n", strip=True)
                elif any(k in text for k in ["example", "sample"]):
                    pre_tags = next_tag.find_all("pre")
                    if not pre_tags and next_tag.name == "pre":
                        pre_tags = [next_tag]
                    for i in range(0, len(pre_tags), 2):
                        inp = pre_tags[i].get_text("\n", strip=True)
                        out = (
                            pre_tags[i + 1].get_text("\n", strip=True)
                            if i + 1 < len(pre_tags)
                            else ""
                        )
                        examples.append({"input": inp, "output": out, "explanation": ""})

            if not examples:
                pre_tags = container.find_all("pre")
                for i in range(0, len(pre_tags), 2):
                    inp = pre_tags[i].get_text("\n", strip=True)
                    out = (
                        pre_tags[i + 1].get_text("\n", strip=True)
                        if i + 1 < len(pre_tags)
                        else ""
                    )
                    examples.append({"input": inp, "output": out, "explanation": ""})

            # Limits --------------------------------------------------------
            page_text = soup.get_text()
            time_limit = ""
            memory_limit = ""
            m = re.search(r"Time limit:\s*([0-9.]+)\s*s", page_text, re.IGNORECASE)
            if m:
                time_limit = m.group(1) + "s"
            m = re.search(r"Memory limit:\s*(\d+)\s*MB", page_text, re.IGNORECASE)
            if m:
                memory_limit = m.group(1) + "MB"

            images = self.handle_images_for_pdf(container, url)

            # Categories / difficulty --------------------------------------
            categories: List[str] = []
            difficulty = ""
            tags_elem = soup.find(id="problem-tags") or soup.find("div", class_="problem-tags")
            if tags_elem:
                categories = [a.get_text(strip=True) for a in tags_elem.find_all("a")]

            diff_elem = soup.find(text=re.compile("Difficulty", re.IGNORECASE))
            if diff_elem:
                parent = diff_elem.parent
                difficulty = parent.get_text(strip=True)

            result = self.create_standard_format(
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
            result.update({"categories": categories, "difficulty": difficulty, "editorial_url": None})
            return result

        except Exception as exc:  # pragma: no cover - best effort
            logger.error(f"Failed to extract problem statement from {url}: {exc}")
            return self.create_standard_format(title=f"Error: {str(exc)}")

    def get_editorial(self, url: str) -> Dict[str, Any]:
        """SPOJ does not provide official editorials; return a placeholder."""

        logger.info("SPOJ does not provide official editorials.")
        return self.create_standard_format(
            title="Editorial not available",
            problem_statement=(
                "SPOJ problems generally do not include official editorials. "
                "Check community forums for discussions and solutions."
            ),
        )
    
    def download_problem_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download a SPOJ problem page directly as a PDF with LLM optimization.
        
        This method downloads the webpage and converts it directly to PDF format,
        preserving the original layout and styling while optimizing for LLM training.
        
        Args:
            url (str): SPOJ problem URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            ValueError: If URL is not a valid SPOJ problem URL
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid SPOJ problem URL: {url}")
        
        # Extract problem identifier for title
        try:
            match = re.match(self.PROBLEM_PATTERN, url)
            if match:
                problem_code = match.group(1)
                title = f"SPOJ Problem {problem_code.upper()}"
            else:
                title = "SPOJ Problem"
        except:
            title = "SPOJ Problem"
        
        # SPOJ-specific CSS for better PDF rendering with LLM optimization
        spoj_css = """
        /* SPOJ-specific PDF optimizations */
        .lang-chooser, .second-level-menu,
        .header .menu, .footer,
        .sidebar, .right-sidebar,
        .social, .sharing, .vote,
        .comment-table, #comments,
        .contribution, .rating,
        .user-link, .user-avatar,
        .handle, .user-rating,
        .login-reminder, .register-link,
        .advertisement, .ads-container,
        .cookie-notice, .gdpr-banner,
        .share-buttons, .social-share,
        .edit-button, .report-button,
        .breadcrumbs, .contest-navigation,
        .problem-tags, .problem-stats,
        .submit-button, .my-submissions,
        #problem-meta, .problem-info {
            display: none !important;
        }
        
        /* Improve problem content readability */
        #problem-body, .prob-content, .problem-statement {
            background: #f8f9fa;
            padding: 1.5em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
            page-break-inside: avoid;
        }
        
        #problem-body::before,
        .prob-content::before,
        .problem-statement::before {
            content: "[PROBLEM_STATEMENT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 1em;
            font-weight: bold;
        }
        
        #problem-body h1,
        #problem-body h2,
        #problem-body h3,
        .prob-content h1,
        .prob-content h2,
        .prob-content h3,
        .problem-statement h1,
        .problem-statement h2,
        .problem-statement h3 {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        #problem-body h1::before,
        #problem-body h2::before,
        #problem-body h3::before,
        .prob-content h1::before,
        .prob-content h2::before,
        .prob-content h3::before,
        .problem-statement h1::before,
        .problem-statement h2::before,
        .problem-statement h3::before {
            content: "[PROBLEM_TITLE] ";
            font-size: 0.7em;
            color: #666;
            margin-right: 0.5em;
        }
        
        /* Input/Output format sections */
        .input-format, .output-format {
            background: #e8f5e8;
            padding: 1em;
            margin: 1em 0;
            border: 1px solid #28a745;
            border-radius: 4px;
        }
        
        .input-format::before {
            content: "[INPUT_FORMAT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
            font-weight: bold;
        }
        
        .output-format::before {
            content: "[OUTPUT_FORMAT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
            font-weight: bold;
        }
        
        /* Constraints section */
        .constraints {
            background: #fff3cd;
            padding: 1em;
            margin: 1em 0;
            border: 1px solid #ffc107;
            border-radius: 4px;
        }
        
        .constraints::before {
            content: "[CONSTRAINTS]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
            font-weight: bold;
        }
        
        /* Sample input/output sections */
        .sample-input, .sample-output {
            background: #f8f9fa;
            padding: 1em;
            margin: 1em 0;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
            page-break-inside: avoid;
        }
        
        .sample-input::before {
            content: "[SAMPLE_INPUT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
            font-weight: bold;
        }
        
        .sample-output::before {
            content: "[SAMPLE_OUTPUT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
            font-weight: bold;
        }
        
        /* Code blocks */
        pre, code {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.25rem;
            padding: 0.75rem;
            margin: 0.5em 0;
            font-family: 'Courier New', monospace;
            font-size: 9pt;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }
        
        pre::before {
            content: "[CODE_BLOCK]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
        }
        
        /* Mathematical expressions */
        .MathJax, .math, .tex {
            font-family: 'Latin Modern Math', serif;
        }
        
        .MathJax::before,
        .math::before,
        .tex::before {
            content: "[MATH]";
            font-size: 0.8em;
            color: #666;
            margin-right: 0.3em;
        }
        
        /* Tables */
        table::before {
            content: "[TABLE]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
        }
        
        /* Lists */
        ul::before {
            content: "[LIST]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        ol::before {
            content: "[NUMBERED_LIST]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        /* Images */
        img::before {
            content: "[IMAGE: " attr(alt) "]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        /* Enhanced problem components for LLM training */
        .time-limit::before {
            content: "[TIME_LIMIT] ";
            font-weight: bold;
        }
        
        .memory-limit::before {
            content: "[MEMORY_LIMIT] ";
            font-weight: bold;
        }
        
        .example::before {
            content: "[EXAMPLE] ";
            font-weight: bold;
        }
        
        .note::before {
            content: "[NOTE] ";
            font-weight: bold;
        }
        
        .hint::before {
            content: "[HINT] ";
            font-weight: bold;
        }
        
        .source::before {
            content: "[SOURCE] ";
            font-weight: bold;
        }
        
        .tags::before {
            content: "[TAGS] ";
            font-weight: bold;
        }
        
        .difficulty::before {
            content: "[DIFFICULTY] ";
            font-weight: bold;
        }
        
        .author::before {
            content: "[AUTHOR] ";
            font-weight: bold;
        }
        """
        
        return self.download_webpage_as_pdf(
            url=url,
            output_path=output_path,
            title=title,
            use_selenium=use_selenium,
            css_styles=spoj_css
        )
    
    def download_editorial_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download a SPOJ editorial page directly as a PDF with LLM optimization.
        
        Since SPOJ doesn't have official editorials, this method will create a PDF
        with information about community resources.
        
        Args:
            url (str): SPOJ problem URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid SPOJ problem URL: {url}")
        
        # Extract problem identifier for title
        try:
            match = re.match(self.PROBLEM_PATTERN, url)
            if match:
                problem_code = match.group(1)
                title = f"SPOJ Problem {problem_code.upper()} - Editorial"
            else:
                title = "SPOJ Editorial"
        except:
            title = "SPOJ Editorial"
        
        # SPOJ editorial-specific CSS with LLM optimization
        editorial_css = """
        /* SPOJ editorial-specific PDF optimizations */
        .lang-chooser, .second-level-menu,
        .header .menu, .footer,
        .sidebar, .right-sidebar,
        .social, .sharing, .vote,
        .comment-table, #comments,
        .contribution, .rating,
        .user-link, .user-avatar,
        .handle, .user-rating,
        .login-reminder, .register-link,
        .advertisement, .ads-container,
        .cookie-notice, .gdpr-banner,
        .share-buttons, .social-share,
        .edit-button, .report-button,
        .breadcrumbs, .contest-navigation,
        .problem-tags, .problem-stats,
        .submit-button, .my-submissions {
            display: none !important;
        }
        
        /* Improve editorial content readability */
        #content, .main-content {
            background: #f8f9fa;
            padding: 1.5em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
            page-break-inside: avoid;
        }
        
        #content::before,
        .main-content::before {
            content: "[EDITORIAL_CONTENT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 1em;
            font-weight: bold;
        }
        
        #content h1,
        #content h2,
        #content h3,
        .main-content h1,
        .main-content h2,
        .main-content h3 {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        #content h1::before,
        #content h2::before,
        #content h3::before,
        .main-content h1::before,
        .main-content h2::before,
        .main-content h3::before {
            content: "[EDITORIAL_TITLE] ";
            font-size: 0.7em;
            color: #666;
            margin-right: 0.5em;
        }
        
        /* Code blocks */
        pre, code {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.25rem;
            padding: 0.75rem;
            margin: 0.5em 0;
            font-family: 'Courier New', monospace;
            font-size: 9pt;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }
        
        pre::before {
            content: "[CODE_BLOCK]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
        }
        
        /* Mathematical expressions */
        .MathJax, .math, .tex {
            font-family: 'Latin Modern Math', serif;
        }
        
        .MathJax::before,
        .math::before,
        .tex::before {
            content: "[MATH]";
            font-size: 0.8em;
            color: #666;
            margin-right: 0.3em;
        }
        
        /* Tables */
        table::before {
            content: "[TABLE]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.5em;
        }
        
        /* Lists */
        ul::before {
            content: "[LIST]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        ol::before {
            content: "[NUMBERED_LIST]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        /* Images */
        img::before {
            content: "[IMAGE: " attr(alt) "]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 0.3em;
        }
        """
        
        return self.download_webpage_as_pdf(
            url=url,
            output_path=output_path,
            title=title,
            use_selenium=use_selenium,
            css_styles=editorial_css
        )

