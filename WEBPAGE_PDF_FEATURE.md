# Webpage-to-PDF Download Feature

## Overview

The OJ Problem Editorial Downloader now supports direct webpage-to-PDF conversion, which preserves the original layout and styling of the webpage instead of extracting and reformatting the content.

## Key Differences

### Traditional Mode (Optional)
- Scrapes content from the webpage
- Extracts text, images, and structured data
- Reformats everything into a clean PDF layout
- Works even when the webpage has complex JavaScript or dynamic content
- Better for text-focused content

### Direct PDF Mode (Default)
- Exact rendering via Chrome print-to-PDF (pixel-perfect)
- Preserves original styling, fonts, and layout
- Ideal for visually rich or JS-driven pages
- Optional HTML renderer (WeasyPrint) with `--no-exact`

## Usage

### Command Line

#### Single URL
```bash
# Direct PDF mode (exact by default)
python main.py --url "https://codeforces.com/problemset/problem/1/A" --no-gui
```

#### Batch Processing
```bash
# Batch (direct PDF mode with exact rendering)
python main.py --batch urls.txt --output ./pdfs --no-gui
```

### Programmatic Usage

#### Using Scrapers Directly
```python
from scraper.codeforces_scraper import CodeforcesScraper

scraper = CodeforcesScraper()

# Direct PDF download
success = scraper.download_problem_as_pdf(
    url="https://codeforces.com/problemset/problem/1/A",
    output_path="./problem.pdf",
    use_selenium=False  # Set to True for JavaScript-heavy pages
)
```

#### Using PDF Creator
```python
from pdf_generator.pdf_creator import PDFCreator

pdf_creator = PDFCreator(output_dir="./output")

# Create PDF from any webpage
pdf_path = pdf_creator.create_webpage_pdf(
    url="https://codeforces.com/problemset/problem/1/A",
    output_filename="custom_name.pdf",
    use_selenium=False
)
```

## Platform Support

### Codeforces
- `download_problem_as_pdf()` - Download problem pages with optimized CSS
- `download_editorial_as_pdf()` - Download editorial/blog pages
- Automatically removes navigation, ads, and other non-content elements

### AtCoder
- Inherits base webpage-to-PDF functionality
- Generic content extraction and PDF generation

### SPOJ
- Inherits base webpage-to-PDF functionality
- Generic content extraction and PDF generation

## Technical Details

### Dependencies
- **Google Chrome + Selenium**: Exact rendering via DevTools `printToPDF`
- **WeasyPrint**: Optional HTML-to-PDF when using `--no-exact`

### CSS Optimizations
The direct PDF mode applies platform-specific CSS optimizations:
- Removes navigation menus, headers, footers
- Optimizes typography for print
- Ensures proper page breaks
- Improves code block formatting
- Handles mathematical expressions

### Error Handling
- Graceful fallback when WeasyPrint is not available
- Network error recovery with retries
- Detailed logging for troubleshooting

## Examples

### Command Line Examples
```bash
# Download a single Codeforces problem directly as PDF
python main.py --url "https://codeforces.com/problemset/problem/1/A" --direct-pdf --no-gui

# Batch download multiple problems
echo "https://codeforces.com/problemset/problem/1/A" > urls.txt
echo "https://codeforces.com/problemset/problem/4/A" >> urls.txt
python main.py --batch urls.txt --direct-pdf --output ./direct_pdfs

# Download with custom output directory and logging
python main.py --url "https://atcoder.jp/contests/abc123/tasks/abc123_a" \\
  --direct-pdf --output ./my_pdfs --log-level DEBUG --no-gui
```

### Output Files
Direct PDF mode generates filenames based on the URL structure:
- `codeforces_com_problemset_problem_1_A.pdf`
- `atcoder_jp_contests_abc123_tasks_abc123_a.pdf`

Traditional mode uses content-based names:
- `Codeforces_Problem_Title.pdf`
- `AtCoder_Problem_Title.pdf`

## When to Use Each Mode

### Use Direct PDF Mode When:
- You want to preserve the original webpage appearance
- The webpage has complex styling or layout
- You need faster processing
- You're archiving webpages for reference

### Use Traditional Mode When:
- You want clean, consistent PDF formatting
- The webpage has lots of advertisements or clutter
- You need structured data extraction
- You want text-optimized PDFs for better readability

## Troubleshooting

### WeasyPrint Not Available
Only required when using `--no-exact`. To enable HTML renderer:

1. Install system dependencies (platform-specific)
2. Install Python package: `pip install weasyprint`

### Network Errors
The system includes comprehensive error handling for:
- Rate limiting (automatic delays)
- Connection timeouts (retries with backoff)
- 403/404 errors (graceful fallback)

### Large File Sizes
Direct PDF mode may create larger files than traditional mode because it preserves all styling and images. Use traditional mode if file size is a concern.
