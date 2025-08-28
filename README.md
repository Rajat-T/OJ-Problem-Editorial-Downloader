# 🔗 Webpage-to-PDF Downloader for Competitive Programming

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![WeasyPrint](https://img.shields.io/badge/WeasyPrint-Supported-green.svg)](https://weasyprint.org/)
[![LLM Optimized](https://img.shields.io/badge/LLM-Optimized-purple.svg)](#llm-training-optimization)

> **Transform competitive programming webpages into LLM-optimized PDFs**

A powerful, intelligent webpage-to-PDF converter specifically designed for competitive programming platforms, with advanced optimizations for LLM training data generation and direct webpage conversion capabilities.

## ✨ Key Features

### 🚀 **Direct PDF Generation (Default Mode)**
- **Exact rendering (default)**: Pixel-perfect PDFs via Chrome print-to-PDF
- **Original layout preserved**: Fonts, colors, spacing, dynamic content
- **HTML renderer (optional)**: WeasyPrint path with optional LLM optimization
- **JS support**: Automatic Selenium use where needed

### 🤖 **LLM Training Optimization**
- **Semantic markup**: Content sections clearly labeled with `[PROBLEM_TITLE]`, `[CONSTRAINTS]`, etc.
- **Enhanced text extraction**: Structured for optimal machine learning consumption
- **Platform-aware processing**: Site-specific optimizations for better parsing
- **Training-ready output**: Standardized format across all platforms

### 🌐 **Comprehensive Platform Support**
- **AtCoder** 🇯🇵 - Contest problems and editorials
- **Codeforces** 🌍 - Problems, contests, and blog editorials  
- **SPOJ** 📚 - Classic programming challenges
- **CodeChef** 🧑‍🍳 - Contest and practice problems *(NEW)*
- **Auto-detection** 🎯 - Intelligent platform recognition

## 🚀 Quick Start

### Installation
```bash
# Clone and install
git clone https://github.com/your-repo/OJ-Problem-Editorial-Downloader.git
cd OJ-Problem-Editorial-Downloader
pip install -r requirements.txt
```

### Basic Usage
```bash
# Convert single webpage to PDF (exact look by default)
python main.py --url "https://codeforces.com/contest/1234/problem/A" --no-gui

# Batch process multiple URLs
echo "https://codeforces.com/contest/1234/problem/A" > urls.txt
echo "https://www.codechef.com/problems/TEST" >> urls.txt
python main.py --batch urls.txt --output ./pdfs

# Traditional scraping mode (optional, re-formatted PDFs)
python main.py --url "URL" --traditional-mode --no-gui

# HTML renderer (not exact) with LLM optimization
python main.py --url "URL" --no-exact --llm-optimized --no-gui
```

### Output Example
```
[PROBLEM_TITLE] A. Water Buying
[PROBLEM_STATEMENT] Vasya wants to buy exactly n bottles...
[CONSTRAINTS] 1 ≤ n ≤ 10^4
[INPUT_FORMAT] The first line contains...
[SAMPLE_INPUT] 3
1 10 15
[SAMPLE_OUTPUT] 10
```

📚 **[Complete Documentation](USAGE_EXAMPLES.md)** | 🗺️ **[Platform Support](#platform-support)** | ⚙️ **[Configuration](#configuration)**

## Project Structure

```
OJ-Problem-Editorial-Downloader/
├── main.py                     # Entry point
├── requirements.txt            # Dependencies
├── README.md                   # This file
├── USAGE_EXAMPLES.md           # Usage examples
├── example_urls.txt            # Example URLs for testing
├── scraper/                    # Scraping logic
│   ├── __init__.py
│   ├── base_scraper.py         # Abstract base class
│   ├── atcoder_scraper.py      # AtCoder implementation
│   ├── codeforces_scraper.py   # Codeforces implementation
│   ├── spoj_scraper.py         # SPOJ implementation
│   └── codechef_scraper.py     # CodeChef implementation (NEW)
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

- **Python 3.8 or higher**
- **Google Chrome** (for exact rendering via Selenium/DevTools)

### Install Dependencies
```bash
pip install -r requirements.txt
```

## 🎯 Platform Support

### Codeforces
- Contest problems: `https://codeforces.com/contest/{contest_id}/problem/{problem_id}`
- Problemset: `https://codeforces.com/problemset/problem/{contest_id}/{problem_id}`
- Blog posts: `https://codeforces.com/blog/entry/{entry_id}`

### AtCoder
- ABC/ARC/AGC problems: `https://atcoder.jp/contests/{contest_id}/tasks/{task_id}`
- Editorials: `https://atcoder.jp/contests/{contest_id}/editorial`

### SPOJ
- Problems: `https://www.spoj.com/problems/{problem_id}/`

### CodeChef *(NEW)*
- Practice problems: `https://www.codechef.com/problems/{problem_id}`
- Contest problems: `https://www.codechef.com/{contest_id}/problems/{problem_id}`
- Editorials: `https://discuss.codechef.com/t/{problem_id}-editorial/{id}`

## ⚙️ Configuration

The downloader can be configured through command-line arguments or configuration files.

### Command Line Options
```bash
usage: main.py [-h] [--batch BATCH] [--url URL] [--output OUTPUT]
               [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
               [--config CONFIG] [--headless] [--no-gui] [--direct-pdf]
               [--traditional-mode] [--llm-optimized] [--no-llm-optimization]
               [--version]

OJ Problem Editorial Downloader

optional arguments:
  -h, --help            show this help message and exit
  --batch BATCH, -b BATCH
                        Batch process URLs from file (one URL per line)
  --url URL, -u URL     Process a single URL
  --output OUTPUT, -o OUTPUT
                        Output directory for generated PDFs
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}, -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set logging level (default: INFO)
  --config CONFIG, -c CONFIG
                        Path to custom configuration file
  --headless            Run browser in headless mode (for batch processing)
  --no-gui              Disable GUI mode (requires --batch or --url)
  --direct-pdf          Download webpages directly as PDF (preserves original
                        layout) - DEFAULT MODE
  --traditional-mode    Use traditional scraping mode instead of direct PDF
                        generation
  --llm-optimized       Apply LLM training optimizations to PDF output -
                        DEFAULT
  --no-llm-optimization
                        Disable LLM training optimizations
  --version, -v         show program's version number and exit
```

## 🤖 LLM Training Optimization (Optional)

When using the HTML renderer with `--llm-optimized`, PDFs are optimized for training with:

1. **Semantic Markers**: Content sections are clearly labeled with markers like `[PROBLEM_TITLE]`, `[INPUT_FORMAT]`, etc.
2. **Structured Format**: Consistent organization across all platforms
3. **Clean Text**: Minimal UI elements and advertisements
4. **Enhanced Readability**: Proper spacing and formatting for text extraction

### Example Output Structure
```
[PROBLEM_TITLE] A. Problem Name
[PROBLEM_STATEMENT] Problem description here...
[CONSTRAINTS] 1 ≤ n ≤ 10^5
[INPUT_FORMAT] Input specification...
[OUTPUT_FORMAT] Output specification...
[SAMPLE_INPUT] 3
1 2 3
[SAMPLE_OUTPUT] 6
```

## 🧪 Testing

Run the test suite to verify functionality:
```bash
python test_downloader.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📧 Support

For issues and feature requests, please [open an issue](https://github.com/your-repo/OJ-Problem-Editorial-Downloader/issues).
