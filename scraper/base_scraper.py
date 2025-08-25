"""
Base scraper class for OJ Problem Editorial Downloader

This module provides the abstract base class and common functionality for all platform-specific
scrapers. It handles web scraping operations, error handling, rate limiting, and provides
a standardized interface for extracting problem statements and editorials from various
online judge platforms.

The BaseScraper class implements:
- Selenium WebDriver management with automatic driver setup
- Requests session configuration with retry logic
- Rate limiting to respect server resources
- Comprehensive error handling and recovery mechanisms
- Platform detection using URL patterns
- Text processing and image extraction utilities
- Network error handling with exponential backoff

Example:
    >>> from scraper.atcoder_scraper import AtCoderScraper
    >>> scraper = AtCoderScraper(headless=True, timeout=30)
    >>> problem_data = scraper.get_problem_statement("https://atcoder.jp/contests/abc123/tasks/abc123_a")
    >>> print(problem_data['title'])
    "A. Problem Title"

Note:
    All platform-specific scrapers must inherit from this class and implement
    the abstract methods: get_problem_statement(), get_editorial(), and is_valid_url().
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException, TimeoutException, NoSuchElementException,
    ElementNotInteractableException, SessionNotCreatedException
)
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import re
import socket
import signal
from urllib.parse import urlparse, urljoin
from PIL import Image
import io
import base64
from requests.exceptions import (
    RequestException, Timeout, ConnectionError, HTTPError, 
    TooManyRedirects, InvalidURL, ChunkedEncodingError
)
from urllib3.exceptions import MaxRetryError, NewConnectionError

# Import our error handling module
from utils.error_handler import (
    NetworkError, URLValidationError, ContentMissingError, CaptchaDetectedError,
    RateLimitError, ErrorDetector, ErrorContext, retry_on_error, handle_exception,
    ErrorRecovery, error_reporter
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract base class for all platform-specific scrapers.
    
    This class provides common functionality for web scraping operations including
    Selenium WebDriver management, HTTP session configuration, rate limiting,
    error handling, and standardized data extraction methods.
    
    All platform-specific scrapers must inherit from this class and implement
    the abstract methods for their respective platforms.
    
    Attributes:
        PLATFORM_PATTERNS (Dict[str, List[str]]): URL regex patterns for platform detection
        headless (bool): Whether to run browser in headless mode
        timeout (int): Request timeout in seconds
        rate_limit (float): Minimum seconds between requests
        session (requests.Session): Configured HTTP session with retry logic
        driver (webdriver.Chrome): Selenium WebDriver instance
        max_retries (int): Maximum number of retry attempts
        backoff_factor (float): Exponential backoff multiplier
        
    Example:
        >>> class MyPlatformScraper(BaseScraper):
        ...     def get_problem_statement(self, url: str) -> Dict[str, Any]:
        ...         # Implementation for specific platform
        ...         pass
        ...
        >>> scraper = MyPlatformScraper(headless=True, rate_limit=2.0)
        >>> data = scraper.get_problem_statement("https://example.com/problem/123")
    """
    
    # Platform patterns for URL detection
    PLATFORM_PATTERNS = {
        'AtCoder': [
            r'https://atcoder\.jp/contests/[^/]+/tasks/[^/]+',
            r'https://atcoder\.jp/contests/[^/]+/editorial'
        ],
        'Codeforces': [
            r'https://codeforces\.com/(?:contest|problemset/problem)/\d+/[A-Z]\d?',
            r'https://codeforces\.com/blog/entry/\d+'
        ],
        'SPOJ': [
            r'https://www\.spoj\.com/problems/[A-Z0-9_]+'
        ]
    }
    
    def __init__(self, headless: bool = True, timeout: int = 30, rate_limit: float = 1.0):
        """
        Initialize the base scraper with configuration options.
        
        Sets up HTTP session with retry logic, configures browser options,
        and initializes error tracking mechanisms.
        
        Args:
            headless (bool, optional): Whether to run browser in headless mode.
                Defaults to True for better performance.
            timeout (int, optional): Request timeout in seconds. Defaults to 30.
                Applied to both HTTP requests and browser operations.
            rate_limit (float, optional): Minimum seconds between requests.
                Defaults to 1.0 to respect server resources.
                
        Raises:
            NetworkError: If session configuration fails
            
        Example:
            >>> scraper = BaseScraper(headless=False, timeout=60, rate_limit=2.0)
            >>> scraper.timeout
            60
            
        Note:
            The session is configured with automatic retries for 5xx status codes
            and connection errors. User-Agent and other headers are set to mimic
            a real browser for better compatibility.
        """
        self.headless = headless
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.session = requests.Session()
        self.driver = None
        self.max_retries = 3
        self.backoff_factor = 2.0
        
        # Error tracking
        self.consecutive_failures = 0
        self.last_error_time = 0
        self.max_consecutive_failures = 5
        
        # Set up session with better error handling
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Configure session timeouts and retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    @retry_on_error(max_attempts=3, delay=2.0)
    def setup_driver(self) -> None:
        """
        Set up Selenium WebDriver with Chrome with comprehensive error handling
        """
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-extensions')
            
            # Set timeouts
            chrome_options.add_argument(f'--timeout={self.timeout}')
            
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as driver_error:
                logger.warning(f"ChromeDriverManager failed: {driver_error}. Trying system Chrome driver...")
                # Fallback to system Chrome driver
                self.driver = webdriver.Chrome(options=chrome_options)
            
            # Configure timeouts
            self.driver.set_page_load_timeout(self.timeout)
            self.driver.implicitly_wait(10)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("WebDriver setup completed successfully")
            
        except SessionNotCreatedException as e:
            error_msg = f"Failed to create WebDriver session: {str(e)}"
            logger.error(error_msg)
            raise NetworkError(error_msg, original_exception=e)
        except WebDriverException as e:
            error_msg = f"WebDriver error during setup: {str(e)}"
            logger.error(error_msg)
            raise NetworkError(error_msg, original_exception=e)
        except Exception as e:
            error_msg = f"Unexpected error setting up WebDriver: {str(e)}"
            logger.error(error_msg)
            raise NetworkError(error_msg, original_exception=e)
    
    def detect_platform(self, url: str) -> Optional[str]:
        """
        Detect the online judge platform from a given URL.
        
        Uses predefined regex patterns to identify which platform the URL belongs to.
        Supports AtCoder, Codeforces, and SPOJ platforms with various URL formats.
        
        Args:
            url (str): The URL to analyze for platform detection
            
        Returns:
            Optional[str]: Platform name if detected ('AtCoder', 'Codeforces', 'SPOJ'),
                          None if no platform pattern matches
                          
        Example:
            >>> scraper = BaseScraper()
            >>> scraper.detect_platform("https://atcoder.jp/contests/abc123/tasks/abc123_a")
            'AtCoder'
            >>> scraper.detect_platform("https://codeforces.com/contest/1234/problem/A")
            'Codeforces'
            >>> scraper.detect_platform("https://example.com/unknown")
            None
            
        Note:
            Platform detection is case-sensitive and requires exact pattern matching.
            URLs should be properly formatted with protocol (http/https).
        """
        try:
            for platform, patterns in self.PLATFORM_PATTERNS.items():
                for pattern in patterns:
                    if re.match(pattern, url.strip()):
                        logger.info(f"Detected platform: {platform} for URL: {url}")
                        return platform
            
            logger.warning(f"No platform detected for URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting platform for URL {url}: {e}")
            return None
    
    def _enforce_rate_limit(self) -> None:
        """
        Enforce rate limiting between requests
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def clean_and_format_text(self, text: str) -> str:
        """
        Clean and format text content for better readability
        
        Args:
            text (str): Raw text content
            
        Returns:
            str: Cleaned and formatted text
        """
        if not text:
            return ""
        
        try:
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text.strip())
            
            # Fix common formatting issues
            text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize paragraph breaks
            text = re.sub(r'\s*\n\s*', '\n', text)   # Clean line breaks
            
            # Remove HTML entities that might have been missed
            html_entities = {
                '&nbsp;': ' ',
                '&amp;': '&',
                '&lt;': '<',
                '&gt;': '>',
                '&quot;': '"',
                '&#39;': "'",
                '&hellip;': '...'
            }
            
            for entity, replacement in html_entities.items():
                text = text.replace(entity, replacement)
            
            # Clean mathematical expressions
            text = re.sub(r'\$\s*([^$]+)\s*\$', r'$\1$', text)  # Clean LaTeX
            
            # Handle LaTeX expressions that might not be properly wrapped
            # Look for common LaTeX commands and ensure proper spacing
            latex_commands = [
                r'\\leq', r'\\geq', r'\\neq', r'\\times', r'\\div', r'\\pm', r'\\mp',
                r'\\cdot', r'\\bullet', r'\\cap', r'\\cup', r'\\subset', r'\\supset',
                r'\\subseteq', r'\\supseteq', r'\\in', r'\\notin', r'\\emptyset',
                r'\\infty', r'\\partial', r'\\nabla', r'\\sum', r'\\prod', r'\\int',
                r'\\sqrt', r'\\alpha', r'\\beta', r'\\gamma', r'\\delta', r'\\epsilon',
                r'\\theta', r'\\lambda', r'\\mu', r'\\pi', r'\\sigma', r'\\phi', r'\\omega'
            ]
            
            # Ensure proper spacing around LaTeX commands
            for cmd in latex_commands:
                # Add space before and after if not already present
                text = re.sub(f'(\\w){cmd}(\\w)', f'\\1 {cmd} \\2', text)
                text = re.sub(f'(\\d){cmd}(\\d)', f'\\1 {cmd} \\2', text)
            
            # Clean up multiple spaces that might have been introduced
            text = re.sub(r'\s+', ' ', text)
            
            # Handle common mathematical constraint patterns
            # Example: "1 \leq T \leq 5" should have proper spacing
            constraint_patterns = [
                (r'(\d+)\s*\\leq\s*(\w+)\s*\\leq\s*(\d+)', r'\1 \\leq \2 \\leq \3'),
                (r'(\d+)\s*\\geq\s*(\w+)\s*\\geq\s*(\d+)', r'\1 \\geq \2 \\geq \3'),
                (r'(\d+)\s*\\times\s*(\d+)', r'\1 \\times \2'),
                (r'(\w+)\s*\\times\s*(\w+)', r'\1 \\times \2'),
            ]
            
            for pattern, replacement in constraint_patterns:
                text = re.sub(pattern, replacement, text)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning text: {e}")
            return text
    
    def handle_images_for_pdf(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """
        Extract and format images for PDF inclusion with comprehensive error handling
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            base_url (str): Base URL for resolving relative image URLs
            
        Returns:
            List[Dict[str, Any]]: List of image information dictionaries
        """
        images = []
        
        try:
            if not soup:
                logger.warning("No soup provided for image processing")
                return images
            
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                try:
                    img_info = self._process_image(img, base_url)
                    if img_info:
                        images.append(img_info)
                except Exception as e:
                    logger.warning(f"Error processing individual image: {e}")
                    continue  # Skip problematic images
            
            logger.info(f"Successfully processed {len(images)} images for PDF")
            return images
            
        except Exception as e:
            logger.error(f"Error handling images: {e}")
            return []  # Return empty list on error
    
    def _process_image(self, img_tag, base_url: str) -> Optional[Dict[str, Any]]:
        """
        Process individual image tag with error handling
        
        Args:
            img_tag: BeautifulSoup img tag
            base_url (str): Base URL for resolving relative URLs
            
        Returns:
            Optional[Dict[str, Any]]: Image information or None if processing fails
        """
        try:
            if not img_tag:
                return None
                
            src = img_tag.get('src')
            if not src:
                return None
            
            # Convert relative URLs to absolute
            try:
                if src.startswith('http'):
                    img_url = src
                elif src.startswith('//'):
                    img_url = 'https:' + src
                else:
                    img_url = urljoin(base_url, src)
                
                # Validate the URL
                parsed = urlparse(img_url)
                if not parsed.scheme or not parsed.netloc:
                    logger.warning(f"Invalid image URL: {img_url}")
                    return None
                    
            except Exception as e:
                logger.warning(f"Error processing image URL {src}: {e}")
                return None
            
            # Get image metadata safely
            alt_text = img_tag.get('alt', '')
            title = img_tag.get('title', '')
            width = img_tag.get('width')
            height = img_tag.get('height')
            
            # Validate dimensions if provided
            try:
                if width:
                    width = int(width)
                if height:
                    height = int(height)
            except (ValueError, TypeError):
                width = None
                height = None
            
            img_info = {
                'url': img_url,
                'alt': self.clean_and_format_text(alt_text) if alt_text else '',
                'title': self.clean_and_format_text(title) if title else '',
                'original_width': width,
                'original_height': height,
                'format': self._get_image_format(img_url)
            }
            
            return img_info
            
        except Exception as e:
            logger.warning(f"Error processing image: {e}")
            return None
    
    def _get_image_format(self, url: str) -> str:
        """
        Determine image format from URL with error handling
        
        Args:
            url (str): Image URL
            
        Returns:
            str: Image format (jpg, png, gif, etc.)
        """
        try:
            if not url:
                return 'JPEG'
                
            extension = url.split('.')[-1].lower().split('?')[0]
            
            # Map common extensions
            format_map = {
                'jpg': 'JPEG',
                'jpeg': 'JPEG', 
                'png': 'PNG',
                'gif': 'GIF',
                'bmp': 'BMP',
                'svg': 'SVG',
                'webp': 'WEBP'
            }
            
            return format_map.get(extension, 'JPEG')
            
        except Exception as e:
            logger.warning(f"Error determining image format for {url}: {e}")
            return 'JPEG'
    @handle_exception
    def get_page_content(self, url: str, use_selenium: bool = False) -> Optional[BeautifulSoup]:
        """
        Get page content using requests or selenium with comprehensive error handling
        
        Args:
            url (str): URL to fetch
            use_selenium (bool): Whether to use Selenium instead of requests
            
        Returns:
            BeautifulSoup: Parsed HTML content or None if failed
        
        Raises:
            URLValidationError: If URL is invalid
            NetworkError: If network-related errors occur
            ContentMissingError: If content is not found (404)
            CaptchaDetectedError: If CAPTCHA is detected
            RateLimitError: If rate limited by server
        """
        # Validate URL
        if not url or not url.strip():
            raise URLValidationError("Empty URL provided", url)
        
        try:
            parsed_url = urlparse(url.strip())
            if not parsed_url.scheme or not parsed_url.netloc:
                raise URLValidationError(f"Invalid URL format: {url}", url)
        except Exception as e:
            raise URLValidationError(f"Invalid URL: {str(e)}", url)
        
        # Check consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            cooldown_time = min(300, self.backoff_factor ** self.consecutive_failures)  # Max 5 minutes
            if time.time() - self.last_error_time < cooldown_time:
                raise NetworkError(f"Too many consecutive failures. Please wait {cooldown_time} seconds.", url=url)
        
        with ErrorContext(f"fetch_content", url=url):
            try:
                # Enforce rate limiting
                self._enforce_rate_limit()
                
                logger.info(f"Fetching content from: {url}")
                
                if use_selenium:
                    html_content = self._get_content_selenium(url)
                else:
                    html_content = self._get_content_requests(url)
                
                if not html_content:
                    self.consecutive_failures += 1
                    self.last_error_time = time.time()
                    raise ContentMissingError("No content received from server", url)
                
                # Check for CAPTCHA
                if ErrorDetector.is_captcha_detected(html_content):
                    self.consecutive_failures += 1
                    self.last_error_time = time.time()
                    raise CaptchaDetectedError("CAPTCHA detected on page", url)
                
                soup = BeautifulSoup(html_content, 'lxml')
                
                # Reset failure counter on success
                self.consecutive_failures = 0
                
                logger.info(f"Successfully parsed content from: {url}")
                return soup
                
            except (CaptchaDetectedError, RateLimitError, URLValidationError):
                # Re-raise our custom exceptions
                raise
            except (ConnectionError, Timeout, socket.timeout, socket.gaierror) as e:
                self.consecutive_failures += 1
                self.last_error_time = time.time()
                raise NetworkError(f"Network error: {str(e)}", original_exception=e, url=url)
            except HTTPError as e:
                if e.response and e.response.status_code == 404:
                    raise ContentMissingError(f"Content not found (404): {url}", url, status_code=404)
                elif e.response and e.response.status_code in [429, 503]:
                    retry_after = None
                    if e.response.headers.get('Retry-After'):
                        try:
                            retry_after = int(e.response.headers['Retry-After'])
                        except ValueError:
                            pass
                    raise RateLimitError(f"Rate limited (HTTP {e.response.status_code})", retry_after, url)
                else:
                    self.consecutive_failures += 1
                    self.last_error_time = time.time()
                    raise NetworkError(f"HTTP error {e.response.status_code if e.response else 'unknown'}: {str(e)}", 
                                     original_exception=e, url=url)
            except (WebDriverException, TimeoutException) as e:
                self.consecutive_failures += 1
                self.last_error_time = time.time()
                raise NetworkError(f"Browser automation error: {str(e)}", original_exception=e, url=url)
            except Exception as e:
                self.consecutive_failures += 1
                self.last_error_time = time.time()
                logger.error(f"Unexpected error fetching {url}: {str(e)}")
                raise NetworkError(f"Unexpected error: {str(e)}", original_exception=e, url=url)
    
    def _get_content_requests(self, url: str) -> Optional[str]:
        """
        Get content using requests with comprehensive error handling and retry logic
        
        Args:
            url (str): URL to fetch
            
        Returns:
            Optional[str]: HTML content or None if failed
        
        Raises:
            NetworkError: For network-related errors
            ContentMissingError: For 404 errors
            RateLimitError: For rate limiting
        """
        for attempt in range(self.max_retries):
            try:
                # Add some randomization to avoid detection
                import random
                delay = random.uniform(0.5, 1.5)
                time.sleep(delay)
                
                response = self.session.get(
                    url, 
                    timeout=(self.timeout // 2, self.timeout),  # (connect_timeout, read_timeout)
                    allow_redirects=True,
                    verify=True
                )
                
                # Check for rate limiting before raising for status
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    retry_seconds = int(retry_after) if retry_after else 60
                    raise RateLimitError(f"Rate limited by server", retry_seconds, url)
                
                if response.status_code == 404:
                    raise ContentMissingError(f"Content not found (404)", url, status_code=404)
                
                response.raise_for_status()
                
                # Additional validation
                if not response.text or len(response.text.strip()) < 100:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Received minimal content from {url}, retrying...")
                        continue
                    else:
                        raise ContentMissingError("Received minimal or no content", url)
                
                return response.text
                
            except (RateLimitError, ContentMissingError):
                # Re-raise our custom exceptions immediately
                raise
            except (ConnectionError, Timeout, socket.timeout, socket.gaierror, 
                    MaxRetryError, NewConnectionError, ChunkedEncodingError) as e:
                if attempt < self.max_retries - 1:
                    import random
                    wait_time = (self.backoff_factor ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Network error on attempt {attempt + 1}/{self.max_retries} for {url}: {e}. "
                                 f"Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                else:
                    raise NetworkError(f"Network error after {self.max_retries} attempts: {str(e)}", 
                                     original_exception=e, url=url)
            except HTTPError as e:
                # Handle specific HTTP errors
                if e.response:
                    status_code = e.response.status_code
                    if status_code == 404:
                        raise ContentMissingError(f"Content not found (404)", url, status_code=404)
                    elif status_code in [429, 503]:
                        retry_after = e.response.headers.get('Retry-After')
                        retry_seconds = int(retry_after) if retry_after else 60
                        raise RateLimitError(f"Rate limited (HTTP {status_code})", retry_seconds, url)
                    elif 500 <= status_code < 600:
                        if attempt < self.max_retries - 1:
                            wait_time = (self.backoff_factor ** attempt) + random.uniform(0, 1)
                            logger.warning(f"Server error {status_code} on attempt {attempt + 1}/{self.max_retries}. "
                                         f"Retrying in {wait_time:.1f} seconds...")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise NetworkError(f"Server error {status_code} after {self.max_retries} attempts", 
                                             original_exception=e, url=url)
                    else:
                        raise NetworkError(f"HTTP error {status_code}: {str(e)}", original_exception=e, url=url)
                else:
                    raise NetworkError(f"HTTP error: {str(e)}", original_exception=e, url=url)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = (self.backoff_factor ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Unexpected error on attempt {attempt + 1}/{self.max_retries} for {url}: {e}. "
                                 f"Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                else:
                    raise NetworkError(f"Unexpected error after {self.max_retries} attempts: {str(e)}", 
                                     original_exception=e, url=url)
        
        return None
    
    def _get_content_selenium(self, url: str) -> Optional[str]:
        """
        Get content using Selenium with comprehensive error handling
        
        Args:
            url (str): URL to fetch
            
        Returns:
            Optional[str]: HTML content or None if failed
        
        Raises:
            NetworkError: For Selenium-related errors
            CaptchaDetectedError: If CAPTCHA is detected
        """
        try:
            if not self.driver:
                self.setup_driver()
            
            # Set up timeout for page load
            original_timeout = self.driver.timeouts.page_load
            self.driver.set_page_load_timeout(self.timeout)
            
            try:
                self.driver.get(url)
                
                # Wait for basic page elements to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                except TimeoutException:
                    logger.warning(f"Page load timeout for {url}, continuing with partial content")
                
                # Additional wait for dynamic content
                time.sleep(2)
                
                # Get page source
                page_source = self.driver.page_source
                
                # Check for common error pages
                if "404" in self.driver.title or "Not Found" in self.driver.title:
                    raise ContentMissingError(f"Page not found: {url}", url, status_code=404)
                
                # Check for CAPTCHA indicators
                if ErrorDetector.is_captcha_detected(page_source):
                    raise CaptchaDetectedError(f"CAPTCHA detected on page: {url}", url)
                
                # Check for rate limiting indicators
                page_text = page_source.lower()
                rate_limit_indicators = [
                    "rate limit", "too many requests", "temporarily blocked",
                    "please try again later", "service unavailable"
                ]
                if any(indicator in page_text for indicator in rate_limit_indicators):
                    raise RateLimitError(f"Rate limiting detected on page: {url}", url=url)
                
                return page_source
                
            except TimeoutException as e:
                raise NetworkError(f"Page load timeout for {url}: {str(e)}", original_exception=e, url=url)
            except (NoSuchElementException, ElementNotInteractableException) as e:
                logger.warning(f"Selenium element error for {url}: {e}")
                # Try to get page source anyway
                try:
                    return self.driver.page_source
                except Exception:
                    raise NetworkError(f"Failed to get page source after element error: {str(e)}", 
                                     original_exception=e, url=url)
            finally:
                # Restore original timeout
                try:
                    self.driver.set_page_load_timeout(original_timeout)
                except Exception:
                    pass
                    
        except (CaptchaDetectedError, RateLimitError, ContentMissingError, NetworkError):
            # Re-raise our custom exceptions
            raise
        except WebDriverException as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg:
                raise NetworkError(f"WebDriver timeout for {url}: {str(e)}", original_exception=e, url=url)
            elif "connection" in error_msg or "network" in error_msg:
                raise NetworkError(f"WebDriver network error for {url}: {str(e)}", original_exception=e, url=url)
            else:
                # Try to recover by restarting driver
                logger.warning(f"WebDriver error for {url}: {e}. Attempting to restart driver...")
                try:
                    self.close_driver()
                    self.setup_driver()
                    # Retry once
                    self.driver.get(url)
                    time.sleep(2)
                    return self.driver.page_source
                except Exception as retry_error:
                    raise NetworkError(f"WebDriver error (retry failed) for {url}: {str(retry_error)}", 
                                     original_exception=e, url=url)
        except Exception as e:
            logger.error(f"Unexpected Selenium error for {url}: {e}")
            raise NetworkError(f"Unexpected Selenium error: {str(e)}", original_exception=e, url=url)
    
    @abstractmethod
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """
        Extract problem statement from the given URL
        
        Args:
            url (str): Problem URL
            
        Returns:
            Dict[str, Any]: Problem information with keys: title, problem_statement, 
                          input_format, output_format, constraints, examples, 
                          time_limit, memory_limit, images
        
        Raises:
            URLValidationError: If URL is invalid for this platform
            NetworkError: If network-related errors occur
            ContentMissingError: If problem content is not found
            CaptchaDetectedError: If CAPTCHA is encountered
        """
        pass
    
    @abstractmethod
    def get_editorial(self, url: str) -> Dict[str, Any]:
        """
        Extract editorial information from the given URL
        
        Args:
            url (str): Editorial URL
            
        Returns:
            Dict[str, Any]: Editorial information with keys: title, problem_statement, 
                          input_format, output_format, constraints, examples, 
                          time_limit, memory_limit, images
        
        Raises:
            URLValidationError: If URL is invalid for this platform
            NetworkError: If network-related errors occur
            ContentMissingError: If editorial content is not found
            CaptchaDetectedError: If CAPTCHA is encountered
        """
        pass
    
    @abstractmethod
    def is_valid_url(self, url: str) -> bool:
        """
        Check if the URL is valid for this platform
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        pass
    
    def safe_get_problem_statement(self, url: str) -> Dict[str, Any]:
        """
        Safely get problem statement with graceful error handling
        
        Args:
            url (str): Problem URL
            
        Returns:
            Dict[str, Any]: Problem information (may contain error info if failed)
        """
        try:
            return self.get_problem_statement(url)
        except (URLValidationError, NetworkError, ContentMissingError, CaptchaDetectedError) as e:
            logger.error(f"Failed to get problem statement from {url}: {e}")
            error_reporter.report_error(e.error_info if hasattr(e, 'error_info') else None)
            return ErrorRecovery.create_fallback_content(url, e)
        except Exception as e:
            logger.error(f"Unexpected error getting problem statement from {url}: {e}")
            return ErrorRecovery.create_fallback_content(url, e)
    
    def safe_get_editorial(self, url: str) -> Dict[str, Any]:
        """
        Safely get editorial with graceful error handling
        
        Args:
            url (str): Editorial URL
            
        Returns:
            Dict[str, Any]: Editorial information (may contain error info if failed)
        """
        try:
            return self.get_editorial(url)
        except (URLValidationError, NetworkError, ContentMissingError, CaptchaDetectedError) as e:
            logger.error(f"Failed to get editorial from {url}: {e}")
            error_reporter.report_error(e.error_info if hasattr(e, 'error_info') else None)
            return ErrorRecovery.create_fallback_content(url, e)
        except Exception as e:
            logger.error(f"Unexpected error getting editorial from {url}: {e}")
            return ErrorRecovery.create_fallback_content(url, e)
    
    def close_driver(self) -> None:
        """
        Close the WebDriver instance safely
        """
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
    
    def create_standard_format(self, **kwargs) -> Dict[str, Any]:
        """
        Create a standardized return dictionary with all required keys and error handling
        
        Args:
            **kwargs: Key-value pairs to include in the dictionary
            
        Returns:
            Dict[str, Any]: Standardized dictionary with all required keys
        """
        try:
            standard_dict = {
                'title': '',
                'problem_statement': '',
                'input_format': '',
                'output_format': '',
                'constraints': '',
                'examples': [],
                'time_limit': '',
                'memory_limit': '',
                'images': []
            }
            
            # Update with provided values
            standard_dict.update(kwargs)
            
            # Use ErrorRecovery to sanitize content
            standard_dict = ErrorRecovery.sanitize_content(standard_dict)
            
            # Clean text fields
            text_fields = ['title', 'problem_statement', 'input_format', 
                          'output_format', 'constraints', 'time_limit', 'memory_limit']
            
            for field in text_fields:
                if field in standard_dict and isinstance(standard_dict[field], str):
                    try:
                        standard_dict[field] = self.clean_and_format_text(standard_dict[field])
                    except Exception as e:
                        logger.warning(f"Error cleaning field {field}: {e}")
                        standard_dict[field] = str(standard_dict[field])  # Fallback to string conversion
            
            return standard_dict
            
        except Exception as e:
            logger.error(f"Error creating standard format: {e}")
            # Return minimal safe format
            return {
                'title': 'Error processing content',
                'problem_statement': f'An error occurred while processing: {str(e)}',
                'input_format': '',
                'output_format': '',
                'constraints': '',
                'examples': [],
                'time_limit': '',
                'memory_limit': '',
                'images': [],
                'error_occurred': True
            }
    
    def __del__(self):
        """
        Cleanup when object is destroyed
        """
        try:
            self.close_driver()
            if hasattr(self, 'session') and self.session:
                self.session.close()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")