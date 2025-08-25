# OJ Problem Editorial Downloader

A comprehensive Python application for downloading and generating PDF documents from Online Judge (OJ) problem statements and editorials. Supports multiple competitive programming platforms including AtCoder, Codeforces, and SPOJ.

## Features

- **Multi-Platform Support**: AtCoder, Codeforces, and SPOJ
- **Flexible Download Options**: Problem statements, editorials, or combined documents
- **PDF Generation**: Clean, formatted PDF documents with proper styling
- **User-Friendly GUI**: Intuitive tkinter-based interface
- **Robust Scraping**: Uses both requests and Selenium for reliable data extraction
- **Image Support**: Downloads and embeds images in PDF documents
- **URL Validation**: Automatic platform detection and URL validation
- **Error Handling**: Comprehensive error handling and logging

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

## Installation

### Prerequisites

- Python 3.8 or higher
- Chrome browser (for Selenium WebDriver)

### Setup

1. **Clone or download the project**:
   ```bash
   git clone <repository-url>
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

## Usage

### GUI Application

1. **Launch the application**:
   ```bash
   python main.py
   ```

2. **Enter URL**: Paste the problem or editorial URL in the input field

3. **Validate URL**: Click "Validate URL" to check if the URL is supported

4. **Select Options**:
   - Choose download type (Problem Only, Editorial Only, or Both)
   - Enable/disable headless browser mode
   - Set output directory

5. **Download**: Click "Download & Generate PDF" to start the process

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

## Troubleshooting

### Common Issues

1. **Chrome Driver Issues**:
   - Ensure Chrome browser is installed
   - WebDriver is managed automatically by `webdriver-manager`

2. **Network Timeouts**:
   - Check internet connection
   - Some platforms may have rate limiting

3. **PDF Generation Issues**:
   - Ensure sufficient disk space
   - Check output directory permissions

4. **Missing Content**:
   - Some editorials may not be publicly available
   - SPOJ has limited editorial support

### Performance Tips

- Use headless mode for faster scraping
- Close unnecessary browser windows
- Clear cache directory periodically
- Use specific URLs rather than general contest pages

## Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Adding New Platforms

To add support for a new platform:

1. Create a new scraper class inheriting from `BaseScraper`
2. Implement required methods: `extract_problem_info`, `extract_editorial_info`, `is_valid_url`
3. Add URL patterns to `URLParser`
4. Update the main window to include the new scraper
5. Test thoroughly with various URLs

## License

This project is open source. Please check the license file for details.

## Disclaimer

This tool is for educational purposes. Please respect the terms of service of the platforms you're scraping and use responsibly. Always check robots.txt and platform policies before scraping.

## Support

For issues, questions, or contributions:
- Check existing issues in the repository
- Create new issues with detailed descriptions
- Include logs and error messages when reporting bugs

## Changelog

### Version 1.0.0
- Initial release
- Support for AtCoder, Codeforces, and SPOJ
- GUI interface with tkinter
- PDF generation with ReportLab
- Comprehensive error handling and logging