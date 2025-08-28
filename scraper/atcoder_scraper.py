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
                        # Process HTML content to clean text
                        result['problem_statement'] = self._process_atcoder_content(lang_div)
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
    
    def _process_atcoder_content(self, content_elem) -> str:
        """
        Process AtCoder HTML content and convert to clean text while preserving structure.
        
        Args:
            content_elem: BeautifulSoup element containing the content
            
        Returns:
            str: Cleaned and formatted text content
        """
        try:
            if not content_elem:
                return ""
            
            # Create a copy to avoid modifying the original
            from bs4 import BeautifulSoup
            content_copy = BeautifulSoup(str(content_elem), 'html.parser')
            
            # Remove script and style tags
            for tag in content_copy.find_all(['script', 'style']):
                tag.decompose()
            
            # Process different HTML elements appropriately
            self._process_html_elements(content_copy)
            
            # Get the text content with proper spacing
            text_content = content_copy.get_text(separator='\n', strip=True)
            
            # Apply text processing and cleaning
            cleaned_text = self.clean_and_format_text(text_content)
            
            return cleaned_text
            
        except Exception as e:
            logger.error(f"Error processing AtCoder content: {e}")
            # Fallback to simple text extraction
            return content_elem.get_text(separator='\n', strip=True) if content_elem else ""
    
    def _process_html_elements(self, soup) -> None:
        """
        Process HTML elements to improve text extraction.
        
        Args:
            soup: BeautifulSoup object to process
        """
        try:
            # Handle <var> tags - convert to variable formatting
            for var_tag in soup.find_all('var'):
                var_text = var_tag.get_text(strip=True)
                if var_text:
                    var_tag.replace_with(f"{var_text}")
            
            # Handle <pre> tags - preserve formatting but clean content
            for pre_tag in soup.find_all('pre'):
                pre_text = pre_tag.get_text(strip=False)  # Preserve internal spacing
                if pre_text:
                    # Clean up the text but preserve structure
                    lines = pre_text.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        # Remove excessive whitespace but preserve indentation
                        cleaned_line = re.sub(r'[ \t]+', ' ', line.rstrip())
                        cleaned_lines.append(cleaned_line)
                    
                    # Join with double newlines for better separation
                    cleaned_pre = '\n'.join(cleaned_lines)
                    pre_tag.replace_with(f"\n\n{cleaned_pre}\n\n")
            
            # Handle headings - add emphasis
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                heading_text = heading.get_text(strip=True)
                if heading_text:
                    heading.replace_with(f"\n\n=== {heading_text} ===\n")
            
            # Handle paragraphs - ensure proper spacing
            for p_tag in soup.find_all('p'):
                p_text = p_tag.get_text(strip=True)
                if p_text:
                    p_tag.replace_with(f"\n{p_text}\n")
            
            # Handle list items
            for li_tag in soup.find_all('li'):
                li_text = li_tag.get_text(strip=True)
                if li_text:
                    li_tag.replace_with(f"\n• {li_text}")
            
            # Handle line breaks
            for br_tag in soup.find_all('br'):
                br_tag.replace_with('\n')
            
            # Handle emphasis tags
            for em_tag in soup.find_all(['em', 'i']):
                em_text = em_tag.get_text(strip=True)
                if em_text:
                    em_tag.replace_with(f"*{em_text}*")
            
            for strong_tag in soup.find_all(['strong', 'b']):
                strong_text = strong_tag.get_text(strip=True)
                if strong_text:
                    strong_tag.replace_with(f"**{strong_text}**")
            
            # Handle code tags
            for code_tag in soup.find_all('code'):
                code_text = code_tag.get_text(strip=True)
                if code_text:
                    code_tag.replace_with(f"`{code_text}`")
                    
        except Exception as e:
            logger.warning(f"Error processing HTML elements: {e}")
    
    def _extract_problem_sections(self, content_div, url: str) -> Dict[str, Any]:
        """
        Extract problem sections from AtCoder problem content
        
        Args:
            content_div: BeautifulSoup element containing problem content
            url (str): URL for context in error messages
            
        Returns:
            Dict[str, Any]: Dictionary with extracted problem sections
        """
        result = {
            'problem_statement': '',
            'input_format': '',
            'output_format': '',
            'constraints': '',
            'examples': []
        }
        
        try:
            if not content_div:
                logger.warning(f"No content div provided for {url}")
                return result
                
            # Remove script and style tags
            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()
            
            # Find section headers and extract content
            sections = content_div.find_all(['h3', 'h4', 'section'])
            
            current_section = None
            section_content = []
            
            for element in content_div.find_all(['h3', 'h4', 'p', 'div', 'pre', 'section', 'ul', 'ol']):
                # Check if this is a section header
                if element.name in ['h3', 'h4', 'section']:
                    # Save previous section if any
                    if current_section and section_content:
                        self._process_section(current_section, section_content, result)
                    
                    # Start new section
                    section_text = element.get_text(strip=True).lower()
                    current_section = self._identify_section_type(section_text)
                    section_content = []
                else:
                    # Add content to current section
                    if element.get_text(strip=True):
                        section_content.append(element)
            
            # Process the last section
            if current_section and section_content:
                self._process_section(current_section, section_content, result)
            
            # If no sections found, try to extract examples directly
            if not result['examples']:
                result['examples'] = self._extract_examples_fallback(content_div)
            
            # If no problem statement found, use the main content
            if not result['problem_statement']:
                # Remove sample inputs/outputs and headers
                main_content = content_div.get_text(separator='\n', strip=True)
                # Clean up the content
                lines = main_content.split('\n')
                filtered_lines = []
                skip_next = False
                
                for line in lines:
                    line_lower = line.lower().strip()
                    if skip_next:
                        skip_next = False
                        continue
                    if any(keyword in line_lower for keyword in ['sample input', 'sample output', 'input format', 'output format', 'constraints']):
                        skip_next = True
                        continue
                    if line.strip():
                        filtered_lines.append(line)
                
                result['problem_statement'] = '\n'.join(filtered_lines[:20])  # Limit to first 20 lines
            
            # Clean all text content
            for key in ['problem_statement', 'input_format', 'output_format', 'constraints']:
                if result[key]:
                    result[key] = self.clean_and_format_text(result[key])
            
            logger.debug(f"Extracted sections for {url}: {list(result.keys())}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting problem sections from {url}: {e}")
            return result
    
    def _identify_section_type(self, section_text: str) -> str:
        """
        Identify the type of section based on header text
        
        Args:
            section_text (str): Section header text
            
        Returns:
            str: Section type identifier
        """
        section_text = section_text.lower().strip()
        
        if 'problem' in section_text or 'statement' in section_text:
            return 'problem_statement'
        elif 'input' in section_text:
            return 'input_format'
        elif 'output' in section_text:
            return 'output_format'
        elif 'constraint' in section_text or 'limit' in section_text:
            return 'constraints'
        elif 'sample' in section_text or 'example' in section_text:
            return 'examples'
        else:
            return 'problem_statement'  # Default to problem statement
    
    def _process_section(self, section_type: str, elements: List, result: Dict[str, Any]) -> None:
        """
        Process a section and add content to result
        
        Args:
            section_type (str): Type of section
            elements (List): List of BeautifulSoup elements
            result (Dict[str, Any]): Result dictionary to update
        """
        try:
            if section_type == 'examples':
                # Extract examples
                examples = self._extract_examples_from_elements(elements)
                result['examples'].extend(examples)
            else:
                # Extract text content, preserving bullet lists
                content_parts = []
                for element in elements:
                    if element.name in ['ul', 'ol']:
                        for li in element.find_all('li'):
                            item = li.get_text(separator=' ', strip=True)
                            if item:
                                content_parts.append(f"• {item}")
                    else:
                        text = element.get_text(separator='\n', strip=True)
                        if text:
                            content_parts.append(text)
                
                content = '\n'.join(content_parts)
                if content:
                    if result[section_type]:
                        result[section_type] += '\n\n' + content
                    else:
                        result[section_type] = content
                        
        except Exception as e:
            logger.warning(f"Error processing section {section_type}: {e}")
    
    def _extract_examples_from_elements(self, elements: List) -> List[Dict[str, str]]:
        """
        Extract examples from a list of elements
        
        Args:
            elements (List): List of BeautifulSoup elements
            
        Returns:
            List[Dict[str, str]]: List of example dictionaries
        """
        examples = []
        
        try:
            current_input = None
            current_output = None
            
            for element in elements:
                text = element.get_text(strip=True)
                if not text:
                    continue
                    
                # Check if this is input or output
                if 'input' in text.lower():
                    if current_input and current_output:
                        examples.append({
                            'input': current_input,
                            'output': current_output
                        })
                        current_output = None
                    current_input = text
                elif 'output' in text.lower():
                    current_output = text
                elif element.name == 'pre':
                    # This is likely sample data
                    if current_input and not current_output:
                        current_output = text
                    elif not current_input:
                        current_input = text
            
            # Add the last example if we have both input and output
            if current_input and current_output:
                examples.append({
                    'input': current_input,
                    'output': current_output
                })
            
        except Exception as e:
            logger.warning(f"Error extracting examples from elements: {e}")
            
        return examples
    
    def _extract_examples_fallback(self, content_div) -> List[Dict[str, str]]:
        """
        Fallback method to extract examples when standard parsing fails
        
        Args:
            content_div: BeautifulSoup element containing problem content
            
        Returns:
            List[Dict[str, str]]: List of example dictionaries
        """
        examples = []
        
        try:
            # Look for pre tags that might contain examples
            pre_tags = content_div.find_all('pre')
            
            for i in range(0, len(pre_tags), 2):
                if i + 1 < len(pre_tags):
                    input_text = pre_tags[i].get_text(strip=True)
                    output_text = pre_tags[i + 1].get_text(strip=True)
                    
                    if input_text and output_text:
                        examples.append({
                            'input': input_text,
                            'output': output_text
                        })
            
            # If no pre tags, look for divs with sample content
            if not examples:
                sample_divs = content_div.find_all('div', string=re.compile(r'sample|example', re.IGNORECASE))
                for div in sample_divs[:4]:  # Limit to first 4 examples
                    text = div.get_text(strip=True)
                    if text:
                        examples.append({
                            'input': text,
                            'output': 'See problem statement'
                        })
            
        except Exception as e:
            logger.warning(f"Error in fallback example extraction: {e}")
            
        return examples
    
    def download_problem_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download an AtCoder problem page directly as a PDF with LLM optimization.
        
        This method downloads the webpage and converts it directly to PDF format,
        preserving the original layout and styling while optimizing for LLM training.
        
        Args:
            url (str): AtCoder problem URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            ValueError: If URL is not a valid AtCoder problem URL
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid AtCoder problem URL: {url}")
        
        # Extract problem identifier for title
        try:
            match = re.match(self.PROBLEM_PATTERN, url)
            if match:
                contest_id, task_id = match.groups()
                title = f"AtCoder {contest_id.upper()} Problem {task_id.upper()}"
            else:
                title = "AtCoder Problem"
        except:
            title = "AtCoder Problem"
        
        # AtCoder-specific CSS for better PDF rendering with LLM optimization
        atcoder_css = """
        /* AtCoder-specific PDF optimizations */
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
        #task-statement, .problem-statement {
            background: #f8f9fa;
            padding: 1.5em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
            page-break-inside: avoid;
        }
        
        #task-statement::before,
        .problem-statement::before {
            content: "[PROBLEM_STATEMENT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 1em;
            font-weight: bold;
        }
        
        #task-statement h1,
        #task-statement h2,
        #task-statement h3,
        .problem-statement h1,
        .problem-statement h2,
        .problem-statement h3 {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        #task-statement h1::before,
        #task-statement h2::before,
        #task-statement h3::before,
        .problem-statement h1::before,
        .problem-statement h2::before,
        .problem-statement h3::before {
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
        
        /* Language-specific content */
        .lang-en, .lang-ja {
            display: block !important;
        }
        
        /* Part sections */
        .part {
            margin: 1em 0;
            padding: 0.8em;
            background: #f8f9fa;
            border-left: 4px solid #007bff;
        }
        
        .part::before {
            content: "[SECTION]";
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
            css_styles=atcoder_css
        )
    
    def download_editorial_as_pdf(self, url: str, output_path: str, use_selenium: bool = False) -> bool:
        """
        Download an AtCoder editorial page directly as a PDF with LLM optimization.
        
        Args:
            url (str): AtCoder editorial URL
            output_path (str): Path where the PDF should be saved
            use_selenium (bool): Whether to use Selenium for JavaScript rendering
            
        Returns:
            bool: True if PDF was successfully created, False otherwise
            
        Raises:
            ValueError: If URL is not a valid AtCoder editorial URL
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid AtCoder editorial URL: {url}")
        
        # Extract editorial identifier for title
        try:
            match = re.match(self.EDITORIAL_PATTERN, url)
            if match:
                contest_id = match.group(1)
                title = f"AtCoder {contest_id.upper()} Editorial"
            else:
                title = "AtCoder Editorial"
        except:
            title = "AtCoder Editorial"
        
        # AtCoder editorial-specific CSS with LLM optimization
        editorial_css = """
        /* AtCoder editorial-specific PDF optimizations */
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
        #main-container, #editorial {
            background: #f8f9fa;
            padding: 1.5em;
            margin: 1em 0;
            border-left: 4px solid #007bff;
            page-break-inside: avoid;
        }
        
        #main-container::before,
        #editorial::before {
            content: "[EDITORIAL_CONTENT]";
            display: block;
            font-size: 0.8em;
            color: #666;
            margin-bottom: 1em;
            font-weight: bold;
        }
        
        #main-container h1,
        #main-container h2,
        #main-container h3,
        #editorial h1,
        #editorial h2,
        #editorial h3 {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        
        #main-container h1::before,
        #main-container h2::before,
        #main-container h3::before,
        #editorial h1::before,
        #editorial h2::before,
        #editorial h3::before {
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