"""
Comprehensive Error Handling Module for OJ Problem Editorial Downloader

This module provides custom exceptions, error detection utilities, and recovery mechanisms
for handling various types of errors that can occur during scraping and PDF generation.
"""

import logging
import time
import traceback
import functools
import sys
import os
import shutil
from typing import Dict, Any, Optional, Callable, List, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import requests
from requests.exceptions import (
    RequestException, Timeout, ConnectionError, HTTPError, 
    TooManyRedirects, InvalidURL, ChunkedEncodingError
)
from selenium.common.exceptions import (
    WebDriverException, TimeoutException, NoSuchElementException,
    ElementNotInteractableException, StaleElementReferenceException,
    SessionNotCreatedException, InvalidSessionIdException
)
from urllib3.exceptions import MaxRetryError, NewConnectionError
import socket

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""
    NETWORK = "network"
    URL_VALIDATION = "url_validation"
    CONTENT_MISSING = "content_missing"
    CAPTCHA = "captcha"
    RATE_LIMITING = "rate_limiting"
    PDF_GENERATION = "pdf_generation"
    FILE_SYSTEM = "file_system"
    PERMISSION = "permission"
    PLATFORM_SPECIFIC = "platform_specific"
    SELENIUM = "selenium"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """Structured error information"""
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    original_exception: Optional[Exception] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    traceback_str: Optional[str] = None
    recovery_suggestions: List[str] = field(default_factory=list)
    user_message: Optional[str] = None


# =============================================================================
# Custom Exception Classes
# =============================================================================

class OJDownloaderError(Exception):
    """Base exception for all OJ Downloader specific errors"""
    
    def __init__(self, message: str, error_info: Optional[ErrorInfo] = None):
        super().__init__(message)
        self.error_info = error_info or ErrorInfo(
            message=message,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM
        )


class NetworkError(OJDownloaderError):
    """Network-related errors (timeouts, connection failures, etc.)"""
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None, 
                 url: Optional[str] = None):
        error_info = ErrorInfo(
            message=message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            original_exception=original_exception,
            context={"url": url} if url else {},
            recovery_suggestions=[
                "Check internet connection",
                "Verify URL is accessible",
                "Try again after a few minutes",
                "Check if the website is down"
            ]
        )
        super().__init__(message, error_info)


class URLValidationError(OJDownloaderError):
    """Invalid URL or unsupported platform errors"""
    
    def __init__(self, message: str, url: Optional[str] = None):
        error_info = ErrorInfo(
            message=message,
            category=ErrorCategory.URL_VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            context={"url": url} if url else {},
            recovery_suggestions=[
                "Check URL format",
                "Ensure the platform is supported",
                "Try a different problem URL from the same platform"
            ],
            user_message="Please check the URL format and ensure it's from a supported platform."
        )
        super().__init__(message, error_info)


class ContentMissingError(OJDownloaderError):
    """Missing problem content, 404 errors, etc."""
    
    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None):
        error_info = ErrorInfo(
            message=message,
            category=ErrorCategory.CONTENT_MISSING,
            severity=ErrorSeverity.MEDIUM,
            context={"url": url, "status_code": status_code},
            recovery_suggestions=[
                "Verify the problem/editorial exists",
                "Check if the contest is still active",
                "Try the URL in a web browser",
                "Contact the platform if the content should exist"
            ],
            user_message="The requested content could not be found. Please verify the URL."
        )
        super().__init__(message, error_info)


class CaptchaDetectedError(OJDownloaderError):
    """CAPTCHA detected during scraping"""
    
    def __init__(self, message: str, url: Optional[str] = None):
        error_info = ErrorInfo(
            message=message,
            category=ErrorCategory.CAPTCHA,
            severity=ErrorSeverity.HIGH,
            context={"url": url} if url else {},
            recovery_suggestions=[
                "Wait for some time before retrying",
                "Try accessing the site manually first",
                "Reduce scraping frequency",
                "Use a different IP address if possible"
            ],
            user_message="CAPTCHA detected. Please try again later or reduce the scraping frequency."
        )
        super().__init__(message, error_info)


class RateLimitError(OJDownloaderError):
    """Rate limiting errors from servers"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, url: Optional[str] = None):
        error_info = ErrorInfo(
            message=message,
            category=ErrorCategory.RATE_LIMITING,
            severity=ErrorSeverity.MEDIUM,
            context={"url": url, "retry_after": retry_after},
            recovery_suggestions=[
                f"Wait {retry_after} seconds before retrying" if retry_after else "Wait before retrying",
                "Increase delay between requests",
                "Reduce concurrent requests"
            ],
            user_message=f"Rate limit exceeded. Please wait {retry_after} seconds." if retry_after 
                        else "Rate limit exceeded. Please wait before retrying."
        )
        super().__init__(message, error_info)


class PDFGenerationError(OJDownloaderError):
    """PDF generation related errors"""
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None, 
                 output_path: Optional[str] = None):
        error_info = ErrorInfo(
            message=message,
            category=ErrorCategory.PDF_GENERATION,
            severity=ErrorSeverity.HIGH,
            original_exception=original_exception,
            context={"output_path": output_path} if output_path else {},
            recovery_suggestions=[
                "Check if output directory exists and is writable",
                "Ensure sufficient disk space",
                "Verify image URLs are accessible",
                "Try with simpler content first"
            ],
            user_message="Failed to generate PDF. Please check the output directory and try again."
        )
        super().__init__(message, error_info)


class FileSystemError(OJDownloaderError):
    """File system related errors (permissions, disk space, etc.)"""
    
    def __init__(self, message: str, path: Optional[str] = None, 
                 original_exception: Optional[Exception] = None):
        error_info = ErrorInfo(
            message=message,
            category=ErrorCategory.FILE_SYSTEM,
            severity=ErrorSeverity.HIGH,
            original_exception=original_exception,
            context={"path": path} if path else {},
            recovery_suggestions=[
                "Check file/directory permissions",
                "Ensure sufficient disk space",
                "Verify the path exists",
                "Try a different output location"
            ],
            user_message="File system error occurred. Please check permissions and disk space."
        )
        super().__init__(message, error_info)


# =============================================================================
# Error Detection Utilities
# =============================================================================

class ErrorDetector:
    """Utilities for detecting specific types of errors"""
    
    @staticmethod
    def is_network_error(exception: Exception) -> bool:
        """Check if exception is a network-related error"""
        network_exceptions = (
            ConnectionError, Timeout, socket.timeout, socket.gaierror,
            MaxRetryError, NewConnectionError, ChunkedEncodingError,
            OSError  # Can occur for network issues
        )
        return isinstance(exception, network_exceptions)
    
    @staticmethod
    def is_http_error(exception: Exception) -> Tuple[bool, Optional[int]]:
        """Check if exception is an HTTP error and return status code"""
        if isinstance(exception, HTTPError):
            return True, exception.response.status_code if exception.response else None
        return False, None
    
    @staticmethod
    def is_404_error(exception: Exception) -> bool:
        """Check if exception is a 404 error"""
        is_http, status_code = ErrorDetector.is_http_error(exception)
        return is_http and status_code == 404
    
    @staticmethod
    def is_rate_limit_error(exception: Exception) -> Tuple[bool, Optional[int]]:
        """Check if exception is a rate limit error and extract retry-after"""
        is_http, status_code = ErrorDetector.is_http_error(exception)
        if is_http and status_code in [429, 503]:
            retry_after = None
            if hasattr(exception, 'response') and exception.response:
                retry_after_header = exception.response.headers.get('Retry-After')
                if retry_after_header:
                    try:
                        retry_after = int(retry_after_header)
                    except ValueError:
                        pass
            return True, retry_after
        return False, None
    
    @staticmethod
    def is_captcha_detected(content: str) -> bool:
        """Detect CAPTCHA in page content"""
        captcha_indicators = [
            'captcha', 'recaptcha', 'hcaptcha', 'bot detection',
            'verify you are human', 'security check', 'cloudflare',
            'please complete', 'anti-bot', 'verification required'
        ]
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in captcha_indicators)
    
    @staticmethod
    def is_selenium_error(exception: Exception) -> bool:
        """Check if exception is a Selenium-related error"""
        selenium_exceptions = (
            WebDriverException, TimeoutException, NoSuchElementException,
            ElementNotInteractableException, StaleElementReferenceException,
            SessionNotCreatedException, InvalidSessionIdException
        )
        return isinstance(exception, selenium_exceptions)
    
    @staticmethod
    def check_disk_space(path: str, required_mb: int = 50) -> bool:
        """Check if there's sufficient disk space"""
        try:
            statvfs = os.statvfs(path)
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            free_mb = free_bytes / (1024 * 1024)
            return free_mb >= required_mb
        except (OSError, AttributeError):
            # Windows doesn't have os.statvfs, fallback to shutil
            try:
                free_bytes = shutil.disk_usage(path).free
                free_mb = free_bytes / (1024 * 1024)
                return free_mb >= required_mb
            except Exception:
                return True  # Assume sufficient space if can't check


# =============================================================================
# Error Context Manager
# =============================================================================

class ErrorContext:
    """Context manager for comprehensive error handling"""
    
    def __init__(self, operation: str, url: Optional[str] = None, 
                 retry_attempts: int = 3, retry_delay: float = 1.0):
        self.operation = operation
        self.url = url
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.current_attempt = 0
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_value:
            self._handle_exception(exc_value)
        return False  # Don't suppress exceptions
    
    def _handle_exception(self, exception: Exception):
        """Handle and classify exceptions"""
        error_info = self._classify_exception(exception)
        
        # Log the error
        logger.error(f"Error in {self.operation}: {error_info.message}")
        if error_info.traceback_str:
            logger.debug(f"Traceback: {error_info.traceback_str}")
        
        # Store error information for potential recovery
        self._store_error_info(error_info)
    
    def _classify_exception(self, exception: Exception) -> ErrorInfo:
        """Classify exception into appropriate error type"""
        # Network errors
        if ErrorDetector.is_network_error(exception):
            return ErrorInfo(
                message=f"Network error: {str(exception)}",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.HIGH,
                original_exception=exception,
                context={"url": self.url, "operation": self.operation},
                traceback_str=traceback.format_exc()
            )
        
        # HTTP errors
        is_http, status_code = ErrorDetector.is_http_error(exception)
        if is_http:
            if status_code == 404:
                return ErrorInfo(
                    message=f"Content not found (404): {self.url}",
                    category=ErrorCategory.CONTENT_MISSING,
                    severity=ErrorSeverity.MEDIUM,
                    original_exception=exception,
                    context={"url": self.url, "status_code": status_code}
                )
            elif status_code in [429, 503]:
                is_rate_limit, retry_after = ErrorDetector.is_rate_limit_error(exception)
                return ErrorInfo(
                    message=f"Rate limit exceeded: {status_code}",
                    category=ErrorCategory.RATE_LIMITING,
                    severity=ErrorSeverity.MEDIUM,
                    original_exception=exception,
                    context={"url": self.url, "status_code": status_code, "retry_after": retry_after}
                )
        
        # Selenium errors
        if ErrorDetector.is_selenium_error(exception):
            return ErrorInfo(
                message=f"Browser automation error: {str(exception)}",
                category=ErrorCategory.SELENIUM,
                severity=ErrorSeverity.HIGH,
                original_exception=exception,
                context={"url": self.url, "operation": self.operation}
            )
        
        # Generic error
        return ErrorInfo(
            message=f"Unexpected error: {str(exception)}",
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            original_exception=exception,
            context={"operation": self.operation},
            traceback_str=traceback.format_exc()
        )
    
    def _store_error_info(self, error_info: ErrorInfo):
        """Store error information for potential recovery or reporting"""
        # This could be extended to store in a database or file
        # For now, we'll just add it to the context
        if not hasattr(self, 'errors'):
            self.errors = []
        self.errors.append(error_info)


# =============================================================================
# Retry Decorator
# =============================================================================

def retry_on_error(max_attempts: int = 3, delay: float = 1.0, 
                   backoff_factor: float = 2.0, 
                   retryable_errors: Optional[List[type]] = None):
    """
    Decorator for automatic retry on specific errors
    
    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay between retries (seconds)
        backoff_factor: Multiplier for delay on each retry
        retryable_errors: List of exception types to retry on
    """
    if retryable_errors is None:
        retryable_errors = [
            ConnectionError, Timeout, socket.timeout, socket.gaierror,
            MaxRetryError, NewConnectionError, ChunkedEncodingError,
            TimeoutException, WebDriverException
        ]
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    if not any(isinstance(e, error_type) for error_type in retryable_errors):
                        raise
                    
                    # Don't retry on last attempt
                    if attempt == max_attempts - 1:
                        break
                    
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {str(e)}. "
                                 f"Retrying in {current_delay} seconds...")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
            # If we get here, all attempts failed
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError("All retry attempts failed but no exception was captured")
        
        return wrapper
    return decorator


# =============================================================================
# Error Recovery Mechanisms
# =============================================================================

class ErrorRecovery:
    """Utilities for error recovery and graceful degradation"""
    
    @staticmethod
    def create_fallback_content(url: str, error: Exception) -> Dict[str, Any]:
        """Create fallback content when scraping fails"""
        return {
            'title': f'Content unavailable - {url}',
            'problem_statement': f'Error occurred while fetching content: {str(error)}',
            'input_format': 'N/A',
            'output_format': 'N/A',
            'constraints': 'N/A',
            'examples': [],
            'time_limit': 'N/A',
            'memory_limit': 'N/A',
            'images': [],
            'error_occurred': True,
            'error_message': str(error),
            'url': url,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def sanitize_content(content: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize content to handle missing or corrupted data"""
        sanitized = content.copy()
        
        # Ensure required fields exist
        required_fields = {
            'title': 'Untitled',
            'problem_statement': 'No content available',
            'input_format': '',
            'output_format': '',
            'constraints': '',
            'examples': [],
            'time_limit': '',
            'memory_limit': '',
            'images': []
        }
        
        for field, default_value in required_fields.items():
            if field not in sanitized or sanitized[field] is None:
                sanitized[field] = default_value
            elif isinstance(sanitized[field], str):
                # Clean up string fields
                sanitized[field] = sanitized[field].strip()
        
        # Ensure examples is a list
        if not isinstance(sanitized['examples'], list):
            sanitized['examples'] = []
        
        # Ensure images is a list
        if not isinstance(sanitized['images'], list):
            sanitized['images'] = []
        
        return sanitized
    
    @staticmethod
    def suggest_alternatives(url: str, error_category: ErrorCategory) -> List[str]:
        """Suggest alternative actions based on error category"""
        suggestions = []
        
        if error_category == ErrorCategory.NETWORK:
            suggestions.extend([
                "Check your internet connection",
                "Try again in a few minutes",
                "Verify the website is accessible",
                "Use a VPN if the site is blocked"
            ])
        elif error_category == ErrorCategory.CONTENT_MISSING:
            suggestions.extend([
                "Verify the URL is correct",
                "Check if the contest/problem is still available",
                "Try accessing the page manually in a browser",
                "Look for alternative sources of the same problem"
            ])
        elif error_category == ErrorCategory.RATE_LIMITING:
            suggestions.extend([
                "Wait longer between requests",
                "Reduce the number of concurrent requests",
                "Try again during off-peak hours"
            ])
        elif error_category == ErrorCategory.CAPTCHA:
            suggestions.extend([
                "Access the site manually first to solve CAPTCHA",
                "Wait for an extended period before retrying",
                "Use different user agents or IP addresses"
            ])
        
        return suggestions


# =============================================================================
# Error Reporting
# =============================================================================

class ErrorReporter:
    """Centralized error reporting and logging"""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self.error_history: List[ErrorInfo] = []
    
    def report_error(self, error_info: ErrorInfo, context: Optional[Dict[str, Any]] = None):
        """Report an error with full context"""
        # Add to history
        self.error_history.append(error_info)
        
        # Log based on severity
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"CRITICAL ERROR: {error_info.message}")
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(f"ERROR: {error_info.message}")
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"WARNING: {error_info.message}")
        else:
            logger.info(f"INFO: {error_info.message}")
        
        # Log additional context
        if error_info.context:
            logger.debug(f"Context: {error_info.context}")
        
        if context:
            logger.debug(f"Additional context: {context}")
        
        # Log traceback for debugging
        if error_info.traceback_str:
            logger.debug(f"Traceback: {error_info.traceback_str}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all reported errors"""
        if not self.error_history:
            return {"total_errors": 0, "categories": {}, "severity_counts": {}}
        
        categories = {}
        severity_counts = {}
        
        for error in self.error_history:
            # Count by category
            cat = error.category.value
            categories[cat] = categories.get(cat, 0) + 1
            
            # Count by severity
            sev = error.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        return {
            "total_errors": len(self.error_history),
            "categories": categories,
            "severity_counts": severity_counts,
            "recent_errors": [
                {
                    "message": e.message,
                    "category": e.category.value,
                    "severity": e.severity.value,
                    "timestamp": e.timestamp.isoformat()
                }
                for e in self.error_history[-10:]  # Last 10 errors
            ]
        }


# =============================================================================
# Global Error Handler Instance
# =============================================================================

# Global error reporter instance
error_reporter = ErrorReporter()


def handle_exception(func: Callable) -> Callable:
    """Decorator to handle exceptions and report them"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OJDownloaderError as e:
            error_reporter.report_error(e.error_info)
            raise
        except Exception as e:
            error_info = ErrorInfo(
                message=f"Unexpected error in {func.__name__}: {str(e)}",
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.MEDIUM,
                original_exception=e,
                traceback_str=traceback.format_exc()
            )
            error_reporter.report_error(error_info)
            raise OJDownloaderError(f"Unexpected error: {str(e)}", error_info)
    
    return wrapper