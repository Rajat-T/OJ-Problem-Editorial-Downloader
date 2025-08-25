"""
Scraper package for OJ Problem Editorial Downloader
Contains base scraper class and platform-specific scrapers
"""

from .base_scraper import BaseScraper
from .atcoder_scraper import AtCoderScraper
from .codeforces_scraper import CodeforcesScraper
from .spoj_scraper import SPOJScraper

__all__ = [
    'BaseScraper',
    'AtCoderScraper', 
    'CodeforcesScraper',
    'SPOJScraper'
]