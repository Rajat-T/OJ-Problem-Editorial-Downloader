# Contributing to OJ Problem Editorial Downloader

Thank you for your interest in contributing to the OJ Problem Editorial Downloader project! This document provides guidelines and information for contributors to help maintain code quality and project consistency.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation Standards](#documentation-standards)
- [Submitting Contributions](#submitting-contributions)
- [Adding New Platforms](#adding-new-platforms)
- [Reporting Issues](#reporting-issues)
- [Community and Support](#community-and-support)

## 🤝 Code of Conduct

### Our Pledge

We are committed to making participation in this project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Standards

Examples of behavior that contributes to creating a positive environment include:

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

### Enforcement

Project maintainers are responsible for clarifying standards of acceptable behavior and are expected to take appropriate and fair corrective action in response to any instances of unacceptable behavior.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git for version control
- Google Chrome browser
- Basic understanding of web scraping concepts
- Familiarity with Python package structure

### First-Time Contributors

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/OJ-Problem-Editorial-Downloader.git
   cd OJ-Problem-Editorial-Downloader
   ```
3. **Add the upstream repository**:
   ```bash
   git remote add upstream https://github.com/original-owner/OJ-Problem-Editorial-Downloader.git
   ```

## 🛠️ Development Setup

### Environment Setup

1. **Create a virtual environment**:
   ```bash
   python -m venv dev_env
   source dev_env/bin/activate  # On Windows: dev_env\Scripts\activate
   ```

2. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   # or
   pip install -r requirements.txt
   pip install pytest pytest-cov flake8 black mypy isort
   ```

3. **Install pre-commit hooks** (recommended):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Project Structure Overview

```
OJ-Problem-Editorial-Downloader/
├── main.py                     # Application entry point
├── setup.py                    # Package installation script
├── requirements.txt            # Project dependencies
├── CONTRIBUTING.md            # This file
├── scraper/                   # Web scraping modules
│   ├── __init__.py
│   ├── base_scraper.py        # Abstract base class
│   ├── atcoder_scraper.py     # AtCoder implementation
│   ├── codeforces_scraper.py  # Codeforces implementation
│   └── spoj_scraper.py        # SPOJ implementation
├── pdf_generator/             # PDF generation
│   ├── __init__.py
│   └── pdf_creator.py
├── ui/                        # User interface
│   ├── __init__.py
│   └── main_window.py
├── utils/                     # Utility functions
│   ├── __init__.py
│   ├── url_parser.py
│   ├── url_validator.py
│   ├── file_manager.py
│   └── error_handler.py
└── tests/                     # Test modules
    ├── test_scrapers.py
    ├── test_pdf_generator.py
    └── test_ui.py
```

## 📝 Contributing Guidelines

### Types of Contributions

We welcome several types of contributions:

1. **🐛 Bug Reports**: Help us identify and fix issues
2. **💡 Feature Requests**: Suggest new functionality
3. **🔧 Bug Fixes**: Fix identified issues
4. **✨ New Features**: Implement new functionality
5. **📚 Documentation**: Improve or add documentation
6. **🧪 Tests**: Add or improve test coverage
7. **🎨 Code Improvements**: Refactoring and optimization

### Contribution Workflow

1. **Check existing issues** to avoid duplicating work
2. **Create an issue** for new features or bugs (if one doesn't exist)
3. **Fork and clone** the repository
4. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b bugfix/issue-number
   ```
5. **Make your changes** following our coding standards
6. **Add tests** for new functionality
7. **Update documentation** as needed
8. **Run tests and linting**:
   ```bash
   python -m pytest tests/
   flake8 .
   black --check .
   ```
9. **Commit your changes** with clear messages
10. **Push to your fork** and **create a pull request**

## 🎯 Code Standards

### Python Style Guide

We follow **PEP 8** with some project-specific guidelines:

#### Formatting
- Use **Black** for code formatting (line length: 88 characters)
- Use **isort** for import sorting
- Use **flake8** for linting

#### Naming Conventions
```python
# Classes: PascalCase
class AtCoderScraper:
    pass

# Functions and variables: snake_case
def extract_problem_info():
    problem_data = {}

# Constants: UPPER_SNAKE_CASE
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# Private methods: leading underscore
def _process_internal_data():
    pass
```

#### Documentation
- Use **docstrings** for all public classes, methods, and functions
- Follow **Google style docstrings**:

```python
def extract_problem_info(self, url: str) -> Dict[str, Any]:
    """
    Extract problem information from the given URL.
    
    Args:
        url (str): The problem URL to extract information from
        
    Returns:
        Dict[str, Any]: Dictionary containing problem information with keys:
            - title: Problem title
            - problem_statement: Main problem description
            - input_format: Input specification
            - output_format: Output specification
            - constraints: Problem constraints
            - examples: List of example inputs/outputs
            - time_limit: Time limit string
            - memory_limit: Memory limit string
            - images: List of image URLs
            
    Raises:
        URLValidationError: If the URL is invalid or unsupported
        NetworkError: If there are network connectivity issues
        ScrapingError: If the content cannot be extracted
        
    Example:
        >>> scraper = AtCoderScraper()
        >>> data = scraper.extract_problem_info("https://atcoder.jp/contests/abc123/tasks/abc123_a")
        >>> print(data['title'])
        "A. Problem Title"
    """
```

### Error Handling Standards

Follow the comprehensive error handling requirements:

```python
# Use specific exception types
from utils.error_handler import NetworkError, URLValidationError

def fetch_data(url: str) -> str:
    """Fetch data with proper error handling."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        raise NetworkError(f"Timeout while fetching {url}")
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error: {e}")
```

### CLI Interface Standards

All CLI options must follow the standard interface:

```python
# Required CLI arguments
parser.add_argument('--help', '-h', help='Display help information')
parser.add_argument('--version', '-v', help='Show program version')
parser.add_argument('--url', '-u', help='Process a single URL')
parser.add_argument('--batch', '-b', help='Process URLs from file')
parser.add_argument('--output', '-o', help='Specify output directory')
parser.add_argument('--log-level', help='Set logging level')
parser.add_argument('--config', '-c', help='Path to configuration file')
parser.add_argument('--headless', action='store_true', help='Run in headless mode')
parser.add_argument('--no-gui', action='store_true', help='Disable GUI mode')
```

## 🧪 Testing Requirements

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=./ --cov-report=html

# Run specific test file
python -m pytest tests/test_scrapers.py

# Run with verbose output
python -m pytest tests/ -v
```

### Writing Tests

1. **Test file naming**: `test_*.py`
2. **Test function naming**: `test_*`
3. **Use descriptive test names**:
   ```python
   def test_atcoder_scraper_extracts_problem_title_correctly():
       pass
   
   def test_url_validation_rejects_invalid_platform():
       pass
   ```

4. **Follow AAA pattern** (Arrange, Act, Assert):
   ```python
   def test_pdf_generation_creates_valid_file():
       # Arrange
       problem_data = {"title": "Test Problem", "content": "Sample content"}
       pdf_creator = PDFCreator()
       
       # Act
       pdf_path = pdf_creator.create_problem_pdf(problem_data)
       
       # Assert
       assert pdf_path.exists()
       assert pdf_path.suffix == '.pdf'
   ```

### Test Coverage Requirements

- Maintain **minimum 80%** test coverage
- All new features must include tests
- Bug fixes should include regression tests
- Critical components require **90%+ coverage**

## 📚 Documentation Standards

### Code Documentation

1. **Docstrings**: All public APIs must have comprehensive docstrings
2. **Type hints**: Use type hints for all function parameters and return values
3. **Comments**: Use inline comments for complex logic

### README Updates

When adding new features:
1. Update the features list
2. Add usage examples
3. Update installation instructions if needed
4. Add troubleshooting information for common issues

### API Documentation

Document all public APIs with:
- Purpose and functionality
- Parameters and return values
- Usage examples
- Error conditions
- Performance considerations

## 🔄 Submitting Contributions

### Pull Request Guidelines

1. **Create descriptive PR titles**:
   - ✅ "Add support for CodeChef platform scraping"
   - ✅ "Fix PDF generation memory leak issue #123"
   - ❌ "Update code"
   - ❌ "Fixes"

2. **Write comprehensive PR descriptions**:
   ```markdown
   ## Description
   Brief description of changes
   
   ## Changes Made
   - Added new scraper for Platform X
   - Updated URL validation logic
   - Fixed memory leak in PDF generator
   
   ## Testing
   - [ ] All existing tests pass
   - [ ] New tests added for new functionality
   - [ ] Manual testing completed
   
   ## Documentation
   - [ ] README updated
   - [ ] Docstrings added/updated
   - [ ] Example URLs added
   
   Fixes #123
   ```

3. **Keep PRs focused**: One feature or fix per PR
4. **Update CHANGELOG.md** for significant changes
5. **Ensure all CI checks pass**

### Review Process

1. **Automated checks** must pass (tests, linting, formatting)
2. **Code review** by maintainers
3. **Testing** on different platforms if applicable
4. **Documentation review** for clarity and completeness
5. **Final approval** and merge

## 🌐 Adding New Platforms

To add support for a new competitive programming platform:

### 1. Create Scraper Class

```python
# scraper/new_platform_scraper.py
from .base_scraper import BaseScraper
from typing import Dict, Any, Optional

class NewPlatformScraper(BaseScraper):
    """Scraper for NewPlatform online judge."""
    
    def __init__(self):
        super().__init__()
        self.platform_name = "NewPlatform"
        self.base_url = "https://newplatform.com"
    
    def is_valid_url(self, url: str) -> bool:
        """Check if URL belongs to NewPlatform."""
        # Implementation here
        
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """Extract problem statement from URL."""
        # Implementation here
        
    def get_editorial(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract editorial from URL."""
        # Implementation here
```

### 2. Update URL Parser

```python
# utils/url_parser.py
URL_PATTERNS = {
    # ... existing patterns ...
    'newplatform': [
        r'https?://(?:www\.)?newplatform\.com/problem/(\w+)',
        r'https?://(?:www\.)?newplatform\.com/contest/(\w+)/problem/(\w+)',
    ]
}
```

### 3. Add Tests

```python
# tests/test_scrapers.py
class TestNewPlatformScraper:
    def test_validates_correct_urls(self):
        # Test URL validation
        
    def test_extracts_problem_data(self):
        # Test problem extraction
        
    def test_handles_missing_editorial(self):
        # Test graceful handling of missing editorials
```

### 4. Update Documentation

- Add platform to supported list in README
- Include example URLs
- Update troubleshooting guide if needed
- Add platform-specific configuration options

### 5. Platform-Specific Requirements

Each platform scraper must:
- Handle rate limiting appropriately
- Respect robots.txt
- Provide meaningful error messages
- Support both HTTP and HTTPS
- Handle different URL formats
- Extract images properly for PDF generation

## 🐛 Reporting Issues

### Bug Reports

When reporting bugs, include:

1. **Clear title** describing the issue
2. **Environment information**:
   ```
   - OS: [e.g., macOS 12.0, Windows 11, Ubuntu 20.04]
   - Python version: [e.g., 3.9.7]
   - Package version: [e.g., 1.0.0]
   - Browser: [e.g., Chrome 98.0]
   ```
3. **Steps to reproduce**:
   ```
   1. Launch the application
   2. Enter URL: https://example.com/problem/123
   3. Click "Download"
   4. Error occurs
   ```
4. **Expected vs actual behavior**
5. **Error messages or logs** (use `--log-level DEBUG`)
6. **Screenshots** if applicable (for GUI issues)

### Feature Requests

For feature requests, describe:
1. **Use case**: Why is this feature needed?
2. **Proposed solution**: How should it work?
3. **Alternatives considered**: Other approaches you've thought of
4. **Implementation ideas**: If you have technical suggestions

## 💬 Community and Support

### Getting Help

1. **Check the documentation** first (README, this guide)
2. **Search existing issues** for similar problems
3. **Ask questions** in issue discussions
4. **Join community discussions** on the project page

### Communication Guidelines

- Be respectful and constructive
- Provide clear, detailed information
- Use appropriate labels for issues
- Follow up on your contributions
- Help others when possible

### Maintainer Response

- **Bug reports**: We aim to respond within 48 hours
- **Feature requests**: Initial response within 1 week
- **Pull requests**: Review within 1 week for small changes, longer for major features

## 🎖️ Recognition

We value all contributions! Contributors will be:
- **Listed in CONTRIBUTORS.md**
- **Mentioned in release notes** for significant contributions
- **Invited as collaborators** for consistent, high-quality contributions

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

Thank you for contributing to the OJ Problem Editorial Downloader project! Your contributions help make competitive programming resources more accessible to everyone. 🚀