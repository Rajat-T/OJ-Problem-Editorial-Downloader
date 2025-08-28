# Webpage-to-PDF Downloader for Competitive Programming

## Overview

The OJ Problem Editorial Downloader has been transformed into a powerful **webpage-to-PDF downloader** specifically optimized for competitive programming platforms and **LLM training purposes**. The system now prioritizes direct webpage conversion while maintaining high-quality PDF output optimized for machine learning models.

## Key Features

### 🚀 Direct PDF Generation (Default Mode)
- **One-click webpage conversion**: Direct HTML-to-PDF using WeasyPrint
- **Original layout preservation**: Maintains visual fidelity and styling
- **LLM-optimized output**: Enhanced text structure and semantic markup
- **Platform-specific optimizations**: Tailored CSS for competitive programming sites
- **Intelligent fallback**: Automatic traditional mode when needed

### 🤖 LLM Training Optimization
- **Semantic markup**: Content sections clearly labeled with markers
- **Enhanced text extraction**: Improved structure for better parsing
- **Content organization**: Logical flow optimized for training data
- **Platform-aware processing**: Site-specific improvements for better results
- **Standardized formatting**: Consistent output across different platforms

### 🌐 Enhanced Platform Support
- **AtCoder**: Complete problem statements and editorials
- **Codeforces**: Contest problems and blog editorials
- **SPOJ**: Classic programming problems
- **CodeChef**: Contest and practice problems *(NEW)*
- **Auto-detection**: Intelligent platform recognition

## Installation

### Quick Install
```bash
# Clone the repository
git clone https://github.com/your-repo/OJ-Problem-Editorial-Downloader.git
cd OJ-Problem-Editorial-Downloader

# Install dependencies
pip install -r requirements.txt

# For optimal PDF quality (recommended)
pip install weasyprint
```

### System Dependencies (Optional)
For best PDF rendering with WeasyPrint:

**macOS:**
```bash
brew install pango
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0
```

**Windows:**
WeasyPrint will work with basic features. For full functionality, use WSL.

## Usage

### 🖱️ Quick Start

**Single URL Processing:**
```bash
# Basic usage (uses direct PDF mode with LLM optimization by default)
python main.py --url \"https://codeforces.com/contest/1234/problem/A\" --no-gui

# CodeChef problem
python main.py --url \"https://www.codechef.com/problems/PROBLEM_CODE\" --no-gui

# AtCoder contest problem
python main.py --url \"https://atcoder.jp/contests/abc300/tasks/abc300_a\" --no-gui
```

**Batch Processing:**
```bash
# Create a URL file
echo \"https://codeforces.com/contest/1234/problem/A\" > urls.txt
echo \"https://www.codechef.com/problems/TEST\" >> urls.txt
echo \"https://atcoder.jp/contests/abc300/tasks/abc300_a\" >> urls.txt

# Process all URLs
python main.py --batch urls.txt --output ./contest_pdfs
```

### ⚙️ Advanced Configuration

**Mode Selection:**
```bash
# Direct PDF mode (default)
python main.py --url \"URL\" --direct-pdf

# Traditional scraping mode
python main.py --url \"URL\" --traditional-mode

# Disable LLM optimization
python main.py --url \"URL\" --no-llm-optimization
```

**Output Customization:**
```bash
# Custom output directory
python main.py --batch urls.txt --output ./my_pdfs

# Debug mode
python main.py --url \"URL\" --log-level DEBUG

# Headless processing
python main.py --batch urls.txt --headless
```

### 📚 Complete CLI Reference

| Option | Description | Default |
|--------|-------------|----------|
| `--direct-pdf` | Use direct webpage-to-PDF conversion | ✅ Enabled |
| `--traditional-mode` | Use traditional scraping mode | ❌ Disabled |
| `--llm-optimized` | Apply LLM training optimizations | ✅ Enabled |
| `--no-llm-optimization` | Disable LLM optimizations | ❌ Disabled |
| `--batch FILE` | Process URLs from file | - |
| `--url URL` | Process single URL | - |
| `--output DIR` | Output directory | `./output` |
| `--headless` | Run browser in headless mode | ❌ |
| `--no-gui` | Disable GUI mode | ❌ |
| `--log-level LEVEL` | Set logging level | `INFO` |

## LLM Training Optimization Features

### 🎯 Content Structure Enhancement

The LLM optimization mode adds semantic markers to identify different content sections:

```
[PROBLEM_TITLE] Contest Problem A
[PROBLEM_STATEMENT] Given an array of integers...
[CONSTRAINTS] 1 ≤ N ≤ 10^5
[INPUT_FORMAT] First line contains...
[OUTPUT_FORMAT] Print the answer...
[SAMPLE_INPUT] 3\n1 2 3
[SAMPLE_OUTPUT] 6
[CODE_BLOCK] for i in range(n):
```

### 📝 Text Extraction Benefits

1. **Structured Content**: Clear section demarcation
2. **Semantic Markup**: Content type identification
3. **Enhanced Readability**: Improved formatting for parsing
4. **Platform Consistency**: Standardized output across sites
5. **Training Ready**: Optimized for ML model consumption

### 🔧 Platform-Specific Optimizations

**Codeforces:**
- Problem statement extraction
- Input/output specification parsing
- Contest metadata preservation
- Blog editorial processing

**AtCoder:**
- Multi-language support
- Editorial integration
- Contest information
- Mathematical expression handling

**CodeChef:**
- Problem description parsing
- Author information extraction
- Contest metadata
- Discussion integration

**SPOJ:**
- Classic problem format
- Constraint extraction
- Basic statistics

## Configuration

### 📄 Configuration File

Create `config.ini` for custom settings:

```ini
[DEFAULT]
# Output settings
output_directory = ./pdfs
log_level = INFO

# Processing settings
max_concurrent_downloads = 3
default_timeout = 30
rate_limit = 1.0

# PDF settings
llm_optimized = true
direct_pdf_mode = true

# Browser settings
headless_browser = true
```

### 🎨 Custom CSS Styling

Add custom CSS for PDF generation:

```python
from pdf_generator.pdf_creator import PDFCreator

custom_css = \"\"\"
.problem-title {
    color: #2c3e50;
    font-size: 18pt;
    border-bottom: 2px solid #3498db;
}
\".contest-info {
    background: #ecf0f1;
    padding: 10px;
    margin: 10px 0;
}
\"\"\"

pdf_creator = PDFCreator()
pdf_path = pdf_creator.create_webpage_pdf(
    url=\"https://codeforces.com/contest/1234/problem/A\",
    custom_css=custom_css,
    llm_optimized=True
)
```

## Programming Interface

### 🐍 Python API

**Basic Usage:**
```python
from pdf_generator.pdf_creator import PDFCreator
from scraper.codechef_scraper import CodeChefScraper

# Initialize components
pdf_creator = PDFCreator(output_dir=\"./output\")
scraper = CodeChefScraper()

# Generate PDF directly from webpage
pdf_path = pdf_creator.create_webpage_pdf(
    url=\"https://www.codechef.com/problems/PROBLEM_CODE\",
    llm_optimized=True
)

print(f\"PDF generated: {pdf_path}\")
```

**Advanced Usage:**
```python
from main import ApplicationManager

# Initialize application
app = ApplicationManager()
app.initialize()

# Process multiple URLs
urls = [
    \"https://codeforces.com/contest/1234/problem/A\",
    \"https://www.codechef.com/problems/TEST\",
    \"https://atcoder.jp/contests/abc300/tasks/abc300_a\"
]

success, failed = app.run_batch_processing(
    urls=urls,
    output_dir=\"./batch_output\",
    direct_pdf=True,
    llm_optimized=True
)

print(f\"Processed: {success} successful, {failed} failed\")
```

### 🔍 Platform Detection

```python
from scraper.base_scraper import BaseScraper

# Check platform patterns
patterns = BaseScraper.PLATFORM_PATTERNS
print(\"Supported platforms:\", list(patterns.keys()))
# Output: ['AtCoder', 'Codeforces', 'SPOJ', 'CodeChef']

# Platform-specific scraper
from scraper.codechef_scraper import CodeChefScraper

scraper = CodeChefScraper()
if scraper.is_valid_url(\"https://www.codechef.com/problems/TEST\"):
    print(\"Valid CodeChef URL\")
```

## Troubleshooting

### 🚨 Common Issues

**1. WeasyPrint Not Available**
```
WeasyPrint not available: cannot load library 'libpango-1.0-0'
```
**Solution:** Install system dependencies or use fallback mode
```bash
# The system will automatically use traditional mode
python main.py --url \"URL\" --traditional-mode
```

**2. PDF Generation Fails**
```
Failed to generate PDF from webpage
```
**Solution:** Enable debug logging and check fallback
```bash
python main.py --url \"URL\" --log-level DEBUG
```

**3. Rate Limiting Issues**
```
Too many requests error
```
**Solution:** Increase rate limiting
```bash
# Add delay between requests
python main.py --batch urls.txt --config custom_config.ini
```

### 📊 Performance Tips

1. **Use headless mode** for faster processing:
   ```bash
   python main.py --batch urls.txt --headless
   ```

2. **Enable concurrent processing** in config:
   ```ini
   [DEFAULT]
   max_concurrent_downloads = 3
   ```

3. **Optimize for LLM training**:
   ```bash
   python main.py --batch training_urls.txt --llm-optimized --output ./training_data
   ```

### 🔧 Debug Mode

```bash
# Enable detailed logging
python main.py --url \"URL\" --log-level DEBUG --no-gui

# Check configuration
python -c \"from main import ApplicationManager; app = ApplicationManager(); app.initialize(); print(app.settings)\"
```

## Output Examples

### 📁 File Structure

```
output/
├── codeforces_com_contest_1234_problem_A.pdf
├── www_codechef_com_problems_TEST.pdf
├── atcoder_jp_contests_abc300_tasks_abc300_a.pdf
└── images/
    ├── problem_diagram_1.png
    └── sample_image_2.jpg
```

### 📄 PDF Content Structure (LLM-Optimized)

```
[PROBLEM_TITLE] A. Water Buying

[PROBLEM_STATEMENT] 
Vasya wants to buy exactly n bottles of water...

[CONSTRAINTS]
1 ≤ n ≤ 10^4
1 ≤ a, b ≤ 10^9

[INPUT_FORMAT]
The first line contains three integers n, a, b...

[OUTPUT_FORMAT]
For each test case print the minimum amount of money...

[SAMPLE_INPUT]
3
1 10 15
2 10 15
3 10 15

[SAMPLE_OUTPUT]
10
20
25
```

## Migration from Previous Version

### 🔄 Breaking Changes

1. **Default Mode**: Direct PDF is now the default (was traditional)
2. **LLM Optimization**: Enabled by default
3. **New Platform**: CodeChef support added
4. **CLI Options**: New flags for mode control

### 📝 Migration Guide

**Old Command:**
```bash
python main.py --url \"URL\"
```

**New Equivalent:**
```bash
# Same behavior as before
python main.py --url \"URL\" --traditional-mode --no-llm-optimization

# Or use new optimized mode (recommended)
python main.py --url \"URL\"  # Uses direct PDF + LLM optimization
```

**Batch Processing:**
```bash
# Old way still works
python main.py --batch urls.txt

# New optimized way
python main.py --batch urls.txt --llm-optimized
```

## Contributing

### 🛠️ Development Setup

```bash
# Clone and setup development environment
git clone https://github.com/your-repo/OJ-Problem-Editorial-Downloader.git
cd OJ-Problem-Editorial-Downloader

# Install development dependencies
pip install -r requirements.txt
pip install -e .

# Run tests
python -m pytest tests/
```

### 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test suite
python -m pytest tests/test_webpage_pdf_llm.py -v

# Test CLI functionality
python main.py --help
```

### 🚀 Adding New Platforms

1. Create new scraper in `scraper/` directory
2. Inherit from `BaseScraper` class
3. Update `PLATFORM_PATTERNS` in base scraper
4. Add platform initialization in `main.py`
5. Add platform-specific CSS optimization
6. Create tests for the new platform

## License

MIT License - See LICENSE file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Documentation**: [Project Wiki](https://github.com/your-repo/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)

---

**Happy competitive programming! 🏆**