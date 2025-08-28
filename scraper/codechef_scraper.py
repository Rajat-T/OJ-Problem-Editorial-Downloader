"""
CodeChef scraper for OJ Problem Editorial Downloader

This module provides functionality to extract problem statements and editorials
from CodeChef platform with enhanced direct PDF generation capabilities.

CodeChef Features:
- Problem statements with detailed descriptions
- Sample input/output cases
- Editorial discussions and solutions
- Contest and practice problems
- Multiple programming languages support

The scraper supports both traditional content extraction and direct webpage-to-PDF
conversion optimized for LLM training with proper semantic markup and structure.

Example:
    >>> scraper = CodeChefScraper()
    >>> problem_data = scraper.get_problem_statement("https://www.codechef.com/problems/PROBLEM_CODE")
    >>> print(problem_data['title'])
    "Problem Title"
"""

import re
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, urljoin
import time

from bs4 import BeautifulSoup, Tag
from requests.exceptions import RequestException

from .base_scraper import BaseScraper
from utils.error_handler import (
    NetworkError, URLValidationError, ContentMissingError, CaptchaDetectedError,
    handle_exception, ErrorContext, ErrorRecovery
)

logger = logging.getLogger(__name__)


class CodeChefScraper(BaseScraper):
    """
    Scraper for extracting problem statements and editorials from CodeChef.
    
    CodeChef is a popular competitive programming platform with a wide variety
    of programming contests and practice problems. This scraper handles:
    
    - Regular contest problems
    - Practice problems 
    - Editorial discussions
    - Long and short contests
    - Cook-off and Lunchtime contests
    
    Features:
    - Direct PDF generation optimized for LLM training
    - Robust error handling and retry mechanisms
    - Support for both authenticated and public content
    - Rate limiting to respect server resources
    - Enhanced text extraction and formatting
    
    Attributes:
        DOMAIN (str): CodeChef domain
        RATE_LIMIT (float): Minimum seconds between requests
        TIMEOUT (int): Request timeout in seconds
    """
    
    DOMAIN = "www.codechef.com"
    RATE_LIMIT = 2.0  # CodeChef prefers slower requests
    TIMEOUT = 30
    
    def __init__(self, headless: bool = True, timeout: int = 30, rate_limit: float = 2.0):
        """
        Initialize CodeChef scraper with enhanced configuration.
        
        Args:
            headless (bool): Whether to run browser in headless mode
            timeout (int): Request timeout in seconds
            rate_limit (float): Minimum seconds between requests
        """
        super().__init__(headless=headless, timeout=timeout, rate_limit=rate_limit)
        
        # CodeChef-specific headers
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        logger.info(f"CodeChef scraper initialized. Rate limit: {rate_limit}s, Timeout: {timeout}s")
    
    def is_valid_url(self, url: str) -> bool:
        """
        Check if the URL is a valid CodeChef URL.
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid CodeChef URL, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
            
        try:
            parsed_url = urlparse(url.lower())
            
            # Check domain
            if 'codechef.com' not in parsed_url.netloc:
                return False
            
            # Check for valid CodeChef URL patterns
            valid_patterns = [
                r'/problems/[A-Za-z0-9_]+/?$',  # Problem URL (case insensitive)
                r'/[A-Za-z0-9_]+/problems/[A-Za-z0-9_]+/?$',  # Contest problem URL
                r'/discuss/.*',  # Editorial/discussion URL
            ]
            
            for pattern in valid_patterns:
                if re.search(pattern, parsed_url.path):
                    return True
                    
            return False
            
        except Exception as e:
            logger.debug(f"URL validation error for {url}: {e}")
            return False
    
    @handle_exception
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """
        Extract problem statement from CodeChef problem URL.
        
        Args:
            url (str): CodeChef problem URL
            
        Returns:
            Dict[str, Any]: Problem information with enhanced structure
            
        Raises:
            URLValidationError: If URL is invalid
            NetworkError: If network-related errors occur
            ContentMissingError: If problem content is not found
        """
        if not self.is_valid_url(url):
            raise URLValidationError(f"Invalid CodeChef URL: {url}", url)
        
        with ErrorContext(f"get_problem_statement", url=url):
            logger.info(f"Extracting problem statement from: {url}")
            
            try:
                soup = self.get_page_content(url)
                if not soup:
                    raise ContentMissingError("Could not fetch page content", url)
                
                # Extract problem title
                title = self._extract_title(soup, url)
                
                # Extract problem statement
                problem_statement = self._extract_problem_statement(soup)
                
                # Extract input/output format
                input_format, output_format = self._extract_io_format(soup)
                
                # Extract constraints
                constraints = self._extract_constraints(soup)
                
                # Extract examples
                examples = self._extract_examples(soup)
                
                # Extract time and memory limits
                time_limit, memory_limit = self._extract_limits(soup)
                
                # Extract images
                images = self._extract_images(soup, url)
                
                # Extract additional metadata
                metadata = self._extract_metadata(soup)
                
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
                    **metadata  # Include additional CodeChef-specific data
                )
                
                logger.info(f"Successfully extracted problem statement: {title}")
                return result
                
            except (URLValidationError, NetworkError, ContentMissingError):
                raise
            except Exception as e:
                logger.error(f"Unexpected error extracting problem from {url}: {e}")
                raise NetworkError(f"Failed to extract problem: {str(e)}", url, e)
    
    @handle_exception
    def get_editorial(self, url: str) -> Dict[str, Any]:
        """
        Extract editorial information from CodeChef discussion URL.
        
        Args:
            url (str): CodeChef editorial/discussion URL
            
        Returns:
            Dict[str, Any]: Editorial information
            
        Raises:
            URLValidationError: If URL is invalid
            NetworkError: If network-related errors occur
            ContentMissingError: If editorial content is not found
        """
        if not self.is_valid_url(url):
            raise URLValidationError(f"Invalid CodeChef editorial URL: {url}", url)
        
        with ErrorContext(f"get_editorial", url=url):
            logger.info(f"Extracting editorial from: {url}")
            
            try:
                soup = self.get_page_content(url)
                if not soup:
                    raise ContentMissingError("Could not fetch editorial content", url)
                
                # Extract title
                title = self._extract_editorial_title(soup, url)
                
                # Extract editorial content
                editorial_content = self._extract_editorial_content(soup)
                
                # Extract related problem info if available
                problem_info = self._extract_related_problem_info(soup)
                
                result = self.create_standard_format(
                    title=title,
                    problem_statement=editorial_content,
                    **problem_info
                )
                
                logger.info(f"Successfully extracted editorial: {title}")
                return result
                
            except (URLValidationError, NetworkError, ContentMissingError):
                raise
            except Exception as e:
                logger.error(f"Unexpected error extracting editorial from {url}: {e}")
                raise NetworkError(f"Failed to extract editorial: {str(e)}", url, e)
    
    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extract problem title from the page.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            url (str): Original URL for fallback
            
        Returns:
            str: Problem title
        """
        try:
            # Try multiple selectors for title
            title_selectors = [
                'h1.problem-title',
                'h1',
                '.problem-statement h1',
                '.main h1',
                'title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and title != "CodeChef":
                        return self.clean_and_format_text(title)
            
            # Fallback: extract from URL
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')
            if path_parts and len(path_parts) >= 2:
                problem_code = path_parts[-1]
                return f"Problem {problem_code.upper()}"
            
            return "CodeChef Problem"
            
        except Exception as e:
            logger.warning(f"Error extracting title: {e}")
            return "CodeChef Problem"
    
    def _extract_problem_statement(self, soup: BeautifulSoup) -> str:
        """
        Extract the main problem statement.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            str: Problem statement text
        """
        try:
            # Try multiple selectors for problem statement
            statement_selectors = [
                '.problem-statement',
                '.problem-statement-string',
                '.problem-description',
                '.prob',
                '.content .prose',
                '.problem-content'
            ]
            
            for selector in statement_selectors:
                statement_elem = soup.select_one(selector)
                if statement_elem:
                    # Remove unwanted elements
                    for unwanted in statement_elem.select('script, style, .hidden'):
                        unwanted.decompose()
                    
                    text = statement_elem.get_text('\n', strip=True)
                    if text and len(text) > 50:  # Ensure we have substantial content
                        return self.clean_and_format_text(text)
            
            # Fallback: try to get main content
            main_content = soup.select_one('.main-content, .content, main')
            if main_content:
                text = main_content.get_text('\n', strip=True)
                if text:
                    return self.clean_and_format_text(text)
            
            return "Problem statement not found"
            
        except Exception as e:
            logger.warning(f"Error extracting problem statement: {e}")
            return "Error extracting problem statement"
    
    def _extract_io_format(self, soup: BeautifulSoup) -> tuple[str, str]:
        """
        Extract input and output format descriptions.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            tuple[str, str]: Input format and output format
        """
        try:
            input_format = ""
            output_format = ""
            
            # Look for input/output sections
            sections = soup.find_all(['h3', 'h4', 'h5'], string=re.compile(r'input|output', re.I))
            
            for section in sections:
                section_text = section.get_text(strip=True).lower()
                next_elem = section.find_next_sibling()
                
                if next_elem:
                    content = next_elem.get_text('\n', strip=True)
                    content = self.clean_and_format_text(content)
                    
                    if 'input' in section_text:
                        input_format = content
                    elif 'output' in section_text:
                        output_format = content
            
            return input_format, output_format
            
        except Exception as e:
            logger.warning(f"Error extracting I/O format: {e}")
            return "", ""
    
    def _extract_constraints(self, soup: BeautifulSoup) -> str:
        """
        Extract constraints information.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            str: Constraints text
        """
        try:
            # Look for constraints section
            constraints_headers = soup.find_all(['h3', 'h4', 'h5'], string=re.compile(r'constraint', re.I))
            
            for header in constraints_headers:
                next_elem = header.find_next_sibling()
                if next_elem:
                    content = next_elem.get_text('\n', strip=True)
                    if content:
                        return self.clean_and_format_text(content)
            
            # Alternative: look for common constraint patterns
            constraint_patterns = [
                r'\d+\s*≤\s*[a-zA-Z]\s*≤\s*\d+',
                r'\d+\s*<=\s*[a-zA-Z]\s*<=\s*\d+',
                r'1\s*≤\s*[a-zA-Z].*≤.*\d+'
            ]
            
            all_text = soup.get_text()
            for pattern in constraint_patterns:
                matches = re.findall(pattern, all_text)
                if matches:
                    return '\n'.join(matches)
            
            return ""
            
        except Exception as e:
            logger.warning(f"Error extracting constraints: {e}")
            return ""
    
    def _extract_examples(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract sample input/output examples.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            List[Dict[str, str]]: List of examples with input/output pairs
        """
        try:
            examples = []
            
            # Look for example sections
            example_headers = soup.find_all(['h3', 'h4', 'h5'], string=re.compile(r'example|sample', re.I))
            
            for header in example_headers:
                # Try to find input/output pairs after the header
                current = header.find_next_sibling()
                input_text = ""
                output_text = ""
                
                while current and current.name not in ['h1', 'h2', 'h3', 'h4', 'h5']:
                    text = current.get_text('\n', strip=True)
                    
                    if 'input' in current.get_text().lower():
                        next_elem = current.find_next_sibling()
                        if next_elem:
                            input_text = next_elem.get_text('\n', strip=True)
                    elif 'output' in current.get_text().lower():
                        next_elem = current.find_next_sibling()
                        if next_elem:
                            output_text = next_elem.get_text('\n', strip=True)
                    
                    current = current.find_next_sibling()
                
                if input_text or output_text:
                    examples.append({
                        'input': self.clean_and_format_text(input_text),
                        'output': self.clean_and_format_text(output_text)
                    })
            
            # Alternative: look for pre/code blocks that might contain examples
            if not examples:
                code_blocks = soup.find_all(['pre', 'code'])
                for i in range(0, len(code_blocks) - 1, 2):
                    input_block = code_blocks[i]
                    output_block = code_blocks[i + 1] if i + 1 < len(code_blocks) else None
                    
                    if input_block and output_block:
                        input_text = input_block.get_text('\n', strip=True)
                        output_text = output_block.get_text('\n', strip=True)
                        
                        if input_text and output_text:
                            examples.append({
                                'input': self.clean_and_format_text(input_text),
                                'output': self.clean_and_format_text(output_text)
                            })
            
            return examples
            
        except Exception as e:
            logger.warning(f"Error extracting examples: {e}")
            return []
    
    def _extract_limits(self, soup: BeautifulSoup) -> tuple[str, str]:
        """
        Extract time and memory limits.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            tuple[str, str]: Time limit and memory limit
        """
        try:
            time_limit = ""
            memory_limit = ""
            
            # Look for limit information in various places
            limit_text = soup.get_text()
            
            # Time limit patterns
            time_patterns = [
                r'time\s+limit[:\s]*(\d+(?:\.\d+)?\s*(?:sec|second|s))',
                r'(\d+(?:\.\d+)?\s*(?:sec|second|s))\s+time',
                r'time[:\s]*(\d+(?:\.\d+)?\s*(?:sec|second|s))'
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, limit_text, re.I)
                if match:
                    time_limit = match.group(1)
                    break
            
            # Memory limit patterns
            memory_patterns = [
                r'memory\s+limit[:\s]*(\d+(?:\.\d+)?\s*(?:MB|KB|GB|mb|kb|gb))',
                r'(\d+(?:\.\d+)?\s*(?:MB|KB|GB|mb|kb|gb))\s+memory',
                r'memory[:\s]*(\d+(?:\.\d+)?\s*(?:MB|KB|GB|mb|kb|gb))'
            ]
            
            for pattern in memory_patterns:
                match = re.search(pattern, limit_text, re.I)
                if match:
                    memory_limit = match.group(1)
                    break
            
            return time_limit, memory_limit
            
        except Exception as e:
            logger.warning(f"Error extracting limits: {e}")
            return "", ""
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract and resolve image URLs from the problem.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            base_url (str): Base URL for resolving relative links
            
        Returns:
            List[str]: List of absolute image URLs
        """
        try:
            images = []
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                src = img.get('src')
                if src:
                    # Resolve relative URLs
                    if src.startswith('/'):
                        src = urljoin(base_url, src)
                    elif not src.startswith(('http://', 'https://')):
                        src = urljoin(base_url, src)
                    
                    images.append(src)
            
            return images
            
        except Exception as e:
            logger.warning(f"Error extracting images: {e}")
            return []
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract additional CodeChef-specific metadata.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            Dict[str, Any]: Additional metadata
        """
        try:
            metadata = {}
            
            # Extract problem author
            author_elem = soup.select_one('.problem-author, .author')
            if author_elem:
                metadata['author'] = self.clean_and_format_text(author_elem.get_text(strip=True))
            
            # Extract contest information
            contest_elem = soup.select_one('.contest-info, .contest-name')
            if contest_elem:
                metadata['contest'] = self.clean_and_format_text(contest_elem.get_text(strip=True))
            
            # Extract difficulty
            difficulty_elem = soup.select_one('.difficulty, .problem-difficulty')
            if difficulty_elem:
                metadata['difficulty'] = self.clean_and_format_text(difficulty_elem.get_text(strip=True))
            
            # Extract tags
            tag_elems = soup.select('.tag, .problem-tag')
            if tag_elems:
                tags = [self.clean_and_format_text(tag.get_text(strip=True)) for tag in tag_elems]
                metadata['tags'] = [tag for tag in tags if tag]
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Error extracting metadata: {e}")
            return {}
    
    def _extract_editorial_title(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extract editorial title from discussion page.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            url (str): Original URL for fallback
            
        Returns:
            str: Editorial title
        """
        try:
            # Try multiple selectors for editorial title
            title_selectors = [
                'h1',
                '.discussion-title',
                '.post-title',
                'title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and title != "CodeChef":
                        return self.clean_and_format_text(title)
            
            return "CodeChef Editorial"
            
        except Exception as e:
            logger.warning(f"Error extracting editorial title: {e}")
            return "CodeChef Editorial"
    
    def _extract_editorial_content(self, soup: BeautifulSoup) -> str:
        """
        Extract editorial content from discussion page.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            str: Editorial content
        """
        try:
            # Try multiple selectors for editorial content
            content_selectors = [
                '.discussion-content',
                '.post-content',
                '.editorial-content',
                '.main-content .content',
                '.main'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # Remove unwanted elements
                    for unwanted in content_elem.select('script, style, .hidden, .sidebar'):
                        unwanted.decompose()
                    
                    text = content_elem.get_text('\n', strip=True)
                    if text and len(text) > 100:  # Ensure we have substantial content
                        return self.clean_and_format_text(text)
            
            return "Editorial content not found"
            
        except Exception as e:
            logger.warning(f"Error extracting editorial content: {e}")
            return "Error extracting editorial content"
    
    def _extract_related_problem_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract information about the related problem from editorial page.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            Dict[str, Any]: Related problem information
        """
        try:
            info = {}
            
            # Look for problem links
            problem_links = soup.find_all('a', href=re.compile(r'/problems/'))
            if problem_links:
                for link in problem_links:
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    if href and text:
                        info['related_problem_url'] = urljoin('https://www.codechef.com', href)
                        info['related_problem_title'] = self.clean_and_format_text(text)
                        break
            
            return info
            
        except Exception as e:
            logger.warning(f"Error extracting related problem info: {e}")
            return {}
    
    def download_problem_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download a CodeChef problem page directly as a PDF with LLM optimization.
        
        This method downloads the webpage and converts it directly to PDF format,
        preserving the original layout and styling while optimizing for LLM training.
        
        Args:
            url (str): CodeChef problem URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            ValueError: If URL is not a valid CodeChef problem URL
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid CodeChef problem URL: {url}")
        
        # Extract problem identifier for title
        try:
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')
            if path_parts and len(path_parts) >= 2:
                problem_code = path_parts[-1]
                title = f"CodeChef Problem {problem_code.upper()}"
            else:
                title = "CodeChef Problem"
        except:
            title = "CodeChef Problem"
        
        # CodeChef-specific CSS for better PDF rendering with LLM optimization
        codechef_css = """
        /* CodeChef-specific PDF optimizations */
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
        
        /* Improve problem content readability */
        .problem-statement, .problem-statement-string {
            background: #f8f9fa;
            padding: 1.5em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
            page-break-inside: avoid;
        }
        
        .problem-statement::before,
        .problem-statement-string::before {
            content: "[PROBLEM_STATEMENT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 1em;
            font-weight: bold;
        }
        
        .problem-statement h1,
        .problem-statement h2,
        .problem-statement h3,
        .problem-title {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        .problem-statement h1::before,
        .problem-statement h2::before,
        .problem-statement h3::before,
        .problem-title::before {
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
            css_styles=codechef_css
        )
    
    def download_editorial_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download a CodeChef editorial page directly as a PDF with LLM optimization.
        
        Args:
            url (str): CodeChef editorial URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            ValueError: If URL is not a valid CodeChef editorial URL
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid CodeChef editorial URL: {url}")
        
        # Extract editorial identifier for title
        try:
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')
            if path_parts and len(path_parts) >= 2:
                editorial_id = path_parts[-1]
                title = f"CodeChef Editorial {editorial_id}"
            else:
                title = "CodeChef Editorial"
        except:
            title = "CodeChef Editorial"
        
        # CodeChef editorial-specific CSS with LLM optimization
        editorial_css = """
        /* CodeChef editorial-specific PDF optimizations */
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
        .discussion-content, .post-content, .editorial-content {
            background: #f8f9fa;
            padding: 1.5em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
            page-break-inside: avoid;
        }
        
        .discussion-content::before,
        .post-content::before,
        .editorial-content::before {
            content: "[EDITORIAL_CONTENT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 1em;
            font-weight: bold;
        }
        
        .discussion-content h1,
        .discussion-content h2,
        .discussion-content h3,
        .post-content h1,
        .post-content h2,
        .post-content h3,
        .editorial-content h1,
        .editorial-content h2,
        .editorial-content h3 {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        .discussion-content h1::before,
        .discussion-content h2::before,
        .discussion-content h3::before,
        .post-content h1::before,
        .post-content h2::before,
        .post-content h3::before,
        .editorial-content h1::before,
        .editorial-content h2::before,
        .editorial-content h3::before {
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