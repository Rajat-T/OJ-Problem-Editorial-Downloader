# OJ Problem Editorial Downloader

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey.svg)](https://github.com/your-repo/OJ-Problem-Editorial-Downloader)

A comprehensive Python application for downloading and generating PDF documents from Online Judge (OJ) problem statements and editorials. Supports multiple competitive programming platforms with a user-friendly interface and robust error handling.

## 🚀 Features

- **🌐 Multi-Platform Support**: AtCoder, Codeforces, and SPOJ
- **📄 Flexible Download Options**: Problem statements, editorials, or combined documents
- **🎨 PDF Generation**: Clean, formatted PDF documents with professional styling
- **🖥️ User-Friendly Interface**: Both GUI and command-line modes
- **🔄 Robust Scraping**: Uses both requests and Selenium for reliable data extraction
- **🖼️ Image Support**: Downloads and embeds images in PDF documents
- **✅ URL Validation**: Automatic platform detection and URL validation
- **🛡️ Error Handling**: Comprehensive error handling with retry mechanisms
- **📊 Batch Processing**: Process multiple URLs from file
- **⚙️ Configurable**: Extensive configuration options and preferences
- **📝 Logging**: Detailed logging with multiple levels and file output
- **🔧 CLI Interface**: Full command-line support for automation

## Project Structure

```
OJ-Problem-Editorial-Downloader/
├── main.py                     # Entry point
├── requirements.txt            # Dependencies
├── README.md                   # This file
├── scraper/                    # Scraping logic
│   ├── __init__.py
│   ├── base_scraper.py         # Abstract base class
│   ├── atcoder_scraper.py      # AtCoder implementation
│   ├── codeforces_scraper.py   # Codeforces implementation
│   └── spoj_scraper.py         # SPOJ implementation
├── pdf_generator/              # PDF generation
│   ├── __init__.py
│   └── pdf_creator.py          # PDF creation logic
├── ui/                         # User interface
│   ├── __init__.py
│   └── main_window.py          # Main GUI window
└── utils/                      # Utility functions
    ├── __init__.py
    ├── url_parser.py           # URL parsing utilities
    └── file_manager.py         # File management utilities
```

## 📦 Installation

### Prerequisites

- **Python 3.8 or higher** ([Download here](https://www.python.org/downloads/))
- **Google Chrome browser** (for Selenium WebDriver - automatically managed)
- **Git** (optional, for cloning the repository)

### Method 1: Using setup.py (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/OJ-Problem-Editorial-Downloader.git
   cd OJ-Problem-Editorial-Downloader
   ```

2. **Install the package**:
   ```bash
   pip install -e .
   ```

3. **Run the application**:
   ```bash
   oj-downloader
   # or
   python -m oj_downloader
   ```

### Method 2: Manual Installation

1. **Download and extract** the project or clone it:
   ```bash
   git clone https://github.com/your-username/OJ-Problem-Editorial-Downloader.git
   cd OJ-Problem-Editorial-Downloader
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```

### Method 3: Using Virtual Environment (Recommended for Development)

1. **Create and activate virtual environment**:
   ```bash
   python -m venv oj_downloader_env
   
   # On Windows
   oj_downloader_env\Scripts\activate
   
   # On macOS/Linux
   source oj_downloader_env/bin/activate
   ```

2. **Clone and install**:
   ```bash
   git clone https://github.com/your-username/OJ-Problem-Editorial-Downloader.git
   cd OJ-Problem-Editorial-Downloader
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```

## Dependencies

The application uses the following Python packages:

- **requests**: HTTP requests for web scraping
- **beautifulsoup4**: HTML parsing
- **selenium**: Browser automation for dynamic content
- **reportlab**: PDF generation
- **webdriver-manager**: Automatic Chrome driver management
- **lxml**: XML/HTML processing
- **Pillow**: Image processing
- **tkinter**: GUI framework (included with Python)

## 📚 Usage

### 🖼️ GUI Mode (Default)

1. **Launch the application**:
   ```bash
   python main.py
   # or if installed via setup.py
   oj-downloader
   ```

2. **Using the Interface**:
   - **Enter URL**: Paste the problem or editorial URL in the input field
   - **Validate URL**: Click "Validate URL" to check if the URL is supported
   - **Select Options**:
     - Choose download type (Problem Only, Editorial Only, or Both)
     - Enable/disable headless browser mode
     - Set custom output directory
   - **Download**: Click "Download & Generate PDF" to start the process
   - **Monitor Progress**: View real-time logs and progress updates

### 🔧 Command Line Interface

The application supports comprehensive CLI options following standard conventions:

#### Basic Usage Examples

```bash
# Start GUI (default behavior)
python main.py

# Process a single URL
python main.py --url "https://atcoder.jp/contests/abc123/tasks/abc123_a"

# Process multiple URLs from a file
python main.py --batch urls.txt

# Show help information
python main.py --help

# Check version
python main.py --version
```

#### Advanced CLI Options

```bash
# Custom output directory
python main.py --url "URL" --output ./custom_pdfs

# Set logging level for debugging
python main.py --log-level DEBUG --batch urls.txt

# Run in headless mode (no browser UI)
python main.py --headless --batch urls.txt

# Command-line only mode (no GUI)
python main.py --no-gui --batch urls.txt

# Use custom configuration file
python main.py --config ./my_config.ini

# Combine multiple options
python main.py --batch urls.txt --output ./pdfs --log-level INFO --headless
```

#### CLI Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `--help` | `-h` | Display help information |
| `--version` | `-v` | Show program version number |
| `--url` | `-u` | Process a single URL |
| `--batch` | `-b` | Process URLs from a file (one URL per line) |
| `--output` | `-o` | Specify output directory for generated files |
| `--config` | `-c` | Path to custom configuration file |
| `--log-level` | | Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `--headless` | | Run browser in headless mode |
| `--no-gui` | | Disable GUI mode (requires --batch or --url) |

#### Batch Processing File Format

Create a text file with one URL per line:

```text
# example_urls.txt
https://atcoder.jp/contests/abc123/tasks/abc123_a
https://codeforces.com/contest/1234/problem/A
https://www.spoj.com/problems/PRIME1/
# Lines starting with # are treated as comments
https://atcoder.jp/contests/abc124/tasks/abc124_b
```

### Supported URL Formats

#### AtCoder
- **Problem**: `https://atcoder.jp/contests/abc123/tasks/abc123_a`
- **Editorial**: `https://atcoder.jp/contests/abc123/editorial`

#### Codeforces
- **Problem**: `https://codeforces.com/contest/1234/problem/A`
- **Problem (Problemset)**: `https://codeforces.com/problemset/problem/1234/A`
- **Editorial (Blog)**: `https://codeforces.com/blog/entry/12345`

#### SPOJ
- **Problem**: `https://www.spoj.com/problems/PRIME1/`

### Command Line Usage

The main.py entry point provides a comprehensive command-line interface with advanced features:

#### Basic Usage
```bash
# Start GUI (default)
python main.py

# Process single URL
python main.py --url "https://atcoder.jp/contests/abc123/tasks/abc123_a"

# Batch process from file
python main.py --batch urls.txt

# Display help
python main.py --help
```

#### Advanced Command Line Options
```bash
# Custom output directory
python main.py --url "URL" --output ./custom_pdfs

# Set logging level
python main.py --log-level DEBUG --batch urls.txt

# Headless mode (no browser UI)
python main.py --headless --batch urls.txt

# No-GUI mode (command line only)
python main.py --no-gui --batch urls.txt

# Custom configuration file
python main.py --config ./my_config.ini

# Check version
python main.py --version
```

#### Batch File Format
Create a text file with one URL per line:
```
https://atcoder.jp/contests/abc123/tasks/abc123_a
https://codeforces.com/contest/1234/problem/A
https://www.spoj.com/problems/PRIME1/
```

#### Application Features
- **Graceful Shutdown**: Handles Ctrl+C and cleanup automatically
- **Error Recovery**: Automatic retry and backup creation
- **Concurrent Processing**: Configurable parallel downloads
- **Persistent Settings**: Saves preferences across sessions
- **Comprehensive Logging**: File and console output with rotation
- **Configuration Management**: INI files and JSON settings

### Command Line Usage

You can also use the components programmatically:

```python
from scraper.atcoder_scraper import AtCoderScraper
from pdf_generator.pdf_creator import PDFCreator

# Initialize scraper and PDF creator
scraper = AtCoderScraper()
pdf_creator = PDFCreator()

# Extract problem data
problem_data = scraper.extract_problem_info("https://atcoder.jp/contests/abc123/tasks/abc123_a")

# Generate PDF
pdf_path = pdf_creator.create_problem_pdf(problem_data)
print(f"PDF generated: {pdf_path}")
```

## Platform-Specific Features

### AtCoder
- Problem statements with constraints and sample test cases
- Editorial extraction from contest editorial pages
- Automatic editorial URL generation from problem URLs
- Support for mathematical expressions and images

### Codeforces
- Problem statements with time/memory limits
- Input/output specifications
- Sample test cases with expected outputs
- Editorial extraction from blog posts
- Support for contest-wide editorials

### SPOJ
- Problem statements and basic information
- Limited editorial support (SPOJ typically doesn't have official editorials)
- Problem statistics when available

## Configuration

### Browser Settings

The application uses Chrome WebDriver with the following default settings:
- Headless mode (can be disabled in GUI)
- No sandbox mode for compatibility
- Automatic driver management

### Output Settings

- **Default Output Directory**: `./output/`
- **Image Cache**: `./output/images/`
- **PDF Format**: A4 page size with professional styling
- **File Naming**: Includes platform, title, and timestamp

## Error Handling

The application includes comprehensive error handling:

- **Network Issues**: Retry logic and timeout handling
- **Invalid URLs**: Validation before processing
- **Missing Content**: Graceful handling of missing elements
- **PDF Generation**: Error recovery and fallback options
- **Browser Issues**: Automatic WebDriver management

## Logging

All operations are logged with different levels:
- **INFO**: General operation progress
- **WARNING**: Non-fatal issues
- **ERROR**: Operation failures

Logs are displayed in the GUI and can be cleared as needed.

## 📈 Troubleshooting Guide

### Common Issues and Solutions

#### 1. 🚫 Chrome Driver Issues

**Problem**: WebDriver not found or Chrome browser issues

**Solutions**:
- Ensure Google Chrome is installed and updated to the latest version
- The application automatically manages ChromeDriver via `webdriver-manager`
- If issues persist, try:
  ```bash
  pip uninstall webdriver-manager
  pip install webdriver-manager
  ```
- Clear the WebDriver cache:
  ```bash
  # On Windows
  del /s /q %USERPROFILE%\.wdm
  
  # On macOS/Linux
  rm -rf ~/.wdm
  ```

#### 2. 🌐 Network and Timeout Issues

**Problem**: Request timeouts or connection failures

**Solutions**:
- Check your internet connection
- Some platforms may have rate limiting - try again after a few minutes
- Increase timeout in configuration:
  ```ini
  # config.ini
  [network]
  timeout = 60
  rate_limit = 2.0
  ```
- Use VPN if certain platforms are blocked in your region

#### 3. 📄 PDF Generation Issues

**Problem**: PDF creation fails or produces empty files

**Solutions**:
- Ensure sufficient disk space is available
- Check output directory permissions:
  ```bash
  # Create output directory with proper permissions
  mkdir -p ./output
  chmod 755 ./output
  ```
- Verify that all dependencies are installed:
  ```bash
  pip install --upgrade reportlab Pillow
  ```

#### 4. 🔒 Missing Content or 404 Errors

**Problem**: No content extracted or "page not found" errors

**Solutions**:
- Verify the URL is correct and accessible in your browser
- Some editorials may not be publicly available
- SPOJ has limited editorial support
- Check if the contest is still private or requires login
- Try different URL formats:
  ```
  # AtCoder examples
  https://atcoder.jp/contests/abc123/tasks/abc123_a
  https://atcoder.jp/contests/abc123/editorial
  
  # Codeforces examples
  https://codeforces.com/contest/1234/problem/A
  https://codeforces.com/problemset/problem/1234/A
  ```

#### 5. 🖥️ GUI Issues

**Problem**: GUI doesn't start or appears broken

**Solutions**:
- Ensure tkinter is installed (usually comes with Python):
  ```bash
  # On Ubuntu/Debian
  sudo apt-get install python3-tk
  
  # On macOS (if using Homebrew Python)
  brew install python-tk
  ```
- Try running in command-line mode:
  ```bash
  python main.py --no-gui --url "your-url-here"
  ```
- Update your Python installation if using an older version

#### 6. 💾 Installation and Dependency Issues

**Problem**: Import errors or missing modules

**Solutions**:
- Reinstall dependencies:
  ```bash
  pip uninstall -r requirements.txt -y
  pip install -r requirements.txt
  ```
- Use virtual environment to avoid conflicts:
  ```bash
  python -m venv fresh_env
  source fresh_env/bin/activate  # or fresh_env\Scripts\activate on Windows
  pip install -r requirements.txt
  ```
- Check Python version compatibility:
  ```bash
  python --version  # Should be 3.8 or higher
  ```

#### 7. 📊 Performance Issues

**Problem**: Slow processing or high memory usage

**Solutions**:
- Enable headless mode for faster processing:
  ```bash
  python main.py --headless
  ```
- Close unnecessary browser windows
- Clear cache directories periodically:
  ```bash
  rm -rf ./output/cache/
  rm -rf ./output/images/temp/
  ```
- Reduce concurrent downloads in configuration:
  ```ini
  [processing]
  max_concurrent_downloads = 1
  ```

#### 8. 🔐 Permission and Security Issues

**Problem**: File permission errors or security warnings

**Solutions**:
- Run with appropriate permissions (avoid running as admin/root unless necessary)
- Check output directory permissions:
  ```bash
  ls -la ./output/
  chmod -R 755 ./output/
  ```
- Some antivirus software may flag web scraping tools - add exception if needed
- Ensure you have write permissions in the application directory

### 📞 Getting Help

1. **Check the logs**: Enable DEBUG logging for detailed information:
   ```bash
   python main.py --log-level DEBUG
   ```

2. **Search existing issues**: Check the project's issue tracker for similar problems

3. **Create a new issue**: Include the following information:
   - Operating system and Python version
   - Complete error message or log output
   - URL you were trying to process
   - Steps to reproduce the issue
   - Configuration files (remove sensitive information)

4. **Test with example URLs**: Try with known working URLs from `test_urls.txt`

### 📊 Performance Tips

- Use batch processing for multiple URLs
- Enable headless mode for faster scraping
- Configure appropriate rate limiting to respect servers
- Use SSD storage for better I/O performance
- Close other resource-intensive applications while processing

## 🤝 Contributing

We welcome contributions from the community! Please read our [Contributing Guidelines](CONTRIBUTING.md) for detailed information on how to contribute.

### Quick Start for Contributors

1. **Fork the repository** and clone your fork
2. **Create a virtual environment** and install development dependencies:
   ```bash
   python -m venv dev_env
   source dev_env/bin/activate  # On Windows: dev_env\Scripts\activate
   pip install -e ".[dev]"
   ```
3. **Make your changes** following our coding standards
4. **Run tests** to ensure everything works:
   ```bash
   python -m pytest tests/
   flake8 .
   black --check .
   ```
5. **Submit a pull request** with a clear description of your changes

### Types of Contributions Welcome

- 🐛 **Bug Reports**: Help us identify and fix issues
- ✨ **New Features**: Implement new functionality
- 📚 **Documentation**: Improve or add documentation
- 🧪 **Testing**: Add or improve test coverage
- 🌍 **Platform Support**: Add new competitive programming platforms
- 🎨 **UI/UX Improvements**: Enhance user interface and experience

### Adding New Platforms

To add support for a new competitive programming platform:

1. **Create a new scraper class** inheriting from `BaseScraper`
2. **Implement required methods**: `get_problem_statement()`, `get_editorial()`, `is_valid_url()`
3. **Add URL patterns** to `URLParser`
4. **Update the GUI** to include the new scraper
5. **Add comprehensive tests** for the new platform
6. **Update documentation** with examples and platform-specific notes

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines and examples.

## 📚 Documentation

Comprehensive documentation is available:

- **[User Manual](USER_MANUAL.md)**: Complete guide with examples and tutorials
- **[Contributing Guidelines](CONTRIBUTING.md)**: How to contribute to the project
- **[API Documentation](#)**: Code documentation and API reference
- **[Troubleshooting Guide](#troubleshooting)**: Solutions to common issues

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. The license permits commercial use, including training large language models, by any organization.

### Third-Party Licenses

This project uses several open-source libraries:
- **Selenium**: Apache License 2.0
- **BeautifulSoup4**: MIT License
- **ReportLab**: BSD License
- **Requests**: Apache License 2.0
- **Pillow**: HPND License

## 🔒 Security

### Security Considerations

- The application respects robots.txt and implements rate limiting
- No personal data is collected or transmitted
- All network requests use secure HTTPS when available
- WebDriver runs in sandboxed mode for security

### Reporting Security Issues

If you discover a security vulnerability, please send an email to [security@yourproject.com](mailto:security@yourproject.com) instead of opening a public issue.

## ⚖️ Disclaimer

This tool may be used for educational, research, or commercial purposes, including training large language models. Please:

- **Respect platform terms of service** and usage policies
- **Use reasonable rate limiting** to avoid overloading servers
- **Check robots.txt** and platform policies before scraping
- **Use responsibly** and consider the impact on platform resources

The developers are not responsible for any misuse of this tool or violations of platform terms of service.

## 📞 Support

### Getting Help

1. **Check the documentation**: Start with [README.md](README.md) and [USER_MANUAL.md](USER_MANUAL.md)
2. **Search existing issues**: Look for similar problems in the issue tracker
3. **Check troubleshooting guide**: Common solutions are documented above
4. **Create a new issue**: Include detailed information and logs

### Community

- **GitHub Issues**: For bug reports and feature requests
- **Discussions**: For questions and community support
- **Wiki**: Additional documentation and examples

### Commercial Support

For commercial support, custom features, or enterprise deployments, please contact [support@yourproject.com](mailto:support@yourproject.com).

## 📈 Project Status

### Current Version: 1.0.0

### Roadmap

- **v1.1**: Additional platform support (CodeChef, HackerRank)
- **v1.2**: Improved PDF customization options
- **v1.3**: Plugin system for custom scrapers
- **v2.0**: Web interface and cloud deployment options

### Statistics

- **Supported Platforms**: 3 (AtCoder, Codeforces, SPOJ)
- **Test Coverage**: 85%+
- **Languages**: Python 3.8+
- **Dependencies**: 8 core packages

## 🚀 Quick Links

- **[Installation Guide](#installation)**: Get started quickly
- **[User Manual](USER_MANUAL.md)**: Comprehensive usage guide
- **[Contributing](CONTRIBUTING.md)**: How to contribute
- **[Issue Tracker](https://github.com/your-username/OJ-Problem-Editorial-Downloader/issues)**: Report bugs or request features
- **[Latest Release](https://github.com/your-username/OJ-Problem-Editorial-Downloader/releases)**: Download the latest version

---

**Made with ❤️ for the competitive programming community**

If this tool helps you in your competitive programming journey, please consider giving it a ⭐ star on GitHub!