"""
Enhanced URL Validation Utility for OJ Problem Editorial Downloader
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse
from dataclasses import dataclass
from enum import Enum

from utils.error_handler import URLValidationError

logger = logging.getLogger(__name__)


class Platform(Enum):
    ATCODER = "atcoder"
    CODEFORCES = "codeforces"  
    SPOJ = "spoj"
    UNKNOWN = "unknown"


class URLType(Enum):
    PROBLEM = "problem"
    EDITORIAL = "editorial"
    CONTEST = "contest"
    UNKNOWN = "unknown"


@dataclass
class URLInfo:
    original_url: str
    normalized_url: str
    platform: Platform
    url_type: URLType
    is_valid: bool
    contest_id: Optional[str] = None
    problem_id: Optional[str] = None
    error_message: Optional[str] = None


class URLValidator:
    """Comprehensive URL validator for supported platforms"""
    
    PLATFORM_PATTERNS = {
        Platform.ATCODER: {
            URLType.PROBLEM: [
                r'^https?://(?:www\.)?atcoder\.jp/contests/([^/]+)/tasks/([^/?&#]+)',
            ],
            URLType.EDITORIAL: [
                r'^https?://(?:www\.)?atcoder\.jp/contests/([^/]+)/editorial',
            ]
        },
        Platform.CODEFORCES: {
            URLType.PROBLEM: [
                r'^https?://(?:www\.)?codeforces\.com/contest/(\d+)/problem/([A-Z]\d?)',
                r'^https?://(?:www\.)?codeforces\.com/problemset/problem/(\d+)/([A-Z]\d?)',
            ],
            URLType.EDITORIAL: [
                r'^https?://(?:www\.)?codeforces\.com/blog/entry/(\d+)',
            ]
        },
        Platform.SPOJ: {
            URLType.PROBLEM: [
                r'^https?://(?:www\.)?spoj\.com/problems/([A-Z0-9_]+)',
            ]
        }
    }
    
    def __init__(self):
        self.validation_cache = {}
    
    def validate_url(self, url: str) -> URLInfo:
        """Comprehensive URL validation"""
        if not url:
            return URLInfo("", "", Platform.UNKNOWN, URLType.UNKNOWN, False, 
                          error_message="Empty URL")
        
        original_url = url.strip()
        
        # Check cache
        if original_url in self.validation_cache:
            return self.validation_cache[original_url]
        
        try:
            # Basic validation
            parsed = urlparse(original_url)
            if not parsed.scheme or parsed.scheme not in ['http', 'https']:
                return self._invalid_result(original_url, "Invalid or missing scheme")
            
            if not parsed.netloc:
                return self._invalid_result(original_url, "Invalid domain")
            
            # Normalize URL
            normalized = self._normalize_url(original_url)
            
            # Detect platform and type
            platform, url_type, match = self._detect_platform_type(normalized)
            
            if platform == Platform.UNKNOWN:
                return self._invalid_result(original_url, "Unsupported platform", normalized)
            
            # Extract components
            contest_id, problem_id = self._extract_components(match, platform, url_type)
            
            result = URLInfo(
                original_url=original_url,
                normalized_url=normalized,
                platform=platform,
                url_type=url_type,
                is_valid=True,
                contest_id=contest_id,
                problem_id=problem_id
            )
            
            self.validation_cache[original_url] = result
            return result
            
        except Exception as e:
            return self._invalid_result(original_url, f"Validation error: {str(e)}")
    
    def _invalid_result(self, original_url: str, error: str, 
                       normalized: str = "") -> URLInfo:
        return URLInfo(original_url, normalized or original_url, 
                      Platform.UNKNOWN, URLType.UNKNOWN, False, 
                      error_message=error)
    
    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        scheme = 'https'
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        path = parsed.path.rstrip('/')
        return urlunparse((scheme, netloc, path, '', '', ''))
    
    def _detect_platform_type(self, url: str) -> Tuple[Platform, URLType, Optional[re.Match]]:
        for platform, url_types in self.PLATFORM_PATTERNS.items():
            for url_type, patterns in url_types.items():
                for pattern in patterns:
                    match = re.match(pattern, url, re.IGNORECASE)
                    if match:
                        return platform, url_type, match
        return Platform.UNKNOWN, URLType.UNKNOWN, None
    
    def _extract_components(self, match: Optional[re.Match], platform: Platform, 
                          url_type: URLType) -> Tuple[Optional[str], Optional[str]]:
        if not match:
            return None, None
        
        groups = match.groups()
        contest_id = problem_id = None
        
        if platform == Platform.ATCODER:
            contest_id = groups[0] if groups else None
            if url_type == URLType.PROBLEM and len(groups) > 1:
                problem_id = groups[1]
        elif platform == Platform.CODEFORCES:
            if url_type == URLType.PROBLEM:
                contest_id = groups[0] if groups else None
                problem_id = groups[1] if len(groups) > 1 else None
        elif platform == Platform.SPOJ:
            if url_type == URLType.PROBLEM:
                problem_id = groups[0] if groups else None
        
        return contest_id, problem_id
    
    def batch_validate(self, urls: List[str]) -> List[URLInfo]:
        return [self.validate_url(url) for url in urls]
    
    def suggest_corrections(self, url: str) -> List[str]:
        suggestions = []
        url_lower = url.lower().strip()
        
        # Add protocol if missing
        if not url_lower.startswith(('http://', 'https://')):
            suggestions.append(f"https://{url}")
        
        # Common domain fixes
        fixes = {
            'atcoder.com': 'atcoder.jp',
            'codeforce.com': 'codeforces.com',
            'spoj.pl': 'spoj.com'
        }
        
        for wrong, correct in fixes.items():
            if wrong in url_lower:
                suggestions.append(url_lower.replace(wrong, correct))
        
        return list(set(suggestions))


# Global instance
url_validator = URLValidator()