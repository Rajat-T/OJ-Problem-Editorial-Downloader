# OJ Problem Editorial Downloader - User Manual

## 📚 Table of Contents

1. [Introduction](#introduction)
2. [Installation Guide](#installation-guide)
3. [Getting Started](#getting-started)
4. [GUI User Guide](#gui-user-guide)
5. [Command Line Usage](#command-line-usage)
6. [Platform-Specific Features](#platform-specific-features)
7. [Configuration Options](#configuration-options)
8. [Batch Processing](#batch-processing)
9. [PDF Customization](#pdf-customization)
10. [Troubleshooting](#troubleshooting)
11. [Advanced Usage](#advanced-usage)
12. [Tips and Best Practices](#tips-and-best-practices)

## 📖 Introduction

The OJ Problem Editorial Downloader is a comprehensive tool designed to help competitive programmers download and organize problem statements and editorials from popular online judge platforms. This manual will guide you through all features and capabilities of the application.

### What You Can Do

- **Download Problem Statements**: Extract complete problem descriptions with examples
- **Download Editorials**: Get official solutions and explanations
- **Generate Professional PDFs**: Create clean, formatted documents for offline study
- **Batch Processing**: Process multiple URLs at once
- **Platform Support**: Works with AtCoder, Codeforces, and SPOJ
- **Flexible Usage**: Both GUI and command-line interfaces available

### System Requirements

- **Python 3.8 or higher**
- **Google Chrome browser** (latest version recommended)
- **Internet connection** for downloading content
- **2GB+ RAM** for optimal performance
- **100MB+ free disk space** for application and generated PDFs

## 🚀 Installation Guide

### Method 1: Quick Install (Recommended)

1. **Download the latest release** from the project repository
2. **Extract the files** to your preferred directory
3. **Run the installer**:
   ```bash
   pip install -e .
   ```
4. **Start the application**:
   ```bash
   oj-downloader
   ```

### Method 2: Development Install

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/OJ-Problem-Editorial-Downloader.git
   cd OJ-Problem-Editorial-Downloader
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python -m venv oj_env
   # Windows
   oj_env\\Scripts\\activate
   # macOS/Linux
   source oj_env/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Test the installation**:
   ```bash
   python main.py --version
   ```

### Verification

To verify your installation works correctly:

```bash
# Test basic functionality
python main.py --help

# Test with a sample URL
python main.py --url "https://atcoder.jp/contests/abc300/tasks/abc300_a" --output ./test_output
```

## 🎯 Getting Started

### First-Time Setup

1. **Launch the application** for the first time:
   ```bash
   python main.py
   ```

2. **Configure basic settings**:
   - Output directory: Choose where PDFs will be saved
   - Browser mode: Enable/disable headless mode
   - Logging level: Set to INFO for normal use, DEBUG for troubleshooting

3. **Test with a simple URL**:
   - AtCoder: `https://atcoder.jp/contests/abc300/tasks/abc300_a`
   - Codeforces: `https://codeforces.com/contest/1800/problem/A`
   - SPOJ: `https://www.spoj.com/problems/PRIME1/`

### Understanding the Interface

The application provides two main interfaces:

1. **Graphical User Interface (GUI)**: User-friendly point-and-click interface
2. **Command Line Interface (CLI)**: Powerful automation and batch processing

## 🖥️ GUI User Guide

### Main Window Overview

When you launch the GUI, you'll see the main window with several sections:

#### 1. URL Input Section
- **URL Field**: Enter the problem or editorial URL here
- **Validate Button**: Check if the URL is supported before processing
- **Platform Display**: Shows which platform was detected

#### 2. Options Section
- **Download Type**: Choose what to download
  - **Problem Only**: Just the problem statement
  - **Editorial Only**: Just the editorial/solution
  - **Both**: Problem statement and editorial combined
- **Browser Mode**: 
  - **Headless**: Faster processing, no browser window
  - **Visible**: Slower but you can see what's happening
- **Output Directory**: Where to save the generated PDFs

#### 3. Progress Section
- **Progress Bar**: Shows download and PDF generation progress
- **Status Messages**: Real-time updates on current operations
- **Log Display**: Detailed logging information

#### 4. Control Buttons
- **Download & Generate PDF**: Start the process
- **Clear Log**: Clear the log display
- **Settings**: Open configuration dialog
- **Help**: Access this manual

### Step-by-Step GUI Usage

#### Basic Usage

1. **Start the application**:
   ```bash
   python main.py
   ```

2. **Enter a URL** in the URL input field:
   ```
   https://atcoder.jp/contests/abc300/tasks/abc300_a
   ```

3. **Click "Validate URL"** to ensure it's supported:
   - ✅ Green checkmark: URL is valid and supported
   - ❌ Red X: URL is invalid or unsupported
   - ⚠️ Yellow warning: URL may work but has issues

4. **Select download options**:
   - Choose "Problem Only" for just the problem statement
   - Choose "Editorial Only" if you only want the solution
   - Choose "Both" for a combined document

5. **Configure browser mode**:
   - Keep "Headless" checked for faster processing
   - Uncheck for debugging or if you want to see the browser

6. **Set output directory** (optional):
   - Default: `./output/` in the application directory
   - Click "Browse" to choose a different location

7. **Click "Download & Generate PDF"**:
   - Watch the progress bar for completion status
   - Check the log for detailed progress information

8. **Find your PDF**:
   - Check the output directory you specified
   - PDFs are named with platform, contest, and problem identifiers

#### Advanced GUI Features

##### Settings Configuration

Click the "Settings" button to access advanced options:

- **Network Settings**:
  - Request timeout (default: 30 seconds)
  - Rate limiting delay (default: 1.0 seconds)
  - Maximum retry attempts (default: 3)

- **PDF Settings**:
  - Page size (A4, Letter, etc.)
  - Font family and size
  - Include images (enabled by default)
  - Color scheme (default, dark, high contrast)

- **Application Settings**:
  - Default output directory
  - Logging level
  - Auto-save settings
  - GUI theme

##### Batch Processing via GUI

1. **Create a URLs file** (e.g., `my_urls.txt`):
   ```
   https://atcoder.jp/contests/abc300/tasks/abc300_a
   https://codeforces.com/contest/1800/problem/A
   https://www.spoj.com/problems/PRIME1/
   ```

2. **Use File Menu**:
   - Click "File" → "Process Batch File"
   - Select your URLs file
   - Configure batch processing options
   - Start processing

## 💻 Command Line Usage

The CLI provides powerful automation capabilities and is ideal for batch processing.

### Basic CLI Commands

#### Single URL Processing

```bash
# Download problem statement only
python main.py --url "https://atcoder.jp/contests/abc300/tasks/abc300_a"

# Download with custom output directory
python main.py --url "URL" --output "./my_pdfs"

# Download in visible browser mode (for debugging)
python main.py --url "URL" --no-headless
```

#### Batch Processing

```bash
# Process URLs from file
python main.py --batch urls.txt

# Batch processing with custom settings
python main.py --batch urls.txt --output "./batch_pdfs" --log-level DEBUG
```

#### Configuration Options

```bash
# Use custom configuration file
python main.py --config my_config.ini --batch urls.txt

# Set specific logging level
python main.py --log-level WARNING --url "URL"

# Run without GUI (pure command line)
python main.py --no-gui --batch urls.txt
```

### Complete CLI Reference

| Option | Short | Arguments | Description |
|--------|-------|-----------|-------------|
| `--help` | `-h` | None | Show help message and exit |
| `--version` | `-v` | None | Show version number |
| `--url` | `-u` | URL | Process single URL |
| `--batch` | `-b` | FILE | Process URLs from file |
| `--output` | `-o` | DIRECTORY | Output directory for PDFs |
| `--config` | `-c` | FILE | Configuration file path |
| `--log-level` | | LEVEL | Set logging level (DEBUG, INFO, WARNING, ERROR) |
| `--headless` | | None | Run browser in headless mode |
| `--no-gui` | | None | Disable GUI mode |

### CLI Examples

#### Example 1: Basic Problem Download
```bash
python main.py --url "https://atcoder.jp/contests/abc300/tasks/abc300_a" --output "./pdfs"
```

#### Example 2: Batch Processing with Logging
```bash
python main.py --batch example_urls.txt --log-level DEBUG --output "./batch_results"
```

#### Example 3: Custom Configuration
```bash
python main.py --config ./my_config.ini --batch contest_urls.txt --headless
```

#### Example 4: Silent Processing
```bash
python main.py --no-gui --batch urls.txt --log-level ERROR --output "./silent_pdfs"
```

## 🌐 Platform-Specific Features

### AtCoder

#### Supported URL Formats
- **Problem URLs**: `https://atcoder.jp/contests/{contest}/tasks/{task}`
- **Editorial URLs**: `https://atcoder.jp/contests/{contest}/editorial`

#### Features
- Complete problem statements with constraints
- Sample input/output with explanations
- Automatic editorial URL generation from problem URLs
- Mathematical expressions and images
- Contest information and statistics

#### Example URLs
```
https://atcoder.jp/contests/abc300/tasks/abc300_a
https://atcoder.jp/contests/abc300/tasks/abc300_b
https://atcoder.jp/contests/abc300/editorial
https://atcoder.jp/contests/arc160/tasks/arc160_a
```

#### AtCoder-Specific Tips
- Editorial URLs work for entire contests
- Some older contests may have limited editorial support
- Mathematical expressions are rendered properly in PDFs
- Images are embedded with high quality

### Codeforces

#### Supported URL Formats
- **Contest Problems**: `https://codeforces.com/contest/{contest}/problem/{problem}`
- **Problemset**: `https://codeforces.com/problemset/problem/{contest}/{problem}`
- **Editorial Blogs**: `https://codeforces.com/blog/entry/{entry_id}`

#### Features
- Detailed problem statements with time/memory limits
- Input/output specifications
- Multiple sample test cases
- Editorial extraction from blog posts
- Rating and difficulty information

#### Example URLs
```
https://codeforces.com/contest/1800/problem/A
https://codeforces.com/problemset/problem/1800/A
https://codeforces.com/blog/entry/114500
```

#### Codeforces-Specific Tips
- Both contest and problemset URLs work
- Editorial blogs contain solutions for multiple problems
- Some problems have multiple editorial entries
- Images and diagrams are preserved

### SPOJ

#### Supported URL Formats
- **Problem URLs**: `https://www.spoj.com/problems/{problem_code}/`

#### Features
- Problem statements and descriptions
- Input/output format specifications
- Basic problem statistics
- Limited editorial support (not all problems have editorials)

#### Example URLs
```
https://www.spoj.com/problems/PRIME1/
https://www.spoj.com/problems/FCTRL/
https://www.spoj.com/problems/PALIN/
```

#### SPOJ-Specific Notes
- Editorial support is limited (SPOJ doesn't provide official editorials)
- Focus primarily on problem statements
- Some problems may have user-contributed solutions
- Simpler formatting compared to AtCoder/Codeforces

## ⚙️ Configuration Options

### Configuration File Format

The application uses INI format for configuration files:

```ini
# example_config.ini

[network]
timeout = 30
rate_limit = 1.0
max_retries = 3
user_agent = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36

[pdf]
page_size = A4
font_family = Arial
font_size = 11
include_images = true
color_scheme = default

[application]
output_directory = ./output
log_level = INFO
auto_save_settings = true
max_concurrent_downloads = 3

[gui]
theme = light
window_geometry = 800x600
auto_validate_urls = true
```

### Environment Variables

You can also configure the application using environment variables:

```bash
export OJ_DOWNLOADER_OUTPUT_DIR="./my_pdfs"
export OJ_DOWNLOADER_LOG_LEVEL="DEBUG"
export OJ_DOWNLOADER_TIMEOUT="60"
export OJ_DOWNLOADER_HEADLESS="true"
```

## 📊 Batch Processing

### Creating Batch Files

Batch files should contain one URL per line:

```text
# contest_urls.txt
# AtCoder ABC 300 problems
https://atcoder.jp/contests/abc300/tasks/abc300_a
https://atcoder.jp/contests/abc300/tasks/abc300_b
https://atcoder.jp/contests/abc300/tasks/abc300_c

# Codeforces Round 863
https://codeforces.com/contest/1800/problem/A
https://codeforces.com/contest/1800/problem/B

# SPOJ Classic problems
https://www.spoj.com/problems/PRIME1/
https://www.spoj.com/problems/FCTRL/
```

### Advanced Batch Processing

#### Parallel Processing
```bash
# Process multiple URLs concurrently (be respectful of rate limits)
python main.py --batch urls.txt --config high_performance.ini
```

#### Error Handling in Batches
```bash
# Continue processing even if some URLs fail
python main.py --batch urls.txt --continue-on-error --log-level INFO
```

#### Filtering and Validation
```bash
# Validate all URLs before processing
python main.py --batch urls.txt --validate-only

# Process only valid URLs
python main.py --batch urls.txt --skip-invalid
```

## 🎨 PDF Customization

### Default PDF Features

Generated PDFs include:
- **Professional formatting** with proper typography
- **Embedded images** with high resolution
- **Syntax highlighting** for code examples
- **Table of contents** for multi-section documents
- **Metadata** including source URL and generation date

### Customization Options

#### Page Layout
```ini
[pdf]
page_size = A4          # A4, Letter, Legal, A3
margin_top = 2.5cm
margin_bottom = 2.5cm
margin_left = 2cm
margin_right = 2cm
```

#### Typography
```ini
[pdf]
font_family = Arial     # Arial, Times, Courier, Helvetica
font_size = 11          # Base font size in points
line_spacing = 1.2      # Line height multiplier
heading_font_size = 16  # Heading font size
```

#### Content Options
```ini
[pdf]
include_images = true           # Embed images
include_metadata = true         # Add source URL, date
include_toc = true             # Table of contents
syntax_highlighting = true      # Code syntax highlighting
preserve_formatting = true     # Keep original formatting
```

### PDF Quality Settings

For different use cases:

#### High Quality (for printing)
```ini
[pdf]
image_dpi = 300
compression = false
embed_fonts = true
```

#### Web Optimized (smaller file size)
```ini
[pdf]
image_dpi = 150
compression = true
embed_fonts = false
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### Issue: "Chrome driver not found"
**Symptoms**: Error messages about missing ChromeDriver
**Solutions**:
1. Update Chrome browser to latest version
2. Clear WebDriver cache: `rm -rf ~/.wdm` (Linux/macOS) or `del %USERPROFILE%\.wdm` (Windows)
3. Reinstall webdriver-manager: `pip uninstall webdriver-manager && pip install webdriver-manager`

#### Issue: "Connection timeout"
**Symptoms**: Requests fail with timeout errors
**Solutions**:
1. Check internet connection
2. Increase timeout in configuration: `timeout = 60`
3. Use VPN if platform is geographically restricted
4. Check if platform is experiencing downtime

#### Issue: "Empty PDF generated"
**Symptoms**: PDF file is created but contains no content
**Solutions**:
1. Verify URL is accessible in browser
2. Check if editorial is publicly available
3. Enable non-headless mode for debugging: `--no-headless`
4. Check logs for specific error messages

#### Issue: "Permission denied when saving PDF"
**Symptoms**: Cannot write to output directory
**Solutions**:
1. Check directory permissions: `chmod 755 ./output`
2. Run without administrator privileges
3. Choose different output directory
4. Ensure sufficient disk space

### Debug Mode

Enable comprehensive debugging:

```bash
python main.py --log-level DEBUG --no-headless --url "problematic-url"
```

This will:
- Show detailed operation logs
- Display browser window for visual debugging
- Provide error context and stack traces

### Getting Additional Help

1. **Check logs**: Always review the log output for specific error messages
2. **Test with known URLs**: Use URLs from `example_urls.txt`
3. **Update dependencies**: `pip install --upgrade -r requirements.txt`
4. **Report issues**: Include logs, environment info, and reproduction steps

## 🚀 Advanced Usage

### Programmatic Usage

You can use the scrapers programmatically in your own Python scripts:

```python
from scraper.atcoder_scraper import AtCoderScraper
from pdf_generator.pdf_creator import PDFCreator

# Initialize components
scraper = AtCoderScraper(headless=True)
pdf_creator = PDFCreator()

# Extract problem data
url = "https://atcoder.jp/contests/abc300/tasks/abc300_a"
problem_data = scraper.get_problem_statement(url)

# Generate PDF
pdf_path = pdf_creator.create_problem_pdf(problem_data, "./output")
print(f"PDF saved to: {pdf_path}")
```

### Custom Scrapers

To add support for new platforms:

```python
from scraper.base_scraper import BaseScraper

class CustomPlatformScraper(BaseScraper):
    def is_valid_url(self, url: str) -> bool:
        # Implementation for URL validation
        pass
    
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        # Implementation for problem extraction
        pass
    
    def get_editorial(self, url: str) -> Optional[Dict[str, Any]]:
        # Implementation for editorial extraction
        pass
```

### Integration with Other Tools

#### Integration with Git
```bash
# Save PDFs in version control friendly way
python main.py --batch contest_urls.txt --output "./contest_pdfs" --naming-format "{platform}_{contest}_{problem}"
git add contest_pdfs/
git commit -m "Add contest PDFs for practice"
```

#### Integration with Study Scripts
```python
import subprocess
import os

def download_and_organize(contest_url, study_dir):
    # Download problems
    subprocess.run([
        "python", "main.py", 
        "--url", contest_url,
        "--output", study_dir
    ])
    
    # Organize files
    # ... additional processing
```

## 💡 Tips and Best Practices

### Performance Optimization

1. **Use headless mode**: Significantly faster processing
2. **Respect rate limits**: Don't set rate_limit below 1.0 seconds
3. **Batch processing**: More efficient than individual downloads
4. **Close unused applications**: Free up memory and CPU resources

### Organization Tips

1. **Organize by platform**: Create separate directories for each platform
2. **Use descriptive naming**: Include contest and problem identifiers
3. **Regular cleanup**: Remove temporary files and clear cache periodically
4. **Backup important PDFs**: Keep copies of contest materials

### Best Practices

1. **Test URLs first**: Always validate URLs before batch processing
2. **Monitor logs**: Check for warnings and errors during processing
3. **Respect platform terms**: Don't overload servers with excessive requests
4. **Keep software updated**: Regularly update dependencies and browsers

### Study Workflow Recommendations

1. **Pre-contest preparation**:
   ```bash
   # Download all problems before contest
   python main.py --batch contest_problems.txt --output "./contest_prep"
   ```

2. **Post-contest analysis**:
   ```bash
   # Download editorials after contest
   python main.py --batch editorial_urls.txt --output "./editorials"
   ```

3. **Practice sessions**:
   ```bash
   # Download specific problem types
   python main.py --batch dp_problems.txt --output "./practice/dp"
   ```

### Automation Examples

#### Daily Problem Download
```bash
#!/bin/bash
# daily_download.sh
DATE=$(date +%Y-%m-%d)
python main.py --batch daily_problems.txt --output "./daily/$DATE"
```

#### Contest Preparation Script
```python
# contest_prep.py
import subprocess
import sys

contest_id = sys.argv[1]
urls = [
    f"https://atcoder.jp/contests/{contest_id}/tasks/{contest_id}_a",
    f"https://atcoder.jp/contests/{contest_id}/tasks/{contest_id}_b",
    f"https://atcoder.jp/contests/{contest_id}/tasks/{contest_id}_c",
]

with open(f"{contest_id}_urls.txt", "w") as f:
    for url in urls:
        f.write(url + "\n")

subprocess.run([
    "python", "main.py", 
    "--batch", f"{contest_id}_urls.txt",
    "--output", f"./contests/{contest_id}"
])
```

---

This manual covers all major features and usage scenarios of the OJ Problem Editorial Downloader. For additional help or feature requests, please refer to the project's documentation or issue tracker.