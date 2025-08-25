"""
AtCoder scraper for OJ Problem Editorial Downloader
Handles scraping of AtCoder problems and editorials
"""

import re
from typing import Dict, Any, Optional, List
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

class AtCoderScraper(BaseScraper):
    """
    Scraper for AtCoder platform
    """
    
    BASE_URL = "https://atcoder.jp"
    PROBLEM_PATTERN = r"https://atcoder\.jp/contests/([^/]+)/tasks/([^/]+)"
    EDITORIAL_PATTERN = r"https://atcoder\.jp/contests/([^/]+)/editorial"
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        """
        Initialize AtCoder scraper
        """
        super().__init__(headless, timeout)
        self.platform = "AtCoder"
    
    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is a valid AtCoder problem or editorial URL
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid AtCoder URL
        """
        problem_match = re.match(self.PROBLEM_PATTERN, url)
        editorial_match = re.match(self.EDITORIAL_PATTERN, url)
        return bool(problem_match or editorial_match)
    
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """
        Extract problem statement from AtCoder problem URL
        
        Args:
            url (str): AtCoder problem URL
            
        Returns:
            Dict[str, Any]: Standardized problem information
        """
        try:
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid AtCoder problem URL: {url}")

            _, task_id = match.groups()

            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch problem page")

            # Title
            title_elem = soup.find('span', class_='h2') or soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else f"Problem {task_id.upper()}"

            # Time and memory limits
            page_text = soup.get_text(" ", strip=True)
            time_limit = ""
            memory_limit = ""
            time_match = re.search(r'Time Limit:?\s*([0-9.]+)\s*(?:sec|s)', page_text, re.IGNORECASE)
            mem_match = re.search(r'Memory Limit:?\s*(\d+)\s*(?:MB|MiB)', page_text, re.IGNORECASE)
            if time_match:
                time_limit = f"{time_match.group(1)} seconds"
            if mem_match:
                memory_limit = f"{mem_match.group(1)} MB"

            # Problem statement container (prefer English)
            statement_elem = soup.find('div', id='task-statement')
            if not statement_elem:
                raise Exception("Problem statement not found")
            lang_div = statement_elem.find(class_='lang-en') or statement_elem.find(class_='lang-ja') or statement_elem

            problem_statement_parts: List[str] = []
            input_format = ""
            output_format = ""
            constraints = ""
            examples: List[Dict[str, str]] = []
            sample_inputs: List[str] = []
            sample_outputs: List[str] = []

            parts = lang_div.find_all('div', class_='part')
            for part in parts:
                heading_elem = part.find(['h3', 'h2'])
                heading = heading_elem.get_text(strip=True) if heading_elem else ""
                heading_lower = heading.lower()
                if heading_elem:
                    heading_elem.decompose()

                if 'sample' in heading_lower or 'example' in heading_lower:
                    table = part.find('table')
                    if table:
                        inp = out = ''
                        for row in table.find_all('tr'):
                            th = row.find('th')
                            pre = row.find('pre')
                            if th and pre:
                                th_text = th.get_text(strip=True).lower()
                                pre_text = pre.get_text('\n', strip=True)
                                if 'input' in th_text:
                                    inp = pre_text
                                elif 'output' in th_text:
                                    out = pre_text
                        if inp or out:
                            examples.append({'input': inp, 'output': out, 'explanation': ''})
                    else:
                        pre_tags = part.find_all('pre')
                        if len(pre_tags) == 1:
                            text = pre_tags[0].get_text('\n', strip=True)
                            if 'input' in heading_lower:
                                sample_inputs.append(text)
                            elif 'output' in heading_lower:
                                sample_outputs.append(text)
                        elif len(pre_tags) >= 2:
                            inp = pre_tags[0].get_text('\n', strip=True)
                            out = pre_tags[1].get_text('\n', strip=True)
                            examples.append({'input': inp, 'output': out, 'explanation': ''})
                    continue

                text = part.get_text(separator='\n', strip=True)
                if 'constraint' in heading_lower:
                    constraints = text
                elif 'input' in heading_lower:
                    input_format = text
                elif 'output' in heading_lower:
                    output_format = text
                else:
                    problem_statement_parts.append(text)

            for inp, out in zip(sample_inputs, sample_outputs):
                examples.append({'input': inp, 'output': out, 'explanation': ''})

            problem_statement = '\n\n'.join(part for part in problem_statement_parts if part)

            images = self.handle_images_for_pdf(lang_div, url)

            return self.create_standard_format(
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

        except Exception as e:
            logger.error(f"Failed to extract problem statement from {url}: {e}")
            return self.create_standard_format(title=f"Error: {str(e)}")
    
    def get_editorial(self, url: str) -> Dict[str, Any]:
        """
        Extract editorial information from AtCoder editorial URL
        
        Args:
            url (str): AtCoder editorial URL
            
        Returns:
            Dict[str, Any]: Standardized editorial information
        """
        try:
            match = re.match(self.EDITORIAL_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid AtCoder editorial URL: {url}")

            contest_id = match.group(1)

            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch editorial page")

            title_elem = soup.find('span', class_='h2') or soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else f"Editorial - Contest {contest_id}"

            content_container = (
                soup.find('div', id='main-container')
                or soup.find('div', id='editorial')
                or soup
            )
            lang_div = content_container.find(class_='lang-en') or content_container.find(class_='lang-ja') or content_container

            for tag in lang_div.find_all(['script', 'style']):
                tag.decompose()
            editorial_content = lang_div.get_text(separator='\n', strip=True)
            if not editorial_content:
                editorial_content = soup.get_text(separator='\n', strip=True)

            images = self.handle_images_for_pdf(lang_div, url)

            return self.create_standard_format(
                title=title,
                problem_statement=editorial_content,
                images=images,
            )

        except Exception as e:
            logger.error(f"Failed to extract editorial from {url}: {e}")
            return self.create_standard_format(title=f"Error: {str(e)}")