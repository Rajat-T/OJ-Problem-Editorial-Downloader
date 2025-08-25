"""
AtCoder scraper for OJ Problem Editorial Downloader
Handles scraping of AtCoder problems and editorials
"""

import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
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
            # Validate URL
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid AtCoder problem URL: {url}")
            
            contest_id, task_id = match.groups()
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch problem page")
            
            # Extract problem title
            title_elem = soup.find('span', class_='h2')
            title = title_elem.get_text(strip=True) if title_elem else f"Problem {task_id.upper()}"
            
            # Extract problem statement
            statement_elem = soup.find('div', {'id': 'task-statement'})
            problem_statement = ""
            if statement_elem:
                # Remove script and style elements
                for script in statement_elem.find_all(["script", "style"]):
                    script.decompose()
                problem_statement = statement_elem.get_text(separator='\n', strip=True)
            
            # Extract constraints
            constraints = ""
            constraints_elem = soup.find('div', string=re.compile('Constraints', re.IGNORECASE))
            if constraints_elem:
                constraints_parent = constraints_elem.find_parent()
                if constraints_parent:
                    constraints = constraints_parent.get_text(separator='\n', strip=True)
            
            # Extract input/output format
            input_format = ""
            output_format = ""
            
            io_sections = soup.find_all('div', class_='part')
            for section in io_sections:
                section_title = section.find('h3')
                if section_title:
                    title_text = section_title.get_text().lower()
                    content_elem = section.find('div', class_='lang-en')
                    if not content_elem:
                        content_elem = section
                    
                    content = content_elem.get_text(separator='\n', strip=True)
                    
                    if 'input' in title_text and not input_format:
                        input_format = content
                    elif 'output' in title_text and not output_format:
                        output_format = content
            
            # Extract sample inputs and outputs
            examples = []
            sample_sections = soup.find_all('div', class_='part')
            sample_inputs = []
            sample_outputs = []
            
            for section in sample_sections:
                section_title = section.find('h3')
                if section_title and 'Sample' in section_title.get_text():
                    pre_elem = section.find('pre')
                    if pre_elem:
                        content = pre_elem.get_text(strip=True)
                        if 'Input' in section_title.get_text():
                            sample_inputs.append(content)
                        elif 'Output' in section_title.get_text():
                            sample_outputs.append(content)
            
            # Pair inputs with outputs
            for i, (inp, out) in enumerate(zip(sample_inputs, sample_outputs)):
                examples.append({
                    'input': inp,
                    'output': out,
                    'explanation': ''
                })
            
            # Extract time and memory limits (AtCoder typically shows these in constraints)
            time_limit = ""
            memory_limit = ""
            
            if constraints:
                time_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:sec|second)', constraints, re.IGNORECASE)
                memory_match = re.search(r'(\d+)\s*(?:MB|megabyte)', constraints, re.IGNORECASE)
                
                if time_match:
                    time_limit = f"{time_match.group(1)} seconds"
                if memory_match:
                    memory_limit = f"{memory_match.group(1)} MB"
            
            # Handle images
            images = self.handle_images_for_pdf(soup, url)
            
            return self.create_standard_format(
                title=title,
                problem_statement=problem_statement,
                input_format=input_format,
                output_format=output_format,
                constraints=constraints,
                examples=examples,
                time_limit=time_limit,
                memory_limit=memory_limit,
                images=images
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
            # Validate URL
            match = re.match(self.EDITORIAL_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid AtCoder editorial URL: {url}")
            
            contest_id = match.group(1)
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch editorial page")
            
            # Extract title
            title = f"Editorial - Contest {contest_id}"
            
            # Extract editorial content
            editorial_content = ""
            content_divs = soup.find_all('div', class_='col-sm-12')
            
            for div in content_divs:
                # Look for editorial content
                text = div.get_text(separator='\n', strip=True)
                if any(keyword in text.lower() for keyword in ['editorial', 'solution', 'explanation']):
                    editorial_content += text + "\n\n"
            
            if not editorial_content:
                # Fallback: get main content
                main_content = soup.find('div', class_='row')
                if main_content:
                    editorial_content = main_content.get_text(separator='\n', strip=True)
            
            # Handle images
            images = self.handle_images_for_pdf(soup, url)
            
            return self.create_standard_format(
                title=title,
                problem_statement=editorial_content,
                images=images
            )
            
        except Exception as e:
            logger.error(f"Failed to extract editorial from {url}: {e}")
            return self.create_standard_format(title=f"Error: {str(e)}")