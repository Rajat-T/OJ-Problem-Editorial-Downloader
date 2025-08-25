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
            problem_statement = container.get_text("\n", strip=True)

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
                problem_statement=problem_statement,
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

