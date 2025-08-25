"""
AtCoder scraper for OJ Problem Editorial Downloader
Handles scraping of AtCoder problems and editorials with comprehensive error handling
"""

import re
from typing import Dict, Any, Optional, List
from .base_scraper import BaseScraper
import logging

# Import comprehensive error handling
from utils.error_handler import (
    URLValidationError, NetworkError, ContentMissingError, 
    handle_exception, ErrorRecovery, error_reporter
)

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
    
    @handle_exception
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """
        Extract problem statement from AtCoder problem URL with comprehensive error handling
        
        Args:
            url (str): AtCoder problem URL
            
        Returns:
            Dict[str, Any]: Standardized problem information
            
        Raises:
            URLValidationError: If URL format is invalid
            NetworkError: If network errors occur
            ContentMissingError: If problem content is not found
        """
        try:
            # Validate URL format
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise URLValidationError(f"Invalid AtCoder problem URL format: {url}", url)

            _, task_id = match.groups()
            contest_id = match.group(1)

            # Get page content with error handling
            soup = self.get_page_content(url)
            if not soup:
                raise ContentMissingError(f"Failed to fetch problem page: {url}", url)

            # Initialize result with defaults for graceful degradation
            result = {
                'title': f"Problem {task_id.upper()}",
                'problem_statement': '',
                'input_format': '',
                'output_format': '',
                'constraints': '',
                'examples': [],
                'time_limit': '',
                'memory_limit': '',
                'images': [],
                'platform': 'AtCoder',
                'url': url,
                'contest_id': contest_id,
                'task_id': task_id
            }

            # Extract title with graceful degradation
            try:
                title_elem = soup.find('span', class_='h2') or soup.find('h1')
                if title_elem:
                    result['title'] = self.clean_and_format_text(title_elem.get_text(strip=True))
                    logger.debug(f"Extracted title: {result['title']}")
                else:
                    logger.warning(f"Title not found for {url}, using default")
            except Exception as e:
                logger.warning(f"Error extracting title from {url}: {e}")

            # Extract time and memory limits with graceful degradation
            try:
                page_text = soup.get_text(" ", strip=True)
                time_match = re.search(r'Time Limit:?\s*([0-9.]+)\s*(?:sec|s)', page_text, re.IGNORECASE)
                mem_match = re.search(r'Memory Limit:?\s*(\d+)\s*(?:MB|MiB)', page_text, re.IGNORECASE)
                
                if time_match:
                    result['time_limit'] = f"{time_match.group(1)} seconds"
                    logger.debug(f"Extracted time limit: {result['time_limit']}")
                else:
                    logger.warning(f"Time limit not found for {url}")
                    
                if mem_match:
                    result['memory_limit'] = f"{mem_match.group(1)} MB"
                    logger.debug(f"Extracted memory limit: {result['memory_limit']}")
                else:
                    logger.warning(f"Memory limit not found for {url}")
            except Exception as e:
                logger.warning(f"Error extracting limits from {url}: {e}")

            # Extract problem statement with graceful degradation
            try:
                statement_elem = soup.find('div', id='task-statement')
                if not statement_elem:
                    logger.warning(f"Main problem statement container not found for {url}")
                    # Try alternative selectors
                    statement_elem = soup.find('div', class_='problem-statement') or soup.find('main')
                
                if statement_elem:
                    # Prefer English content
                    lang_div = (statement_elem.find(class_='lang-en') or 
                               statement_elem.find(class_='lang-ja') or 
                               statement_elem)
                    
                    if lang_div:
                        result.update(self._extract_problem_sections(lang_div, url))
                    else:
                        logger.warning(f"No language-specific content found for {url}")
                else:
                    logger.error(f"No problem statement found for {url}")
                    result['problem_statement'] = "Problem statement could not be extracted."
                    
            except Exception as e:
                logger.error(f"Error extracting problem content from {url}: {e}")
                result['problem_statement'] = f"Error extracting content: {str(e)}"

            # Extract images with graceful degradation
            try:
                if soup:
                    result['images'] = self.handle_images_for_pdf(soup, url)
                    logger.debug(f"Extracted {len(result['images'])} images from {url}")
            except Exception as e:
                logger.warning(f"Error extracting images from {url}: {e}")
                result['images'] = []

            # Apply error recovery sanitization
            result = ErrorRecovery.sanitize_content(result)
            
            # Create standardized format
            return self.create_standard_format(**result)

        except (URLValidationError, NetworkError, ContentMissingError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error extracting problem statement from {url}: {e}")
            # Return fallback content instead of failing completely
            return ErrorRecovery.create_fallback_content(url, e)
    
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