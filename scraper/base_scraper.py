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
try:
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
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None
    Service = None
    Options = None
    By = None
    WebDriverWait = None
    EC = None
    WebDriverException = Exception
    TimeoutException = Exception
    NoSuchElementException = Exception
    ElementNotInteractableException = Exception
    SessionNotCreatedException = Exception
    ChromeDriverManager = None
import time
import logging
import re
import socket
import signal
from urllib.parse import urlparse, urljoin
from pathlib import Path
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
import io
import base64
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    HTML = None
    CSS = None
    FontConfiguration = None
    # Log the issue but don't fail the import
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"WeasyPrint not available: {e}")
from requests.exceptions import (
    RequestException, Timeout, ConnectionError, HTTPError, 
    TooManyRedirects, InvalidURL, ChunkedEncodingError
)
try:
    from urllib3.exceptions import MaxRetryError, NewConnectionError
except ImportError:
    MaxRetryError = Exception
    NewConnectionError = Exception

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
    
    # Platform patterns for URL detection (enhanced with CodeChef support)
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
        ],
        'CodeChef': [
            r'https://www\.codechef\.com/problems/[A-Z0-9_]+',
            r'https://www\.codechef\.com/[A-Z0-9_]+/problems/[A-Z0-9_]+',
            r'https://discuss\.codechef\.com/.*'
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
        try:
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
        except ImportError:
            # Fallback if urllib3 is not available
            retry_strategy = None
        
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
            # Normalize different newline representations first
            text = text.replace('\r\n', '\n').replace('\r', '\n')

            # Remove extra spaces while preserving line breaks
            text = re.sub(r'[ \t]+', ' ', text.strip())

            # Normalize multiple blank lines and spaces around newlines
            text = re.sub(r'\n{3,}', '\n\n', text)  # Collapse many blank lines
            text = re.sub(r' *\n *', '\n', text)     # Trim spaces around newlines
            
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
            text = re.sub(r'[ \t]+', ' ', text)
            
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
            
            # Filter out language flag images and other unwanted images
            if self._should_exclude_image(img_tag, src):
                logger.debug(f"Excluding image: {src}")
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
    
    def _should_exclude_image(self, img_tag, src: str) -> bool:
        """
        Determine if an image should be excluded from PDF generation.
        Enhanced filtering specifically for competitive programming platforms.
        
        This filters out:
        - Language flags and selectors
        - UI elements (navigation, buttons, logos)
        - Decorative icons and sprites
        - Advertisement and social media images
        - Placeholder and spacer images
        
        While preserving:
        - Problem diagrams and illustrations
        - Mathematical figures and graphs
        - Sample input/output visualizations
        - Algorithm flowcharts and data structures
        
        Args:
            img_tag: BeautifulSoup img tag
            src (str): Image source URL
            
        Returns:
            bool: True if the image should be excluded
        """
        try:
            # Get image attributes for comprehensive analysis
            alt_text = (img_tag.get('alt', '') or '').lower()
            title_text = (img_tag.get('title', '') or '').lower()
            class_names = ' '.join(img_tag.get('class', [])).lower()
            id_attr = (img_tag.get('id', '') or '').lower()
            src_lower = src.lower()
            
            # Enhanced language flag detection
            # Common patterns across competitive programming sites
            language_patterns = [
                # File name patterns
                'flag', 'lang', 'language', 'jp.png', 'en.png', 'ja.png', 'gb.png',
                'uk.png', 'us.png', 'cn.png', 'kr.png', 'ru.png',
                # Directory patterns
                '/lang/', '/flag/', '/languages/', '/flags/', '/img/lang/',
                '/images/lang/', '/static/lang/', '/assets/lang/',
                # Alt text patterns
                'japanese', 'english', 'language', 'flag', 'japan', 'britain',
                'united kingdom', 'united states', 'china', 'korea', 'russia'
            ]
            
            # Check language flag patterns
            for pattern in language_patterns:
                if (pattern in src_lower or 
                    pattern in alt_text or 
                    pattern in title_text or
                    pattern in class_names):
                    logger.debug(f"Excluding language flag: {src} (pattern: {pattern})")
                    return True
            
            # Size-based filtering for icons and decorative elements
            width = img_tag.get('width')
            height = img_tag.get('height')
            try:
                if width and height:
                    w, h = int(width), int(height)
                    # Exclude very small images (icons, flags, buttons)
                    if w <= 32 and h <= 32:
                        logger.debug(f"Excluding small icon: {src} ({w}x{h})")
                        return True
                    # Exclude 1x1 pixel trackers and spacers
                    if w == 1 or h == 1:
                        logger.debug(f"Excluding pixel tracker/spacer: {src} ({w}x{h})")
                        return True
            except (ValueError, TypeError):
                pass
            
            # Platform-specific exclusion patterns
            # AtCoder specific filtering
            if 'atcoder.jp' in src_lower:
                atcoder_patterns = [
                    '/img/lang/', '/images/lang/', '/static/lang/', '/assets/lang/',
                    'language-selector', 'lang-', '_lang_', 'flag_', '/common/img/',
                    '/img/flag/', '/images/flag/', '/static/flag/', '/navbar/',
                    '/header/', '/footer/', '/logo/', 'atcoder_logo', 'rating_',
                    'difficulty_', '/contest/', 'user_icon', 'avatar'
                ]
                
                for pattern in atcoder_patterns:
                    if pattern in src_lower:
                        logger.debug(f"Excluding AtCoder UI element: {src} (pattern: {pattern})")
                        return True
            
            # Codeforces specific filtering
            elif 'codeforces.com' in src_lower or 'codeforces.ru' in src_lower:
                codeforces_patterns = [
                    '/images/flags/', '/img/flags/', 'flag_', 'country_', 
                    '/images/icons/', 'icon_', 'logo_', '/header/', '/footer/',
                    'rating_', 'rank_', 'social_', 'sponsor_', 'advertisement',
                    'telegram', 'vk_icon', 'facebook_icon', 'twitter_icon'
                ]
                
                for pattern in codeforces_patterns:
                    if pattern in src_lower:
                        logger.debug(f"Excluding Codeforces UI element: {src} (pattern: {pattern})")
                        return True
            
            # SPOJ specific filtering  
            elif 'spoj.com' in src_lower:
                spoj_patterns = [
                    '/gfx/flags/', '/images/flags/', 'flag_', '/gfx/icons/',
                    'sphere_logo', 'spoj_logo', '/header/', '/footer/',
                    'navigation', 'menu_', 'social_', 'google_ads'
                ]
                
                for pattern in spoj_patterns:
                    if pattern in src_lower:
                        logger.debug(f"Excluding SPOJ UI element: {src} (pattern: {pattern})")
                        return True
            
            # Generic UI and navigation elements
            ui_navigation_patterns = [
                # Navigation and menus
                'nav', 'menu', 'navigation', 'navbar', 'sidebar', 'breadcrumb',
                'dropdown', 'hamburger', 'mobile-menu',
                # Buttons and controls
                'button', 'btn', 'submit', 'search', 'close', 'expand', 'collapse',
                # Branding and logos
                'logo', 'brand', 'header', 'footer', 'banner', 'masthead',
                # Social media and sharing
                'social', 'share', 'twitter', 'facebook', 'github', 'linkedin',
                'youtube', 'instagram', 'telegram', 'discord',
                # Advertisement and tracking
                'advertisement', 'ads', 'google-ads', 'adsense', 'sponsor',
                'tracking', 'analytics', 'pixel',
                # User interface elements
                'avatar', 'profile', 'user-icon', 'thumbnail', 'preview'
            ]
            
            # Check UI patterns in various attributes
            for pattern in ui_navigation_patterns:
                if (pattern in src_lower or 
                    pattern in alt_text or 
                    pattern in class_names or
                    pattern in id_attr or
                    pattern in title_text):
                    logger.debug(f"Excluding UI element: {src} (pattern: {pattern})")
                    return True
            
            # File type and path-based exclusions
            file_path_patterns = [
                # Icon directories
                '/icons/', '/icon/', '/img/icons/', '/images/icons/', '/assets/icons/',
                # UI directories
                '/ui/', '/interface/', '/controls/', '/buttons/',
                # Common icon files
                'favicon', 'sprite', 'thumb', 'avatar', '_icon', '-icon', 'icon_', 'icon-',
                # Placeholder and spacer images
                'placeholder', 'blank', 'empty', 'spacer', 'transparent', 'pixel',
                # Decorative elements
                'decoration', 'ornament', 'border', 'background', 'texture'
            ]
            
            for pattern in file_path_patterns:
                if pattern in src_lower:
                    logger.debug(f"Excluding file path pattern: {src} (pattern: {pattern})")
                    return True
            
            # Content preservation logic - keep these images
            # Mathematical and algorithmic content indicators
            content_indicators = [
                'diagram', 'graph', 'chart', 'figure', 'illustration', 'example',
                'sample', 'input', 'output', 'algorithm', 'flowchart', 'tree',
                'network', 'grid', 'matrix', 'visualization', 'drawing',
                'problem', 'solution', 'explanation', 'tutorial', 'math',
                'formula', 'equation', 'proof', 'geometric', 'coordinate'
            ]
            
            # If image has content indicators, prefer to include it
            for indicator in content_indicators:
                if (indicator in alt_text or 
                    indicator in title_text or
                    indicator in src_lower):
                    logger.debug(f"Preserving content image: {src} (indicator: {indicator})")
                    return False
            
            # Base64 embedded images - usually small decorative elements
            if src.startswith('data:image/'):
                # Allow mathematical expressions but exclude decorative elements
                if len(src) < 1000:  # Small base64 images are likely decorative
                    logger.debug(f"Excluding small base64 image: {src[:100]}...")
                    return True
            
            # Images without meaningful alt text or title that are likely decorative
            if (not alt_text.strip() and 
                not title_text.strip() and 
                any(pattern in src_lower for pattern in ['spacer', 'blank', 'pixel', 'transparent'])):
                logger.debug(f"Excluding decorative image with no alt text: {src}")
                return True
            
            # Default: include the image if no exclusion criteria met
            return False
            
        except Exception as e:
            logger.warning(f"Error in image exclusion analysis for {src}: {e}")
            # On error, include the image to avoid losing potentially important content
            return False
    
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
    
    def download_webpage_as_pdf_fallback(self, url: str, output_path: str, title: str = None) -> bool:
        """
        Fallback method to download webpage as PDF when WeasyPrint is not available.
        
        This method scrapes the content and uses the existing PDF generation system
        instead of direct webpage conversion.
        
        Args:
            url (str): URL of the webpage to download
            output_path (str): Path where the PDF should be saved
            title (str, optional): Custom title for the PDF
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
        """
        try:
            logger.info(f"Using fallback PDF generation for: {url}")
            
            # Get the content using the existing scraping method
            if hasattr(self, 'get_problem_statement') and self.is_valid_url(url):
                # If it's a problem URL, use problem statement extraction
                data = self.get_problem_statement(url)
            elif hasattr(self, 'get_editorial') and 'blog' in url.lower():
                # If it's an editorial URL, use editorial extraction
                data = self.get_editorial(url)
            else:
                # Generic content extraction
                soup = self.get_page_content(url)
                if not soup:
                    return False
                
                # Extract title
                title_elem = soup.find('title')
                page_title = title_elem.get_text(strip=True) if title_elem else title or "Webpage"
                
                # Extract main content (try common content selectors)
                content_selectors = [
                    '.problem-statement',
                    '.blog-entry',
                    '.content',
                    '.main-content',
                    'main',
                    '.post-content',
                    'article'
                ]
                
                content_elem = None
                for selector in content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        break
                
                if not content_elem:
                    # Fallback to body if no specific content found
                    content_elem = soup.find('body') or soup
                
                # Clean up the content
                for tag in content_elem.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    tag.decompose()
                
                content_text = content_elem.get_text('\n', strip=True)
                
                data = self.create_standard_format(
                    title=page_title,
                    problem_statement=content_text
                )
            
            # Use the PDF creator to generate the PDF
            from pdf_generator.pdf_creator import PDFCreator
            
            pdf_creator = PDFCreator(output_dir=str(Path(output_path).parent))
            filename = Path(output_path).name
            
            # Create PDF using the existing system
            pdf_path = pdf_creator.create_problem_pdf(
                problem=data,
                filename=filename,
                section_title="Webpage Content"
            )
            
            return Path(pdf_path).exists()
            
        except Exception as e:
            logger.error(f"Fallback PDF generation failed for {url}: {e}")
            return False
    
    @handle_exception
    def download_webpage_as_pdf(self, url: str, output_path: str, title: str = None, 
                              use_selenium: bool = False, css_styles: str = None) -> bool:
        """
        Download a webpage directly as a PDF file using WeasyPrint.
        
        This method fetches the webpage and converts it directly to PDF format,
        preserving the original layout and styling. This is an alternative to
        the content scraping approach.
        
        Args:
            url (str): URL of the webpage to download
            output_path (str): Path where the PDF should be saved
            title (str, optional): Custom title for the PDF. If None, extracted from page
            use_selenium (bool): Whether to use Selenium to get JavaScript-rendered content
            css_styles (str, optional): Additional CSS styles to apply
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            URLValidationError: If URL is invalid
            NetworkError: If network-related errors occur
            PDFGenerationError: If PDF generation fails
        """
        if not WEASYPRINT_AVAILABLE:
            logger.warning("WeasyPrint is not available. Using fallback PDF generation method.")
            return self.download_webpage_as_pdf_fallback(url, output_path, title)
        
        # Validate URL
        if not url or not url.strip():
            raise URLValidationError("Empty URL provided", url)
        
        try:
            parsed_url = urlparse(url.strip())
            if not parsed_url.scheme or not parsed_url.netloc:
                raise URLValidationError(f"Invalid URL format: {url}", url)
        except Exception as e:
            raise URLValidationError(f"Invalid URL: {str(e)}", url)
        
        with ErrorContext(f"download_webpage_as_pdf", url=url):
            try:
                logger.info(f"Downloading webpage as PDF: {url} -> {output_path}")
                
                # Get HTML content
                if use_selenium:
                    html_content = self._get_content_selenium(url)
                else:
                    html_content = self._get_content_requests(url)
                
                if not html_content:
                    raise ContentMissingError("No content received from webpage", url)
                
                # Apply custom styling for better PDF rendering
                pdf_css = self._get_pdf_css_styles(css_styles)
                
                # Create HTML object with base URL for resolving relative links
                html_doc = HTML(string=html_content, base_url=url)
                
                # Create CSS object if custom styles provided
                css_objects = []
                if pdf_css:
                    css_objects.append(CSS(string=pdf_css))
                
                # Generate PDF with font configuration for better Unicode support
                font_config = FontConfiguration()
                
                # Write PDF to file
                try:
                    html_doc.write_pdf(
                        target=output_path,
                        stylesheets=css_objects,
                        font_config=font_config,
                        presentational_hints=True,  # Use HTML presentation attributes
                        optimize_images=True  # Optimize embedded images
                    )
                    
                    logger.info(f"Successfully created PDF: {output_path}")
                    return True
                    
                except Exception as pdf_error:
                    from utils.error_handler import PDFGenerationError
                    logger.error(f"PDF generation failed for {url}: {pdf_error}")
                    raise PDFGenerationError(f"Failed to generate PDF: {str(pdf_error)}", 
                                           original_exception=pdf_error)
                
            except (URLValidationError, ContentMissingError, NetworkError):
                # Re-raise our custom exceptions
                raise
            except Exception as e:
                from utils.error_handler import PDFGenerationError
                logger.error(f"Unexpected error downloading webpage as PDF from {url}: {e}")
                raise PDFGenerationError(f"Unexpected error: {str(e)}", original_exception=e)
    
    def _get_pdf_css_styles(self, custom_css: str = None) -> str:
        """
        Generate CSS styles optimized for PDF rendering and LLM training.
        
        Enhanced for competitive programming platforms with improved text structure,
        semantic markup, and content organization for better LLM consumption.
        
        Args:
            custom_css (str, optional): Additional custom CSS styles
            
        Returns:
            str: CSS styles for PDF rendering optimized for LLM training
        """
        base_css = """
        /* LLM-Optimized PDF Styles for Competitive Programming */
        @page {
            margin: 2cm;
            size: A4;
            @bottom-center {
                content: counter(page) " / " counter(pages);
                font-size: 9pt;
                color: #666;
            }
            @top-right {
                content: "Generated: " date();
                font-size: 8pt;
                color: #888;
            }
        }
        
        /* Base typography optimized for text extraction */
        body {
            font-family: 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #000;
            background: white;
            margin: 0;
            padding: 0;
        }
        
        /* Semantic structure for better content identification */
        .problem-title, h1.problem-title {
            font-size: 18pt;
            font-weight: bold;
            color: #2c3e50;
            margin: 1.5em 0 1em 0;
            page-break-after: avoid;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
        }
        
        .problem-statement, .problem-description {
            background: #f8f9fa;
            padding: 1em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
            page-break-inside: avoid;
        }
        
        .constraints, .time-limit, .memory-limit {
            background: #fff3cd;
            padding: 0.8em;
            margin: 0.8em 0;
            border: 1px solid #ffc107;
            border-radius: 4px;
            font-weight: 600;
        }
        
        .input-format, .output-format {
            background: #e8f5e8;
            padding: 0.8em;
            margin: 0.8em 0;
            border: 1px solid #28a745;
            border-radius: 4px;
        }
        
        .sample-input, .sample-output, .example {
            background: #f8f9fa;
            padding: 1em;
            margin: 1em 0;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            font-family: 'DejaVu Sans Mono', 'Liberation Mono', 'Courier New', monospace;
            font-size: 10pt;
            page-break-inside: avoid;
        }
        
        .sample-input::before {
            content: "[SAMPLE_INPUT]";
            display: block;
            font-weight: bold;
            color: #495057;
            margin-bottom: 0.5em;
            font-family: 'DejaVu Sans', Arial, sans-serif;
        }
        
        .sample-output::before {
            content: "[SAMPLE_OUTPUT]";
            display: block;
            font-weight: bold;
            color: #495057;
            margin-bottom: 0.5em;
            font-family: 'DejaVu Sans', Arial, sans-serif;
        }
        
        /* Remove navigation and non-content elements */
        nav, .navbar, .nav, .navigation, .menu,
        .sidebar, .header, .footer, .banner,
        .advertisement, .ads, .social-media,
        .breadcrumb, .pagination, .comments,
        .rating, .user-info, .contest-info,
        .lang-selector, .language-picker,
        .flag, .country-flag, .submit-button,
        .login-button, .register-button,
        .vote, .share-buttons, .social-share,
        .cookie-banner, .gdpr-notice,
        .edit-button, .report-button,
        .tags-container, .difficulty-badge,
        .problem-tags, .problem-stats,
        .my-submissions, .contest-navigation,
        .breadcrumbs, .problem-navigation {
            display: none !important;
        }
        
        /* Enhanced headings with semantic structure */
        h1, h2, h3, h4, h5, h6 {
            color: #2c3e50;
            margin-top: 1.5em;
            margin-bottom: 0.8em;
            page-break-after: avoid;
            font-weight: bold;
        }
        
        h1 { font-size: 18pt; border-bottom: 2px solid #3498db; padding-bottom: 0.3em; }
        h2 { font-size: 16pt; border-bottom: 1px solid #3498db; padding-bottom: 0.2em; }
        h3 { font-size: 14pt; color: #34495e; }
        h4 { font-size: 12pt; color: #34495e; }
        h5 { font-size: 11pt; color: #34495e; }
        h6 { font-size: 10pt; color: #34495e; }
        
        /* Improved paragraph formatting */
        p {
            margin-bottom: 1em;
            orphans: 3;
            widows: 3;
            text-align: justify;
        }
        
        /* Enhanced code blocks for competitive programming */
        pre, code {
            font-family: 'DejaVu Sans Mono', 'Liberation Mono', 'Source Code Pro', 'Courier New', monospace;
            font-size: 10pt;
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 1em;
            margin: 1em 0;
            page-break-inside: avoid;
            border-radius: 4px;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }
        
        pre::before {
            content: "[CODE_BLOCK]";
            display: block;
            font-size: 8pt;
            color: #666;
            font-weight: normal;
            margin-bottom: 0.5em;
            font-family: 'DejaVu Sans', Arial, sans-serif;
        }
        
        .code-block, .highlight {
            background: #272822;
            color: #f8f8f2;
            padding: 1em;
            border-radius: 6px;
            margin: 1em 0;
            page-break-inside: avoid;
        }
        
        .code-block::before,
        .highlight::before {
            content: "[CODE_BLOCK]";
            display: block;
            font-size: 8pt;
            color: #aaa;
            font-weight: normal;
            margin-bottom: 0.5em;
            font-family: 'DejaVu Sans', Arial, sans-serif;
        }
        
        /* Inline code styling */
        code {
            background: #f1f3f4;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-size: 0.9em;
            border: none;
            margin: 0;
        }
        
        code::before {
            content: "[INLINE_CODE]";
            font-size: 0.7em;
            color: #666;
            margin-right: 0.3em;
        }
        
        /* Enhanced tables for problem data */
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1.5em 0;
            page-break-inside: avoid;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        table::before {
            content: "[TABLE]";
            display: block;
            font-size: 8pt;
            color: #666;
            font-weight: normal;
            margin-bottom: 0.5em;
        }
        
        th, td {
            border: 1px solid #dee2e6;
            padding: 0.8em;
            text-align: left;
            vertical-align: top;
        }
        
        th {
            background: #f8f9fa;
            font-weight: bold;
            color: #495057;
        }
        
        tr:nth-child(even) {
            background: #f8f9fa;
        }
        
        /* Images and figures */
        img {
            max-width: 100%;
            height: auto;
            page-break-inside: avoid;
            display: block;
            margin: 1em auto;
            border: 1px solid #e9ecef;
            border-radius: 4px;
        }
        
        img::before {
            content: "[IMAGE: " attr(alt) "]";
            display: block;
            font-size: 8pt;
            color: #666;
            font-weight: normal;
            margin-bottom: 0.3em;
        }
        
        figure {
            margin: 1.5em 0;
            text-align: center;
            page-break-inside: avoid;
        }
        
        figcaption {
            font-style: italic;
            color: #6c757d;
            margin-top: 0.5em;
            font-size: 0.9em;
        }
        
        figcaption::before {
            content: "[CAPTION] ";
            font-weight: bold;
        }
        
        /* Mathematical expressions */
        .math, .tex, .mathjax, .katex {
            font-family: 'Latin Modern Math', 'STIX Two Math', 'Cambria Math', serif;
            font-size: 1.1em;
            margin: 0.5em 0;
        }
        
        .math::before,
        .tex::before,
        .mathjax::before,
        .katex::before {
            content: "[MATH]";
            font-size: 8pt;
            color: #666;
            font-weight: normal;
            margin-right: 0.3em;
        }
        
        /* Lists with better spacing */
        ul, ol {
            margin: 1em 0;
            padding-left: 2em;
        }
        
        ul::before {
            content: "[LIST]";
            display: block;
            font-size: 8pt;
            color: #666;
            font-weight: normal;
            margin-bottom: 0.3em;
        }
        
        ol::before {
            content: "[NUMBERED_LIST]";
            display: block;
            font-size: 8pt;
            color: #666;
            font-weight: normal;
            margin-bottom: 0.3em;
        }
        
        li {
            margin-bottom: 0.5em;
        }
        
        /* Special elements for competitive programming */
        .verdict, .status {
            padding: 0.3em 0.6em;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .verdict.accepted {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .verdict.wrong {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        /* Platform-specific optimizations */
        
        /* Codeforces specific */
        .problem-statement .problem-statement {
            padding: 0;
            background: none;
            border: none;
        }
        
        .input-specification, .output-specification {
            background: #e8f5e8;
            padding: 0.8em;
            margin: 0.8em 0;
            border: 1px solid #28a745;
            border-radius: 4px;
        }
        
        .input-specification::before {
            content: "[INPUT_SPECIFICATION]";
            display: block;
            font-size: 8pt;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        .output-specification::before {
            content: "[OUTPUT_SPECIFICATION]";
            display: block;
            font-size: 8pt;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        /* AtCoder specific */
        .lang, .lang-en, .lang-ja {
            display: block !important;
        }
        
        .part {
            margin: 1em 0;
            padding: 0.8em;
            background: #f8f9fa;
            border-left: 4px solid #007bff;
        }
        
        .part::before {
            content: "[SECTION]";
            display: block;
            font-size: 8pt;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        /* CodeChef specific */
        .problem-statement-string {
            background: #f8f9fa;
            padding: 1em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
        }
        
        .problem-statement-string::before {
            content: "[PROBLEM_DESCRIPTION]";
            display: block;
            font-size: 8pt;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        .problem-author {
            color: #6c757d;
            font-style: italic;
            margin: 0.5em 0;
        }
        
        .problem-author::before {
            content: "[AUTHOR]";
            display: inline;
            font-size: 8pt;
            color: #666;
            margin-right: 0.3em;
        }
        
        /* SPOJ specific */
        .prob {
            background: #f8f9fa;
            padding: 1em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
        }
        
        .prob::before {
            content: "[PROBLEM_CONTENT]";
            display: block;
            font-size: 8pt;
            color: #666;
            margin-bottom: 0.3em;
        }
        
        /* Utility classes for content structure */
        .content-section {
            margin: 1.5em 0;
            page-break-inside: avoid;
        }
        
        .content-section:first-child {
            margin-top: 0;
        }
        
        .content-section:last-child {
            margin-bottom: 0;
        }
        
        /* Print optimization */
        @media print {
            body {
                font-size: 11pt;
                line-height: 1.4;
            }
            
            h1 { font-size: 16pt; }
            h2 { font-size: 14pt; }
            h3 { font-size: 12pt; }
            
            .problem-statement, .constraints,
            .input-format, .output-format,
            .sample-input, .sample-output {
                page-break-inside: avoid;
            }
        }
        
        /* Accessibility and readability improvements */
        strong, b {
            font-weight: 700;
            color: #2c3e50;
        }
        
        em, i {
            font-style: italic;
            color: #34495e;
        }
        
        /* Links (for reference) */
        a {
            color: #007bff;
            text-decoration: underline;
        }
        
        a::after {
            content: " (" attr(href) ")";
            font-size: 0.8em;
            color: #6c757d;
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
        
        .example::before {
            content: "[EXAMPLE] ";
            font-weight: bold;
        }
        
        /* Better formatting for competitive programming elements */
        .test-case {
            border: 1px dashed #999;
            margin: 0.5em 0;
            padding: 0.5em;
        }
        
        .test-case::before {
            content: "[TEST_CASE] ";
            font-weight: bold;
            color: #555;
        }
        
        /* Enhanced mathematical notation for LLM parsing */
        .equation::before {
            content: "[EQUATION] ";
            font-style: italic;
        }
        
        .formula::before {
            content: "[FORMULA] ";
        }
        
        /* Better identification of problem components */
        .problem-id::before {
            content: "[PROBLEM_ID] ";
            font-weight: bold;
        }
        
        .contest-name::before {
            content: "[CONTEST_NAME] ";
        }
        
        .submission-count::before {
            content: "[SUBMISSIONS] ";
        }
        
        .success-rate::before {
            content: "[SUCCESS_RATE] ";
        }
        
        /* Additional LLM optimization markers */
        .problem-title::before {
            content: "[PROBLEM_TITLE] ";
            font-weight: bold;
        }
        
        .constraints::before {
            content: "[CONSTRAINTS] ";
            font-weight: bold;
        }
        
        .input-format::before {
            content: "[INPUT_FORMAT] ";
            font-weight: bold;
        }
        
        .output-format::before {
            content: "[OUTPUT_FORMAT] ";
            font-weight: bold;
        }
        
        /* Better handling of mathematical content */
        .math-container {
            background: #f9f9f9;
            padding: 0.5em;
            border-left: 3px solid #007bff;
            margin: 0.5em 0;
        }
        
        .math-container::before {
            content: "[MATHEMATICAL_CONTENT] ";
            font-size: 0.8em;
            color: #666;
        }
        
        /* Better handling of algorithmic content */
        .algorithm {
            background: #e8f4f8;
            padding: 1em;
            border: 1px solid #17a2b8;
            border-radius: 4px;
            margin: 1em 0;
        }
        
        .algorithm::before {
            content: "[ALGORITHM] ";
            display: block;
            font-weight: bold;
            color: #17a2b8;
            margin-bottom: 0.5em;
        }
        
        /* Better handling of complexity analysis */
        .complexity {
            background: #fff3cd;
            padding: 0.8em;
            border: 1px solid #ffc107;
            border-radius: 4px;
            margin: 0.8em 0;
        }
        
        .complexity::before {
            content: "[COMPLEXITY_ANALYSIS] ";
            display: block;
            font-weight: bold;
            color: #856404;
            margin-bottom: 0.3em;
        }
        """
        
        if custom_css:
            base_css += "\n\n/* Custom CSS */\n" + custom_css
        
        return base_css
    
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