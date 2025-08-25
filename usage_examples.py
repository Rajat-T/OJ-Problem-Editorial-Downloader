#!/usr/bin/env python3
"""
Usage Examples for OJ Problem Editorial Downloader

This file demonstrates various ways to use the application
both through command line and programmatically.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def demo_command_line_usage():
    """
    Demonstrate command line usage examples
    """
    print("=== Command Line Usage Examples ===")
    
    examples = [
        # Basic usage
        "python main.py",
        "python main.py --help",
        "python main.py --version",
        
        # Single URL processing
        'python main.py --url "https://atcoder.jp/contests/abc001/tasks/abc001_a"',
        'python main.py --url "https://codeforces.com/contest/1/problem/A" --output ./downloads',
        
        # Batch processing
        "python main.py --batch test_urls.txt",
        "python main.py --batch test_urls.txt --output ./pdfs",
        "python main.py --batch test_urls.txt --headless",
        
        # Advanced options
        "python main.py --log-level DEBUG",
        "python main.py --no-gui --batch test_urls.txt",
        "python main.py --config custom_config.ini --batch test_urls.txt",
        
        # Server deployment
        "python main.py --no-gui --headless --batch problems.txt --output /var/www/pdfs",
    ]
    
    for example in examples:
        print(f"  {example}")
    print()

def demo_programmatic_usage():
    """
    Demonstrate programmatic usage of the ApplicationManager
    """
    print("=== Programmatic Usage Example ===")
    
    try:
        from main import ApplicationManager
        
        # Create and initialize application manager
        app_manager = ApplicationManager()
        
        # Override default settings
        app_manager.settings.update({
            "log_level": "INFO",
            "output_directory": "./example_output",
            "max_concurrent_downloads": 2
        })
        
        # Initialize the application
        app_manager.initialize()
        print("✓ Application initialized successfully")
        
        # Example: Batch processing
        test_urls = [
            "https://atcoder.jp/contests/abc001/tasks/abc001_a",
            "https://codeforces.com/contest/1/problem/A"
        ]
        
        print(f"Processing {len(test_urls)} URLs...")
        # successful, failed = app_manager.run_batch_processing(test_urls)
        # print(f"✓ Batch processing: {successful} successful, {failed} failed")
        
        # Check components
        print(f"✓ Available scrapers: {list(app_manager.scrapers.keys())}")
        print(f"✓ PDF creator available: {app_manager.pdf_creator is not None}")
        
        # Cleanup
        app_manager.shutdown()
        print("✓ Application shutdown completed")
        
    except Exception as e:
        print(f"✗ Error in programmatic usage: {e}")

def demo_individual_components():
    """
    Demonstrate using individual components
    """
    print("=== Individual Component Usage ===")
    
    try:
        # URL Parser example
        from utils.url_parser import URLParser
        
        parser = URLParser()
        test_url = "https://atcoder.jp/contests/abc001/tasks/abc001_a"
        
        platform = parser.detect_platform(test_url)
        is_valid = parser.is_valid_url(test_url)
        
        print(f"URL: {test_url}")
        print(f"✓ Platform detected: {platform}")
        print(f"✓ Valid URL: {is_valid}")
        
        # Individual scraper example
        from scraper.atcoder_scraper import AtCoderScraper
        
        scraper = AtCoderScraper(headless=True, timeout=30)
        print(f"✓ AtCoder scraper initialized")
        print(f"✓ Supports URL: {scraper.is_valid_url(test_url)}")
        
        # PDF Creator example
        from pdf_generator.pdf_creator import PDFCreator
        
        pdf_creator = PDFCreator(output_dir="./example_output")
        print(f"✓ PDF creator initialized")
        print(f"✓ Output directory: {pdf_creator.output_dir}")
        
    except Exception as e:
        print(f"✗ Error in component usage: {e}")

def demo_configuration():
    """
    Demonstrate configuration options
    """
    print("=== Configuration Examples ===")
    
    # Example configuration file content
    config_ini = """
[DEFAULT]
timeout = 30
rate_limit = 1.0
max_retries = 3
headless_browser = true

[Paths]
output_directory = ./output
temp_directory = ./temp

[Scraping]
user_agent = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
concurrent_downloads = 3
"""
    
    settings_json = """
{
  "output_directory": "./output",
  "log_level": "INFO",
  "max_concurrent_downloads": 3,
  "default_timeout": 30,
  "rate_limit": 1.0,
  "auto_save_settings": true,
  "backup_on_error": true,
  "theme": "light",
  "window_geometry": "800x600",
  "last_used_urls": [],
  "max_url_history": 20
}
"""
    
    print("Example config.ini:")
    print(config_ini)
    
    print("Example settings.json:")
    print(settings_json)

def create_test_files():
    """
    Create test files for demonstration
    """
    print("=== Creating Test Files ===")
    
    # Create test URLs file
    test_urls_content = """# Test URLs for OJ Problem Editorial Downloader
# AtCoder examples
https://atcoder.jp/contests/abc001/tasks/abc001_a
https://atcoder.jp/contests/abc001/tasks/abc001_b

# Codeforces examples
https://codeforces.com/contest/1/problem/A
https://codeforces.com/contest/1/problem/B

# SPOJ examples
https://www.spoj.com/problems/TEST/
"""
    
    try:
        with open("example_urls.txt", "w", encoding="utf-8") as f:
            f.write(test_urls_content)
        print("✓ Created example_urls.txt")
        
        # Create custom config
        config_content = """[DEFAULT]
timeout = 60
headless_browser = true

[Paths]
output_directory = ./example_output
"""
        
        with open("example_config.ini", "w", encoding="utf-8") as f:
            f.write(config_content)
        print("✓ Created example_config.ini")
        
    except Exception as e:
        print(f"✗ Error creating test files: {e}")

def main():
    """
    Run all usage examples
    """
    print("OJ Problem Editorial Downloader - Usage Examples")
    print("=" * 50)
    
    demo_command_line_usage()
    demo_programmatic_usage()
    demo_individual_components()
    demo_configuration()
    create_test_files()
    
    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nTry running:")
    print("  python main.py --help")
    print("  python main.py --batch example_urls.txt")
    print("  python main.py")

if __name__ == "__main__":
    main()