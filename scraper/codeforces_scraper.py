"""
Codeforces scraper for OJ Problem Editorial Downloader
Handles scraping of Codeforces problems and editorials
"""

import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

class CodeforcesScraper(BaseScraper):
    """
    Scraper for Codeforces platform
    """
    
    BASE_URL = "https://codeforces.com"
    PROBLEM_PATTERN = r"https://codeforces\.com/(?:contest|problemset/problem)/(\d+)/([A-Z]\d?)"
    BLOG_PATTERN = r"https://codeforces\.com/blog/entry/(\d+)"
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        """
        Initialize Codeforces scraper
        """
        super().__init__(headless, timeout)
        self.platform = "Codeforces"
    
    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is a valid Codeforces problem or blog URL
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid Codeforces URL
        """
        problem_match = re.match(self.PROBLEM_PATTERN, url)
        blog_match = re.match(self.BLOG_PATTERN, url)
        return bool(problem_match or blog_match)
    
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """
        Extract problem statement from Codeforces problem URL
        
        Args:
            url (str): Codeforces problem URL
            
        Returns:
            Dict[str, Any]: Standardized problem information
        """
        try:
            # Validate URL
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid Codeforces problem URL: {url}")
            
            contest_id, problem_id = match.groups()
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch problem page")
            
            # Extract problem title
            title_elem = soup.find('div', class_='title')
            title = ""
            if title_elem:
                title = title_elem.get_text(strip=True)
                # Remove problem ID from title if present
                title = re.sub(r'^[A-Z]\d?\.\s*', '', title)
            else:
                title = f"Problem {problem_id}"
            
            # Extract time and memory limits
            time_limit = ""
            memory_limit = ""
            header_elem = soup.find('div', class_='header')
            if header_elem:
                limits_text = header_elem.get_text()
                time_match = re.search(r'time limit per test(\d+(?:\.\d+)?)\s*seconds?', limits_text)
                memory_match = re.search(r'memory limit per test(\d+)\s*megabytes?', limits_text)
                
                if time_match:
                    time_limit = time_match.group(1) + ' seconds'
                if memory_match:
                    memory_limit = memory_match.group(1) + ' MB'
            
            # Extract problem statement
            problem_statement = ""
            statement_elem = soup.find('div', class_='problem-statement')
            if statement_elem:
                # Remove header and other non-statement elements
                for elem in statement_elem.find_all(['div'], class_=['header', 'input-specification', 'output-specification', 'sample-tests', 'note']):
                    elem.decompose()
                
                # Get the remaining content
                for script in statement_elem.find_all(["script", "style"]):
                    script.decompose()
                problem_statement = statement_elem.get_text(separator='\n', strip=True)
            
            # Extract input/output specifications
            input_format = ""
            output_format = ""
            
            input_elem = soup.find('div', class_='input-specification')
            if input_elem:
                input_format = input_elem.get_text(separator='\n', strip=True)
            
            output_elem = soup.find('div', class_='output-specification')
            if output_elem:
                output_format = output_elem.get_text(separator='\n', strip=True)
            
            # Extract constraints (from problem statement or notes)
            constraints = ""
            notes_elem = soup.find('div', class_='note')
            if notes_elem:
                constraints = notes_elem.get_text(separator='\n', strip=True)
            
            # Extract sample tests
            examples = []
            sample_elem = soup.find('div', class_='sample-tests')
            if sample_elem:
                inputs = sample_elem.find_all('div', class_='input')
                outputs = sample_elem.find_all('div', class_='output')
                
                for i, (inp, out) in enumerate(zip(inputs, outputs)):
                    inp_pre = inp.find('pre')
                    out_pre = out.find('pre')
                    
                    if inp_pre and out_pre:
                        examples.append({
                            'input': inp_pre.get_text(strip=True),
                            'output': out_pre.get_text(strip=True),
                            'explanation': ''
                        })
            
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
        Extract editorial information from Codeforces blog URL
        
        Args:
            url (str): Codeforces blog URL (editorial)
            
        Returns:
            Dict[str, Any]: Standardized editorial information
        """
        try:
            # Validate URL
            match = re.match(self.BLOG_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid Codeforces blog URL: {url}")
            
            blog_id = match.group(1)
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch editorial page")
            
            # Extract blog title
            title_elem = soup.find('div', class_='title')
            title = title_elem.get_text(strip=True) if title_elem else f"Editorial {blog_id}"
            
            # Extract editorial content
            editorial_content = ""
            
            # Look for the main content
            content_elem = soup.find('div', class_='ttypography')
            if content_elem:
                editorial_content = content_elem.get_text(separator='\n', strip=True)
            
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

