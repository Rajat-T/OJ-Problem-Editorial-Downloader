"""
SPOJ scraper for OJ Problem Editorial Downloader
Handles scraping of SPOJ problems and editorials
"""

import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

class SPOJScraper(BaseScraper):
    """
    Scraper for SPOJ (Sphere Online Judge) platform
    """
    
    BASE_URL = "https://www.spoj.com"
    PROBLEM_PATTERN = r"https://www\.spoj\.com/problems/([A-Z0-9_]+)/?.*"
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        """
        Initialize SPOJ scraper
        """
        super().__init__(headless, timeout)
        self.platform = "SPOJ"
    
    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is a valid SPOJ problem URL
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid SPOJ URL
        """
        problem_match = re.match(self.PROBLEM_PATTERN, url)
        return bool(problem_match)
    
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """
        Extract problem statement from SPOJ problem URL
        
        Args:
            url (str): SPOJ problem URL
            
        Returns:
            Dict[str, Any]: Standardized problem information
        """
        try:
            # Validate URL
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid SPOJ problem URL: {url}")
            
            problem_code = match.group(1)
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch problem page")
            
            # Extract problem title
            title = ""
            title_elem = soup.find('h1')
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                # Remove problem code from title if present
                title = re.sub(rf'^{problem_code}\s*-\s*', '', title_text)
            
            if not title:
                title = f"Problem {problem_code}"
            
            # Extract problem statement
            problem_statement = ""
            
            # SPOJ has different layouts, try multiple selectors
            statement_selectors = [
                'div#problem-body',
                'div.prob-content',
                'div.problem-statement',
                'table tr td'  # Fallback for older layout
            ]
            
            for selector in statement_selectors:
                statement_elem = soup.select_one(selector)
                if statement_elem:
                    # Clean up the content
                    for script in statement_elem.find_all(["script", "style"]):
                        script.decompose()
                    
                    # Remove navigation and other non-content elements
                    for elem in statement_elem.find_all(['div'], class_=['navigation', 'header', 'footer']):
                        elem.decompose()
                    
                    problem_statement = statement_elem.get_text(separator='\n', strip=True)
                    break
            
            # Extract additional information from the statement
            # SPOJ often includes constraints, input/output format in the statement
            input_format = ""
            output_format = ""
            constraints = ""
            
            # Try to parse sections from statement
            if problem_statement:
                sections = problem_statement.split('\n\n')
                for section in sections:
                    section_lower = section.lower()
                    if 'input' in section_lower and not input_format:
                        input_format = section
                    elif 'output' in section_lower and not output_format:
                        output_format = section
                    elif any(keyword in section_lower for keyword in ['constraint', 'limit']) and not constraints:
                        constraints = section
            
            # Extract time and memory limits (if visible on page)
            time_limit = ""
            memory_limit = ""
            
            # Look for limits in the page content
            page_text = soup.get_text()
            time_match = re.search(r'Time limit:\s*([0-9.]+)s', page_text, re.IGNORECASE)
            memory_match = re.search(r'Memory limit:\s*(\d+)MB', page_text, re.IGNORECASE)
            
            if time_match:
                time_limit = time_match.group(1) + 's'
            if memory_match:
                memory_limit = memory_match.group(1) + 'MB'
            
            # Handle images
            images = self.handle_images_for_pdf(soup, url)
            
            return self.create_standard_format(
                title=title,
                problem_statement=problem_statement,
                input_format=input_format,
                output_format=output_format,
                constraints=constraints,
                time_limit=time_limit,
                memory_limit=memory_limit,
                images=images
            )
            
        except Exception as e:
            logger.error(f"Failed to extract problem statement from {url}: {e}")
            return self.create_standard_format(title=f"Error: {str(e)}")
        """
        Extract problem information from SPOJ problem URL
        
        Args:
            url (str): SPOJ problem URL
            
        Returns:
            Dict[str, Any]: Problem information
        """
        try:
            # Validate URL
            match = re.match(self.PROBLEM_PATTERN, url)
            if not match:
                raise ValueError(f"Invalid SPOJ problem URL: {url}")
            
            problem_code = match.group(1)
            
            # Get page content
            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch problem page")
            
            # Extract problem title
            title = ""
            title_elem = soup.find('h1')
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                # Remove problem code from title if present
                title = re.sub(rf'^{problem_code}\s*-\s*', '', title_text)
            
            if not title:
                title = f"Problem {problem_code}"
            
            # Extract problem statement
            statement = ""
            
            # SPOJ has different layouts, try multiple selectors
            statement_selectors = [
                'div#problem-body',
                'div.prob-content',
                'div.problem-statement',
                'table tr td'  # Fallback for older layout
            ]
            
            for selector in statement_selectors:
                statement_elem = soup.select_one(selector)
                if statement_elem:
                    # Clean up the content
                    for script in statement_elem(["script", "style"]):
                        script.decompose()
                    
                    # Remove navigation and other non-content elements
                    for elem in statement_elem.find_all(['div'], class_=['navigation', 'header', 'footer']):
                        elem.decompose()
                    
                    statement = statement_elem.get_text(separator='\n', strip=True)
                    break
            
            # Extract additional information from the statement
            # SPOJ often includes constraints, input/output format in the statement
            input_format = ""
            output_format = ""
            constraints = ""
            
            # Try to parse sections from statement
            if statement:
                sections = statement.split('\n\n')
                for i, section in enumerate(sections):
                    section_lower = section.lower()
                    if 'input' in section_lower and not input_format:
                        input_format = section
                    elif 'output' in section_lower and not output_format:
                        output_format = section
                    elif any(keyword in section_lower for keyword in ['constraint', 'limit']) and not constraints:
                        constraints = section
            
            # Extract time and memory limits (if visible on page)
            limits = {}
            
            # Look for limits in the page content
            page_text = soup.get_text()
            time_match = re.search(r'Time limit:\s*([0-9.]+)s', page_text, re.IGNORECASE)
            memory_match = re.search(r'Memory limit:\s*(\d+)MB', page_text, re.IGNORECASE)
            
            if time_match:
                limits['time_limit'] = time_match.group(1) + 's'
            if memory_match:
                limits['memory_limit'] = memory_match.group(1) + 'MB'
            
            # Extract problem statistics (if available)
            stats = {}
            stats_table = soup.find('table', {'class': 'prob-stats'})
            if stats_table:
                rows = stats_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        stats[key] = value
            
            # Note: SPOJ doesn't typically have sample test cases on the problem page
            # or dedicated editorial pages like other platforms
            
            return {
                'platform': self.platform,
                'problem_code': problem_code,
                'title': title,
                'url': url,
                'statement': statement,
                'input_format': input_format,
                'output_format': output_format,
                'constraints': constraints,
                'limits': limits,
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Failed to extract problem info from {url}: {e}")
            return {}
    
    def get_editorial(self, url: str) -> Dict[str, Any]:
        """
        Extract editorial information from SPOJ
        
        Note: SPOJ doesn't have official editorials like other platforms.
        This method is included for interface consistency but may return limited info.
        
        Args:
            url (str): SPOJ URL
            
        Returns:
            Dict[str, Any]: Standardized editorial information (limited for SPOJ)
        """
        try:
            logger.warning("SPOJ doesn't typically have official editorials")
            
            # Try to extract any discussion or hints from the problem page
            soup = self.get_page_content(url)
            if not soup:
                raise Exception("Failed to fetch page")
            
            title = "SPOJ Editorial (Limited)"
            editorial_content = "SPOJ typically does not have official editorials. Consider looking for community solutions on forums or competitive programming websites."
            
            # Look for any hint or discussion elements
            hint_elem = soup.find(text=re.compile('hint', re.IGNORECASE))
            if hint_elem:
                hint_parent = hint_elem.find_parent()
                if hint_parent:
                    hint_content = hint_parent.get_text(separator='\n', strip=True)
                    editorial_content += f"\n\nHint found: {hint_content}"
            
            # Extract any additional notes or author comments
            notes_elem = soup.find('div', class_='problem-author')
            if notes_elem:
                notes_content = notes_elem.get_text(separator='\n', strip=True)
                editorial_content += f"\n\nAuthor Notes: {notes_content}"
            
            return self.create_standard_format(
                title=title,
                problem_statement=editorial_content
            )
            
        except Exception as e:
            logger.error(f"Failed to extract editorial from {url}: {e}")
            return self.create_standard_format(
                title="SPOJ Editorial (Error)",
                problem_statement="SPOJ typically does not have official editorials. Consider looking for community solutions on forums or competitive programming websites."
            )
