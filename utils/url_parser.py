"""
URL Parser for OJ Problem Editorial Downloader
Handles URL validation, parsing, and platform detection
"""

import re
from typing import Dict, Optional, Tuple, Any, List
from urllib.parse import urlparse, parse_qs, urljoin
import logging

logger = logging.getLogger(__name__)

class URLParser:
    """
    Utility class for parsing and validating competitive programming platform URLs
    """
    
    # Comprehensive platform patterns with variations
    PLATFORM_PATTERNS = {
        'AtCoder': {
            'problem': [
                r'https?://(?:www\.)?atcoder\.jp/contests/([^/]+)/tasks/([^/?]+)(?:\?.*)?',
                r'https?://(?:www\.)?atcoder\.jp/contests/([^/]+)/tasks/([^/?]+)/?'
            ],
            'editorial': [
                r'https?://(?:www\.)?atcoder\.jp/contests/([^/]+)/editorial(?:\?.*)?',
                r'https?://(?:www\.)?atcoder\.jp/contests/([^/]+)/editorial/?'
            ],
            'contest': [
                r'https?://(?:www\.)?atcoder\.jp/contests/([^/?]+)(?:\?.*)?',
                r'https?://(?:www\.)?atcoder\.jp/contests/([^/?]+)/?'
            ],
            'base_url': 'https://atcoder.jp'
        },
        'Codeforces': {
            'problem': [
                r'https?://(?:www\.)?codeforces\.com/contest/(\d+)/problem/([A-Z]\d?)(?:\?.*)?',
                r'https?://(?:www\.)?codeforces\.com/problemset/problem/(\d+)/([A-Z]\d?)(?:\?.*)?',
                r'https?://(?:www\.)?codeforces\.com/contest/(\d+)/problem/([A-Z]\d?)/?',
                r'https?://(?:www\.)?codeforces\.com/problemset/problem/(\d+)/([A-Z]\d?)/?' 
            ],
            'blog': [
                r'https?://(?:www\.)?codeforces\.com/blog/entry/(\d+)(?:\?.*)?',
                r'https?://(?:www\.)?codeforces\.com/blog/entry/(\d+)/?'
            ],
            'contest': [
                r'https?://(?:www\.)?codeforces\.com/contest/(\d+)(?:\?.*)?',
                r'https?://(?:www\.)?codeforces\.com/contest/(\d+)/?'
            ],
            'base_url': 'https://codeforces.com'
        },
        'SPOJ': {
            'problem': [
                r'https?://(?:www\.)?spoj\.com/problems/([A-Z0-9_]+)(?:/.*)?(?:\?.*)?',
                r'https?://(?:www\.)?spoj\.com/problems/([A-Z0-9_]+)/?'
            ],
            'base_url': 'https://www.spoj.com'
        }
    }
    
    def __init__(self):
        """
        Initialize URL Parser
        """
        self.supported_platforms = list(self.PLATFORM_PATTERNS.keys())
    
    def identify_platform(self, url: str) -> Optional[str]:
        """
        Identify which platform a URL belongs to
        
        Args:
            url (str): URL to analyze
            
        Returns:
            Optional[str]: Platform name if identified, None otherwise
        """
        try:
            normalized_url = self.normalize_url(url)
            
            for platform, patterns in self.PLATFORM_PATTERNS.items():
                for pattern_type, pattern_list in patterns.items():
                    if pattern_type == 'base_url':
                        continue
                    if isinstance(pattern_list, list):
                        for pattern in pattern_list:
                            if re.match(pattern, normalized_url):
                                logger.debug(f"Detected platform: {platform} for URL: {normalized_url}")
                                return platform
            
            logger.warning(f"No platform detected for URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error identifying platform for URL {url}: {e}")
            return None
    
    def parse_url(self, url: str) -> Dict[str, Any]:
        """
        Parse URL and extract relevant information
        
        Args:
            url (str): URL to parse
            
        Returns:
            Dict[str, Any]: Parsed URL information
        """
        try:
            normalized_url = self.normalize_url(url)
            parsed = urlparse(normalized_url)
            
            result = {
                'original_url': url,
                'normalized_url': normalized_url,
                'domain': parsed.netloc,
                'path': parsed.path,
                'query': dict(parse_qs(parsed.query)),
                'platform': None,
                'type': None,
                'is_valid': False
            }
            
            # Identify platform
            platform = self.identify_platform(normalized_url)
            if not platform:
                result['error'] = 'Unsupported platform or invalid URL'
                return result
            
            result['platform'] = platform
            result['is_valid'] = True
            
            # Extract platform-specific data
            if platform == 'AtCoder':
                platform_data = self.parse_atcoder_url(normalized_url)
            elif platform == 'Codeforces':
                platform_data = self.parse_codeforces_url(normalized_url)
            elif platform == 'SPOJ':
                platform_data = self.parse_spoj_url(normalized_url)
            else:
                platform_data = {}
            
            # Merge platform-specific data
            result.update(platform_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing URL {url}: {e}")
            return {
                'original_url': url,
                'error': str(e),
                'is_valid': False
            }
    
    def parse_atcoder_url(self, url: str) -> Dict[str, Any]:
        """
        Parse AtCoder URL and extract contest ID, task ID, and type
        
        Args:
            url (str): AtCoder URL to parse
            
        Returns:
            Dict[str, Any]: Parsed URL information
        """
        try:
            normalized_url = self.normalize_url(url)
            
            # Check problem URL
            for pattern in self.PLATFORM_PATTERNS['AtCoder']['problem']:
                match = re.match(pattern, normalized_url)
                if match:
                    contest_id, task_id = match.groups()
                    return {
                        'platform': 'AtCoder',
                        'type': 'problem',
                        'contest_id': contest_id,
                        'task_id': task_id,
                        'problem_id': task_id,
                        'url': normalized_url,
                        'editorial_url': f"https://atcoder.jp/contests/{contest_id}/editorial",
                        'contest_url': f"https://atcoder.jp/contests/{contest_id}"
                    }
            
            # Check editorial URL
            for pattern in self.PLATFORM_PATTERNS['AtCoder']['editorial']:
                match = re.match(pattern, normalized_url)
                if match:
                    contest_id = match.group(1)
                    return {
                        'platform': 'AtCoder',
                        'type': 'editorial',
                        'contest_id': contest_id,
                        'url': normalized_url,
                        'contest_url': f"https://atcoder.jp/contests/{contest_id}"
                    }
            
            # Check contest URL
            for pattern in self.PLATFORM_PATTERNS['AtCoder']['contest']:
                match = re.match(pattern, normalized_url)
                if match:
                    contest_id = match.group(1)
                    return {
                        'platform': 'AtCoder',
                        'type': 'contest',
                        'contest_id': contest_id,
                        'url': normalized_url,
                        'editorial_url': f"https://atcoder.jp/contests/{contest_id}/editorial"
                    }
            
            return {'platform': 'AtCoder', 'type': 'unknown', 'url': url, 'error': 'Invalid AtCoder URL format'}
            
        except Exception as e:
            logger.error(f"Error parsing AtCoder URL {url}: {e}")
            return {'platform': 'AtCoder', 'type': 'error', 'url': url, 'error': str(e)}
    
    def parse_codeforces_url(self, url: str) -> Dict[str, Any]:
        """
        Parse Codeforces URL and extract contest ID, problem ID, and type
        
        Args:
            url (str): Codeforces URL to parse
            
        Returns:
            Dict[str, Any]: Parsed URL information
        """
        try:
            normalized_url = self.normalize_url(url)
            
            # Check problem URL
            for pattern in self.PLATFORM_PATTERNS['Codeforces']['problem']:
                match = re.match(pattern, normalized_url)
                if match:
                    contest_id, problem_id = match.groups()
                    return {
                        'platform': 'Codeforces',
                        'type': 'problem',
                        'contest_id': contest_id,
                        'problem_id': problem_id,
                        'url': normalized_url,
                        'contest_url': f"https://codeforces.com/contest/{contest_id}",
                        'normalized_problem_url': f"https://codeforces.com/contest/{contest_id}/problem/{problem_id}"
                    }
            
            # Check blog URL (editorials)
            for pattern in self.PLATFORM_PATTERNS['Codeforces']['blog']:
                match = re.match(pattern, normalized_url)
                if match:
                    blog_id = match.group(1)
                    return {
                        'platform': 'Codeforces',
                        'type': 'blog',
                        'blog_id': blog_id,
                        'url': normalized_url
                    }
            
            # Check contest URL
            for pattern in self.PLATFORM_PATTERNS['Codeforces']['contest']:
                match = re.match(pattern, normalized_url)
                if match:
                    contest_id = match.group(1)
                    return {
                        'platform': 'Codeforces',
                        'type': 'contest',
                        'contest_id': contest_id,
                        'url': normalized_url
                    }
            
            return {'platform': 'Codeforces', 'type': 'unknown', 'url': url, 'error': 'Invalid Codeforces URL format'}
            
        except Exception as e:
            logger.error(f"Error parsing Codeforces URL {url}: {e}")
            return {'platform': 'Codeforces', 'type': 'error', 'url': url, 'error': str(e)}
    
    def parse_spoj_url(self, url: str) -> Dict[str, Any]:
        """
        Parse SPOJ URL and extract problem code
        
        Args:
            url (str): SPOJ URL to parse
            
        Returns:
            Dict[str, Any]: Parsed URL information
        """
        try:
            normalized_url = self.normalize_url(url)
            
            # Check problem URL
            for pattern in self.PLATFORM_PATTERNS['SPOJ']['problem']:
                match = re.match(pattern, normalized_url)
                if match:
                    problem_code = match.group(1)
                    return {
                        'platform': 'SPOJ',
                        'type': 'problem',
                        'problem_code': problem_code,
                        'problem_id': problem_code,
                        'url': normalized_url
                    }
            
            return {'platform': 'SPOJ', 'type': 'unknown', 'url': url, 'error': 'Invalid SPOJ URL format'}
            
        except Exception as e:
            logger.error(f"Error parsing SPOJ URL {url}: {e}")
            return {'platform': 'SPOJ', 'type': 'error', 'url': url, 'error': str(e)}
    
    def validate_atcoder_url(self, url: str) -> bool:
        """
        Validate AtCoder URL format
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid AtCoder URL
        """
        try:
            normalized_url = self.normalize_url(url)
            
            for url_type, patterns in self.PLATFORM_PATTERNS['AtCoder'].items():
                if url_type == 'base_url':
                    continue
                if isinstance(patterns, list):
                    for pattern in patterns:
                        if re.match(pattern, normalized_url):
                            return True
            return False
            
        except Exception as e:
            logger.error(f"Error validating AtCoder URL {url}: {e}")
            return False
    
    def validate_codeforces_url(self, url: str) -> bool:
        """
        Validate Codeforces URL format
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid Codeforces URL
        """
        try:
            normalized_url = self.normalize_url(url)
            
            for url_type, patterns in self.PLATFORM_PATTERNS['Codeforces'].items():
                if url_type == 'base_url':
                    continue
                if isinstance(patterns, list):
                    for pattern in patterns:
                        if re.match(pattern, normalized_url):
                            return True
            return False
            
        except Exception as e:
            logger.error(f"Error validating Codeforces URL {url}: {e}")
            return False
    
    def validate_spoj_url(self, url: str) -> bool:
        """
        Validate SPOJ URL format
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid SPOJ URL
        """
        try:
            normalized_url = self.normalize_url(url)
            
            for url_type, patterns in self.PLATFORM_PATTERNS['SPOJ'].items():
                if url_type == 'base_url':
                    continue
                if isinstance(patterns, list):
                    for pattern in patterns:
                        if re.match(pattern, normalized_url):
                            return True
            return False
            
        except Exception as e:
            logger.error(f"Error validating SPOJ URL {url}: {e}")
            return False
    
    def generate_editorial_url(self, problem_url: str) -> Optional[str]:
        """
        Generate editorial URL from problem URL where possible
        
        Args:
            problem_url (str): Problem URL
            
        Returns:
            Optional[str]: Editorial URL if can be generated, None otherwise
        """
        try:
            platform = self.identify_platform(problem_url)
            
            if platform == 'AtCoder':
                parsed = self.parse_atcoder_url(problem_url)
                if parsed.get('type') == 'problem' and 'contest_id' in parsed:
                    return f"https://atcoder.jp/contests/{parsed['contest_id']}/editorial"
                    
            elif platform == 'Codeforces':
                # Codeforces doesn't have standard editorial URLs
                # Editorials are usually in blog posts
                logger.info("Codeforces editorials are typically in blog posts, no standard URL format")
                return None
                
            elif platform == 'SPOJ':
                # SPOJ doesn't have official editorials
                logger.info("SPOJ doesn't typically have official editorials")
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating editorial URL for {problem_url}: {e}")
            return None
    
    def extract_ids_from_url(self, url: str) -> Dict[str, str]:
        """
        Extract problem ID and contest ID from URL
        
        Args:
            url (str): URL to extract IDs from
            
        Returns:
            Dict[str, str]: Dictionary with extracted IDs
        """
        try:
            platform = self.identify_platform(url)
            
            if platform == 'AtCoder':
                parsed = self.parse_atcoder_url(url)
                return {
                    'platform': platform,
                    'contest_id': parsed.get('contest_id', ''),
                    'problem_id': parsed.get('task_id', ''),
                    'task_id': parsed.get('task_id', '')
                }
                
            elif platform == 'Codeforces':
                parsed = self.parse_codeforces_url(url)
                return {
                    'platform': platform,
                    'contest_id': parsed.get('contest_id', ''),
                    'problem_id': parsed.get('problem_id', ''),
                    'blog_id': parsed.get('blog_id', '')
                }
                
            elif platform == 'SPOJ':
                parsed = self.parse_spoj_url(url)
                return {
                    'platform': platform,
                    'problem_id': parsed.get('problem_code', ''),
                    'problem_code': parsed.get('problem_code', '')
                }
            
            return {'platform': platform or 'Unknown'}
            
        except Exception as e:
            logger.error(f"Error extracting IDs from URL {url}: {e}")
            return {'error': str(e)}
    
    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is valid and supported
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid and supported
        """
        try:
            if not url or not url.strip():
                return False
            
            # Basic URL validation
            normalized_url = self.normalize_url(url)
            parsed = urlparse(normalized_url)
            if not all([parsed.scheme, parsed.netloc]):
                return False
            
            # Check if platform is supported
            platform = self.identify_platform(normalized_url)
            if not platform:
                return False
            
            # Platform-specific validation
            if platform == 'AtCoder':
                return self.validate_atcoder_url(normalized_url)
            elif platform == 'Codeforces':
                return self.validate_codeforces_url(normalized_url)
            elif platform == 'SPOJ':
                return self.validate_spoj_url(normalized_url)
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating URL {url}: {e}")
            return False
    
    def get_platform_base_url(self, platform: str) -> Optional[str]:
        """
        Get base URL for a platform
        
        Args:
            platform (str): Platform name
            
        Returns:
            Optional[str]: Base URL if platform exists
        """
        return self.PLATFORM_PATTERNS.get(platform, {}).get('base_url')
    
    def get_supported_platforms(self) -> List[str]:
        """
        Get list of supported platforms
        
        Returns:
            List[str]: List of supported platform names
        """
        return list(self.PLATFORM_PATTERNS.keys())
    
    def get_url_type(self, url: str) -> Optional[str]:
        """
        Get the type of URL (problem, editorial, contest, etc.)
        
        Args:
            url (str): URL to analyze
            
        Returns:
            Optional[str]: URL type if identified
        """
        try:
            parsed_data = self.parse_url(url)
            return parsed_data.get('type')
        except Exception as e:
            logger.error(f"Error getting URL type for {url}: {e}")
            return None
    
    def batch_validate_urls(self, urls: List[str]) -> Dict[str, bool]:
        """
        Validate multiple URLs in batch
        
        Args:
            urls (List[str]): List of URLs to validate
            
        Returns:
            Dict[str, bool]: Dictionary mapping URLs to validation results
        """
        results = {}
        for url in urls:
            results[url] = self.is_valid_url(url)
        return results
    
    def extract_all_ids(self, url: str) -> Dict[str, Any]:
        """
        Extract all possible IDs and information from URL
        
        Args:
            url (str): URL to extract from
            
        Returns:
            Dict[str, Any]: All extracted information
        """
        try:
            parsed_data = self.parse_url(url)
            ids_data = self.extract_ids_from_url(url)
            
            # Combine both results
            result = {
                **parsed_data,
                **ids_data,
                'editorial_url': self.generate_editorial_url(url)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting all IDs from {url}: {e}")
            return {'error': str(e)}
    def get_related_urls(self, url: str) -> Dict[str, str]:
        """
        Get related URLs for a given URL (e.g., editorial URL for problem URL)
        
        Args:
            url (str): Source URL
            
        Returns:
            Dict[str, str]: Dictionary of related URLs
        """
        try:
            parsed_data = self.parse_url(url)
            platform = parsed_data.get('platform')
            url_type = parsed_data.get('type')
            
            related_urls = {}
            
            if platform == 'AtCoder':
                if url_type == 'problem':
                    contest_id = parsed_data.get('contest_id')
                    if contest_id:
                        related_urls['editorial'] = f"https://atcoder.jp/contests/{contest_id}/editorial"
                        related_urls['contest'] = f"https://atcoder.jp/contests/{contest_id}"
                
                elif url_type == 'editorial':
                    contest_id = parsed_data.get('contest_id')
                    if contest_id:
                        related_urls['contest'] = f"https://atcoder.jp/contests/{contest_id}"
                        # Can't generate specific problem URLs without task ID
                        
                elif url_type == 'contest':
                    contest_id = parsed_data.get('contest_id')
                    if contest_id:
                        related_urls['editorial'] = f"https://atcoder.jp/contests/{contest_id}/editorial"
            
            elif platform == 'Codeforces':
                if url_type == 'problem':
                    contest_id = parsed_data.get('contest_id')
                    if contest_id:
                        related_urls['contest'] = f"https://codeforces.com/contest/{contest_id}"
                
                elif url_type == 'contest':
                    contest_id = parsed_data.get('contest_id')
                    if contest_id:
                        # Common problem IDs in Codeforces contests
                        for problem_id in ['A', 'B', 'C', 'D', 'E', 'F']:
                            related_urls[f'problem_{problem_id}'] = f"https://codeforces.com/contest/{contest_id}/problem/{problem_id}"
            
            # Add editorial URL if can be generated
            editorial_url = self.generate_editorial_url(url)
            if editorial_url:
                related_urls['editorial'] = editorial_url
            
            return related_urls
            
        except Exception as e:
            logger.error(f"Error getting related URLs for {url}: {e}")
            return {}
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL to standard format, handling different variations
        
        Args:
            url (str): URL to normalize
            
        Returns:
            str: Normalized URL
        """
        try:
            url = url.strip()
            
            # Add https if no scheme provided
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Parse URL
            parsed = urlparse(url)
            
            # Normalize scheme to https
            scheme = 'https'
            
            # Normalize domain (remove/add www as needed)
            domain = parsed.netloc.lower()
            
            # Platform-specific normalization
            if 'atcoder.jp' in domain:
                # AtCoder: remove www if present
                domain = domain.replace('www.', '')
                if not domain.startswith('atcoder.jp'):
                    domain = 'atcoder.jp'
                    
            elif 'codeforces.com' in domain:
                # Codeforces: remove www if present
                domain = domain.replace('www.', '')
                if not domain.startswith('codeforces.com'):
                    domain = 'codeforces.com'
                # Convert problemset format to contest format
                if '/problemset/problem/' in parsed.path:
                    path_match = re.match(r'/problemset/problem/(\d+)/([A-Z]\d?)', parsed.path)
                    if path_match:
                        contest_id, problem_id = path_match.groups()
                        normalized_path = f'/contest/{contest_id}/problem/{problem_id}'
                        return f"{scheme}://{domain}{normalized_path}"
                        
            elif 'spoj.com' in domain:
                # SPOJ: ensure www is present
                if not domain.startswith('www.'):
                    domain = 'www.' + domain
                if not domain.startswith('www.spoj.com'):
                    domain = 'www.spoj.com'
            
            # Clean path - remove trailing slashes, keep query parameters
            path = parsed.path.rstrip('/')
            query = f'?{parsed.query}' if parsed.query else ''
            
            normalized_url = f"{scheme}://{domain}{path}{query}"
            
            logger.debug(f"Normalized URL: {url} -> {normalized_url}")
            return normalized_url
            
        except Exception as e:
            logger.error(f"Error normalizing URL {url}: {e}")
            return url
