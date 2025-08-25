#!/usr/bin/env python3
"""
OJ Problem Editorial Downloader
Main entry point for the application
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ui.main_window import MainWindow
from utils.url_parser import URLParser
from utils.file_manager import FileManager
from scraper.atcoder_scraper import AtCoderScraper
from scraper.codeforces_scraper import CodeforcesScraper
from scraper.spoj_scraper import SPOJScraper
from pdf_generator.pdf_creator import PDFCreator

def main():
    """
    Main function to start the OJ Problem Editorial Downloader application
    """
    try:
        # Initialize the GUI application
        app = MainWindow()
        app.run()
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()