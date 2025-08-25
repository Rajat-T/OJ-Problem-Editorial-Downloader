"""
Base scraper class for OJ Problem Editorial Downloader
Provides common interface and functionality for all platform scrapers
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import re
from urllib.parse import urlparse, urljoin
from PIL import Image
import io
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract base class for all platform-specific scrapers
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
        Initialize the base scraper
        
        Args:
            headless (bool): Whether to run browser in headless mode
            timeout (int): Request timeout in seconds
            rate_limit (float): Minimum seconds between requests
        """
        self.headless = headless
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.session = requests.Session()
        self.driver = None
        
        # Set up session headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def setup_driver(self) -> None:
        """
        Set up Selenium WebDriver with Chrome
        """
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
            
            logger.info("WebDriver setup completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {e}")
            raise
    
    def detect_platform(self, url: str) -> Optional[str]:
        """
        Detect platform from URL
        
        Args:
            url (str): URL to analyze
            
        Returns:
            Optional[str]: Platform name if detected, None otherwise
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
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning text: {e}")
            return text
    
    def handle_images_for_pdf(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """
        Extract and format images for PDF inclusion
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            base_url (str): Base URL for resolving relative image URLs
            
        Returns:
            List[Dict[str, Any]]: List of image information dictionaries
        """
        images = []
        
        try:
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                img_info = self._process_image(img, base_url)
                if img_info:
                    images.append(img_info)
            
            logger.info(f"Processed {len(images)} images for PDF")
            return images
            
        except Exception as e:
            logger.error(f"Error handling images: {e}")
            return []
    
    def _process_image(self, img_tag, base_url: str) -> Optional[Dict[str, Any]]:
        """
        Process individual image tag
        
        Args:
            img_tag: BeautifulSoup img tag
            base_url (str): Base URL for resolving relative URLs
            
        Returns:
            Optional[Dict[str, Any]]: Image information or None if processing fails
        """
        try:
            src = img_tag.get('src')
            if not src:
                return None
            
            # Convert relative URLs to absolute
            if src.startswith('http'):
                img_url = src
            elif src.startswith('//'):
                img_url = 'https:' + src
            else:
                img_url = urljoin(base_url, src)
            
            # Get image metadata
            alt_text = img_tag.get('alt', '')
            title = img_tag.get('title', '')
            width = img_tag.get('width')
            height = img_tag.get('height')
            
            img_info = {
                'url': img_url,
                'alt': self.clean_and_format_text(alt_text),
                'title': self.clean_and_format_text(title),
                'original_width': width,
                'original_height': height,
                'format': self._get_image_format(img_url)
            }
            
            return img_info
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None
    
    def _get_image_format(self, url: str) -> str:
        """
        Determine image format from URL
        
        Args:
            url (str): Image URL
            
        Returns:
            str: Image format (jpg, png, gif, etc.)
        """
        try:
            extension = url.split('.')[-1].lower().split('?')[0]
            
            # Map common extensions
            format_map = {
                'jpg': 'JPEG',
                'jpeg': 'JPEG', 
                'png': 'PNG',
                'gif': 'GIF',
                'bmp': 'BMP',
                'svg': 'SVG'
            }
            
            return format_map.get(extension, 'JPEG')
            
        except Exception:
            return 'JPEG'
    def get_page_content(self, url: str, use_selenium: bool = False) -> Optional[BeautifulSoup]:
        """
        Get page content using requests or selenium with rate limiting and error handling
        
        Args:
            url (str): URL to fetch
            use_selenium (bool): Whether to use Selenium instead of requests
            
        Returns:
            BeautifulSoup: Parsed HTML content or None if failed
        """
        try:
            # Enforce rate limiting
            self._enforce_rate_limit()
            
            logger.info(f"Fetching content from: {url}")
            
            if use_selenium:
                html_content = self._get_content_selenium(url)
            else:
                html_content = self._get_content_requests(url)
            
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            logger.info(f"Successfully parsed content from: {url}")
            return soup
            
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return None
    
    def _get_content_requests(self, url: str) -> Optional[str]:
        """
        Get content using requests with retry logic
        
        Args:
            url (str): URL to fetch
            
        Returns:
            Optional[str]: HTML content or None if failed
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                
        return None
    
    def _get_content_selenium(self, url: str) -> Optional[str]:
        """
        Get content using Selenium
        
        Args:
            url (str): URL to fetch
            
        Returns:
            Optional[str]: HTML content or None if failed
        """
        try:
            if not self.driver:
                self.setup_driver()
            
            self.driver.get(url)
            time.sleep(2)  # Wait for page to load
            return self.driver.page_source
            
        except Exception as e:
            logger.error(f"Selenium failed to fetch {url}: {e}")
            return None
    
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
        """
        pass
    
    def close_driver(self) -> None:
        """
        Close the WebDriver instance
        """
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("WebDriver closed")
    
    def create_standard_format(self, **kwargs) -> Dict[str, Any]:
        """
        Create a standardized return dictionary with all required keys
        
        Args:
            **kwargs: Key-value pairs to include in the dictionary
            
        Returns:
            Dict[str, Any]: Standardized dictionary with all required keys
        """
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
        
        # Clean text fields
        text_fields = ['title', 'problem_statement', 'input_format', 
                      'output_format', 'constraints', 'time_limit', 'memory_limit']
        
        for field in text_fields:
            if field in standard_dict and isinstance(standard_dict[field], str):
                standard_dict[field] = self.clean_and_format_text(standard_dict[field])
        
        return standard_dict
    
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
    
    def __del__(self):
        """
        Cleanup when object is destroyed
        """
        self.close_driver()
        if hasattr(self, 'session'):
            self.session.close()