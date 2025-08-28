#!/usr/bin/env python3
"""
OJ Problem Editorial Downloader
Main entry point for the application

This module provides:
- GUI initialization and management
- Command-line argument parsing for batch processing
- Logging configuration and management
- Application settings and preferences
- Graceful shutdown and cleanup
- Error recovery mechanisms
- Integration of all components (scraper, PDF generator, UI)
"""

__version__ = "1.0.0"
__author__ = "OJ Downloader Team"
__email__ = "support@ojdownloader.com"
__license__ = "MIT"
__description__ = "Download and generate PDFs from online judge problem statements and editorials"

import sys
import os
import argparse
import logging
import json
import signal
import atexit
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import configparser
import platform

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import application components
from ui.main_window import MainWindow
from utils.url_parser import URLParser
from utils.file_manager import FileManager
from scraper.atcoder_scraper import AtCoderScraper
from scraper.codeforces_scraper import CodeforcesScraper
from scraper.spoj_scraper import SPOJScraper
from scraper.codechef_scraper import CodeChefScraper
from pdf_generator.pdf_creator import PDFCreator

# Import comprehensive error handling
from utils.error_handler import (
    OJDownloaderError, NetworkError, URLValidationError, PDFGenerationError, 
    FileSystemError, handle_exception, error_reporter, ErrorCategory, ErrorSeverity
)


class ApplicationManager:
    """
    Main application manager that handles initialization, configuration,
    and lifecycle management of the OJ Problem Editorial Downloader.
    """
    
    def __init__(self):
        self.config_dir = Path.home() / ".oj_downloader"
        self.config_file = self.config_dir / "config.ini"
        self.log_file = self.config_dir / "app.log"
        self.settings_file = self.config_dir / "settings.json"
        
        # Application components
        self.gui_app = None
        self.url_parser = None
        self.file_manager = None
        self.pdf_creator = None
        self.scrapers = {}
        
        # Runtime state
        self.is_running = False
        self.shutdown_handlers = []
        
        # Default settings
        self.default_settings = {
            "output_directory": str(Path.cwd() / "output"),
            "log_level": "INFO",
            "max_concurrent_downloads": 3,
            "default_timeout": 30,
            "rate_limit": 1.0,
            "auto_save_settings": True,
            "backup_on_error": True,
            "theme": "light",
            "window_geometry": "800x600",
            "last_used_urls": [],
            "max_url_history": 20
        }
        
        self.settings = self.default_settings.copy()
        
    def initialize(self):
        """
        Initialize the application with all necessary configurations.
        """
        try:
            # Create configuration directory
            self._create_config_directory()
            
            # Load settings and configuration
            self._load_settings()
            self._load_configuration()
            
            # Setup logging
            self._setup_logging()
            
            # Initialize components
            self._initialize_components()
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            # Register cleanup handlers
            atexit.register(self._cleanup)
            
            self.is_running = True
            logging.info("Application initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize application: {e}")
            logging.error(traceback.format_exc())
            raise
    
    def _create_config_directory(self):
        """
        Create configuration directory if it doesn't exist.
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logging.debug(f"Configuration directory: {self.config_dir}")
        except Exception as e:
            logging.error(f"Failed to create config directory: {e}")
            # Fallback to current directory
            self.config_dir = Path.cwd() / ".oj_downloader"
            self.config_dir.mkdir(exist_ok=True)
    
    def _setup_logging(self):
        """
        Configure logging with file and console handlers.
        """
        log_level = getattr(logging, self.settings.get("log_level", "INFO").upper())
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # File handler
        try:
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)
        
        logging.info(f"Logging configured. Level: {log_level}, Log file: {self.log_file}")
    
    def _load_settings(self):
        """
        Load application settings from JSON file.
        """
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                self.settings.update(loaded_settings)
                logging.debug("Settings loaded successfully")
            else:
                logging.info("No existing settings file found, using defaults")
        except Exception as e:
            logging.warning(f"Failed to load settings: {e}. Using defaults.")
    
    def _save_settings(self):
        """
        Save current settings to JSON file.
        """
        try:
            if self.settings.get("auto_save_settings", True):
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, indent=2, ensure_ascii=False)
                logging.debug("Settings saved successfully")
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")
    
    def _load_configuration(self):
        """
        Load configuration from INI file.
        """
        self.config = configparser.ConfigParser()
        
        try:
            if self.config_file.exists():
                self.config.read(self.config_file, encoding='utf-8')
                logging.debug("Configuration loaded successfully")
            else:
                # Create default configuration
                self._create_default_configuration()
        except Exception as e:
            logging.warning(f"Failed to load configuration: {e}")
            self._create_default_configuration()
    
    def _create_default_configuration(self):
        """
        Create default configuration file.
        """
        self.config['DEFAULT'] = {
            'timeout': '30',
            'rate_limit': '1.0',
            'max_retries': '3',
            'headless_browser': 'true'
        }
        
        self.config['Paths'] = {
            'output_directory': str(Path.cwd() / "output"),
            'temp_directory': str(Path.cwd() / "temp")
        }
        
        self.config['Scraping'] = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'concurrent_downloads': '3'
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logging.info("Default configuration created")
        except Exception as e:
            logging.error(f"Failed to create default configuration: {e}")
    
    def _initialize_components(self):
        """
        Initialize all application components.
        """
        try:
            # Initialize utility components
            self.url_parser = URLParser()
            self.file_manager = FileManager()
            self.pdf_creator = PDFCreator()
            
            # Initialize scrapers with configuration
            timeout = self.config.getint('DEFAULT', 'timeout', fallback=30)
            headless = self.config.getboolean('DEFAULT', 'headless_browser', fallback=True)
            
            self.scrapers = {
                "AtCoder": AtCoderScraper(headless=headless, timeout=timeout),
                "Codeforces": CodeforcesScraper(headless=headless, timeout=timeout),
                "SPOJ": SPOJScraper(headless=headless, timeout=timeout),
                "CodeChef": CodeChefScraper(headless=headless, timeout=timeout)
            }
            
            logging.info("All components initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize components: {e}")
            raise
    
    def _setup_signal_handlers(self):
        """
        Setup signal handlers for graceful shutdown.
        """
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown()
        
        # Register signal handlers (Unix-like systems)
        if platform.system() != 'Windows':
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        else:
            # Windows specific
            signal.signal(signal.SIGINT, signal_handler)
    
    def add_shutdown_handler(self, handler):
        """
        Add a shutdown handler function.
        
        Args:
            handler: Function to call during shutdown
        """
        self.shutdown_handlers.append(handler)
    
    def run_gui(self):
        """
        Start the GUI application.
        """
        try:
            if not self.is_running:
                raise RuntimeError("Application not initialized")
            
            logging.info("Starting GUI application")
            
            # Create and configure GUI
            self.gui_app = MainWindow()
            
            # Apply saved settings to GUI
            self._apply_gui_settings()
            
            # Add shutdown handler for GUI cleanup
            self.add_shutdown_handler(self._gui_cleanup)
            
            # Start the GUI main loop
            self.gui_app.run()
            
        except Exception as e:
            logging.error(f"GUI application error: {e}")
            logging.error(traceback.format_exc())
            self._handle_error(e, "GUI Application Error")
    
    def _apply_gui_settings(self):
        """
        Apply saved settings to the GUI application.
        """
        try:
            if self.gui_app:
                # Set output directory
                output_dir = self.settings.get("output_directory")
                if output_dir:
                    self.gui_app.output_dir_var.set(output_dir)
                
                # Set window geometry
                geometry = self.settings.get("window_geometry")
                if geometry:
                    self.gui_app.root.geometry(geometry)
                
                # Load URL history
                url_history = self.settings.get("last_used_urls", [])
                self.gui_app.url_history = url_history
                if hasattr(self.gui_app, 'problem_combo'):
                    self.gui_app.problem_combo['values'] = url_history
                
        except Exception as e:
            logging.error(f"Failed to apply GUI settings: {e}")
    
    def _gui_cleanup(self):
        """
        Cleanup GUI-specific resources.
        """
        try:
            if self.gui_app:
                # Save current settings
                if hasattr(self.gui_app, 'output_dir_var'):
                    self.settings["output_directory"] = self.gui_app.output_dir_var.get()
                
                if hasattr(self.gui_app, 'root'):
                    try:
                        self.settings["window_geometry"] = self.gui_app.root.geometry()
                    except:
                        pass
                
                if hasattr(self.gui_app, 'url_history'):
                    # Keep only last N URLs
                    max_history = self.settings.get("max_url_history", 20)
                    self.settings["last_used_urls"] = self.gui_app.url_history[-max_history:]
                
                logging.info("GUI cleanup completed")
        except Exception as e:
            logging.error(f"Error during GUI cleanup: {e}")
    
    @handle_exception
    def run_batch_processing(self, urls: List[str], output_dir: Optional[str] = None, 
                           direct_pdf: bool = True, llm_optimized: bool = False,
                           exact_render: bool = True):
        """
        Run batch processing for multiple URLs with comprehensive error handling.
        
        Args:
            urls: List of URLs to process
            output_dir: Output directory (optional)
            direct_pdf: Whether to use direct webpage-to-PDF conversion (default: True)
            llm_optimized: Whether to apply LLM training optimizations (default: True)
            
        Returns:
            Tuple[int, int]: (successful_count, failed_count)
        """
        try:
            if not self.is_running:
                raise RuntimeError("Application not initialized")
            
            if not urls:
                logging.warning("No URLs provided for batch processing")
                return 0, 0

            output_dir = output_dir or self.settings.get("output_directory", str(Path.cwd() / "output"))
            max_workers = self.settings.get("max_concurrent_downloads", 3)
            
            # Validate output directory
            try:
                output_path = Path(output_dir)
                if not output_path.exists():
                    output_path.mkdir(parents=True, exist_ok=True)
                elif not output_path.is_dir():
                    raise FileSystemError(f"Output path is not a directory: {output_dir}", output_dir)
            except Exception as e:
                raise FileSystemError(f"Cannot access output directory: {output_dir}", output_dir, e)
            
            logging.info(f"Starting batch processing for {len(urls)} URLs ({'direct PDF' if direct_pdf else 'traditional'} mode{',' if direct_pdf else ''}{'LLM-optimized' if direct_pdf and llm_optimized else ''})")
            
            successful = 0
            failed = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for url in urls:
                    try:
                        future = executor.submit(self._process_single_url, url, output_dir, direct_pdf, llm_optimized, exact_render)
                        futures.append((url, future))
                    except Exception as e:
                        logging.error(f"Failed to submit URL for processing: {url}: {e}")
                        failed += 1
                
                for url, future in futures:
                    try:
                        result = future.result(timeout=300)  # 5 minute timeout per URL
                        if result:
                            successful += 1
                            logging.info(f"Successfully processed: {url}")
                        else:
                            failed += 1
                            logging.error(f"Failed to process: {url}")
                    except Exception as e:
                        failed += 1
                        logging.error(f"Error processing {url}: {e}")
                        self._handle_error(e, f"batch_processing_url_{url}")
            
            logging.info(f"Batch processing completed. Successful: {successful}, Failed: {failed}")
            
            # Generate summary report
            if failed > 0:
                error_summary = error_reporter.get_error_summary()
                logging.warning(f"Batch processing summary: {error_summary}")
            
            return successful, failed
            
        except Exception as e:
            logging.error(f"Batch processing error: {e}")
            self._handle_error(e, "batch_processing")
            return 0, len(urls)
    
    def _process_single_url(self, url: str, output_dir: str, direct_pdf: bool = True, llm_optimized: bool = False, exact_render: bool = True) -> bool:
        """
        Process a single URL for batch processing with enhanced direct PDF support.
        
        Args:
            url: URL to process
            output_dir: Output directory
            direct_pdf: Whether to use direct webpage-to-PDF conversion (default: True)
            llm_optimized: Whether to apply LLM training optimizations (default: True)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure PDF creator is available
            if not self.pdf_creator:
                logging.error("PDF creator not initialized")
                return False
            
            # Detect platform
            platform = None
            for platform_name, scraper in self.scrapers.items():
                if scraper.is_valid_url(url):
                    platform = platform_name
                    break
            
            if not platform:
                logging.error(f"Unsupported platform for URL: {url}")
                return False
            
            scraper = self.scrapers[platform]
            
            # Ensure output directory exists
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            if direct_pdf:
                # Use direct webpage-to-PDF conversion with LLM optimization
                logging.info(f"Using direct PDF conversion {'(LLM-optimized) ' if llm_optimized else ''}for: {url}")
                
                # Generate filename based on URL
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace('.', '_')
                path_part = parsed_url.path.replace('/', '_').strip('_')
                
                if path_part:
                    filename = f"{domain}_{path_part}.pdf"
                else:
                    filename = f"{domain}.pdf"
                
                output_path = Path(output_dir) / filename
                
                # Use enhanced create_webpage_pdf method
                try:
                    self.pdf_creator.output_dir = Path(output_dir)
                    if exact_render:
                        # Chrome print-to-PDF for pixel-perfect output
                        pdf_path = self.pdf_creator.create_webpage_pdf(
                            url=url,
                            output_filename=filename,
                            use_selenium=True,
                            llm_optimized=False,
                            exact_render=True
                        )
                        if pdf_path and Path(pdf_path).exists():
                            logging.info(f"Exact-rendered PDF created: {pdf_path}")
                            return True
                        logging.error(f"Failed to create exact-rendered PDF for: {url}")
                        return False
                    else:
                        # HTML renderer path; try without and then with Selenium for JS
                        pdf_path = self.pdf_creator.create_webpage_pdf(
                            url=url,
                            output_filename=filename,
                            use_selenium=False,
                            llm_optimized=llm_optimized,
                            exact_render=False
                        )
                        if pdf_path and Path(pdf_path).exists():
                            logging.info(f"Direct PDF created: {pdf_path}")
                            return True
                        logging.info("Retrying direct PDF generation with Selenium-enabled HTML fetch...")
                        pdf_path = self.pdf_creator.create_webpage_pdf(
                            url=url,
                            output_filename=filename,
                            use_selenium=True,
                            llm_optimized=llm_optimized,
                            exact_render=False
                        )
                        if pdf_path and Path(pdf_path).exists():
                            logging.info(f"Direct PDF created with Selenium content: {pdf_path}")
                            return True
                        logging.error(f"Failed to create direct PDF for: {url}")
                        return False

                except Exception as e:
                    logging.error(f"Direct PDF generation failed for {url}: {e}")
                    # Do NOT fall back to traditional scraping in direct mode
                    return False
            
            if not direct_pdf:
                # Use traditional scraping + PDF generation
                logging.info(f"Using traditional scraping for: {url}")
                
                # Scrape content
                problem_data = scraper.get_problem_statement(url)
                if not problem_data:
                    logging.error(f"Failed to scrape problem data for: {url}")
                    return False
                
                # Generate PDF
                filename = self._generate_filename(problem_data, platform)
                
                # Set the output directory for the PDF creator
                self.pdf_creator.output_dir = Path(output_dir)
                
                try:
                    output_path = self.pdf_creator.create_problem_pdf(problem_data, filename)
                    logging.info(f"Traditional PDF created: {output_path}")
                    return True
                except Exception as e:
                    logging.error(f"Failed to create traditional PDF for {url}: {e}")
                    return False
                
        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")
            return False
    
    def _generate_filename(self, problem_data: Dict, platform: str) -> str:
        """
        Generate a filename for the PDF based on problem data.
        
        Args:
            problem_data: Problem data dictionary
            platform: Platform name
            
        Returns:
            str: Generated filename
        """
        try:
            title = problem_data.get('title', 'problem')
            # Clean title for filename
            title = re.sub(r'[^\w\s-]', '', title)
            title = re.sub(r'\s+', '_', title)
            return f"{platform}_{title}.pdf"
        except:
            return f"{platform}_problem.pdf"
    
    @handle_exception
    def _handle_error(self, error: Exception, context: str = ""):
        """
        Handle application errors with comprehensive recovery mechanisms.
        
        Args:
            error: The exception that occurred
            context: Additional context information
        """
        try:
            error_msg = f"Error in {context}: {str(error)}"
            
            # Determine error type and severity
            if isinstance(error, (NetworkError, URLValidationError, PDFGenerationError, FileSystemError)):
                # Our custom errors already have detailed info
                logger.error(error_msg)
                error_reporter.report_error(error.error_info)
            else:
                # Handle other exceptions
                logging.error(error_msg)
                logging.error(traceback.format_exc())
                
                # Create error info for reporting
                from utils.error_handler import ErrorInfo, ErrorCategory, ErrorSeverity
                error_info = ErrorInfo(
                    message=error_msg,
                    category=ErrorCategory.UNKNOWN,
                    severity=ErrorSeverity.HIGH,
                    original_exception=error,
                    context={"operation": context},
                    traceback_str=traceback.format_exc()
                )
                error_reporter.report_error(error_info)
            
            # Save backup if enabled
            if self.settings.get("backup_on_error", True):
                self._create_error_backup(error, context)
            
            # Try to recover or cleanup
            self._attempt_recovery(error, context)
            
        except Exception as recovery_error:
            logging.critical(f"Error in error handler: {recovery_error}")
    
    def _create_error_backup(self, error: Exception, context: str):
        """
        Create a backup when an error occurs.
        
        Args:
            error: The exception that occurred
            context: Additional context information
        """
        try:
            backup_dir = self.config_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = str(int(time.time()))
            backup_file = backup_dir / f"error_backup_{timestamp}.json"
            
            backup_data = {
                "timestamp": timestamp,
                "error": str(error),
                "context": context,
                "settings": self.settings,
                "traceback": traceback.format_exc()
            }
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Error backup created: {backup_file}")
            
        except Exception as e:
            logging.error(f"Failed to create error backup: {e}")
    
    def _attempt_recovery(self, error: Exception, context: str):
        """
        Attempt to recover from errors.
        
        Args:
            error: The exception that occurred
            context: Additional context information
        """
        try:
            # Reset components if needed
            if "WebDriver" in str(error) or "selenium" in str(error).lower():
                logging.info("Attempting to reset WebDriver connections...")
                for scraper in self.scrapers.values():
                    if hasattr(scraper, 'driver') and scraper.driver:
                        try:
                            scraper.driver.quit()
                        except:
                            pass
                        scraper.driver = None
            
            # Other recovery mechanisms can be added here
            
        except Exception as e:
            logging.error(f"Recovery attempt failed: {e}")
    
    def shutdown(self):
        """
        Graceful shutdown of the application.
        """
        if not self.is_running:
            return
        
        logging.info("Initiating application shutdown...")
        self.is_running = False
        
        try:
            # Call shutdown handlers
            for handler in self.shutdown_handlers:
                try:
                    handler()
                except Exception as e:
                    logging.error(f"Error in shutdown handler: {e}")
            
            # Save settings
            self._save_settings()
            
            # Cleanup components
            self._cleanup()
            
            logging.info("Application shutdown completed")
            
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
    
    def _cleanup(self):
        """
        Cleanup application resources.
        """
        try:
            # Cleanup scrapers
            for scraper in self.scrapers.values():
                if hasattr(scraper, 'driver') and scraper.driver:
                    try:
                        scraper.driver.quit()
                    except:
                        pass
                
                if hasattr(scraper, 'session') and scraper.session:
                    try:
                        scraper.session.close()
                    except:
                        pass
            
            # Close any open files
            logging.info("Cleanup completed")
            
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="OJ Problem Editorial Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                          # Start GUI mode
  %(prog)s --batch urls.txt                        # Batch process URLs from file
  %(prog)s --batch urls.txt --output ./pdfs        # Batch with custom output
  %(prog)s --url "https://atcoder.jp/..."           # Process single URL
  %(prog)s --url "https://codeforces.com/..." --direct-pdf  # Direct webpage-to-PDF
  %(prog)s --batch urls.txt --direct-pdf           # Batch direct PDF download
  %(prog)s --log-level DEBUG                       # Enable debug logging
        """
    )
    
    parser.add_argument(
        '--batch', '-b',
        type=str,
        help='Batch process URLs from file (one URL per line)'
    )
    
    parser.add_argument(
        '--url', '-u',
        type=str,
        help='Process a single URL'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output directory for generated PDFs'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to custom configuration file'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (for batch processing)'
    )
    
    parser.add_argument(
        '--no-gui',
        action='store_true',
        help='Disable GUI mode (requires --batch or --url)'
    )
    
    parser.add_argument(
        '--direct-pdf',
        action='store_true',
        default=True,  # Direct PDF is default
        help='Download webpages directly as PDF (exact rendering by default)'
    )
    
    parser.add_argument(
        '--traditional-mode',
        action='store_true',
        help='Use traditional scraping mode instead of direct PDF generation'
    )
    
    parser.add_argument(
        '--llm-optimized',
        action='store_true',
        default=False,  # Disabled by default for exact look
        help='Apply LLM training optimizations to PDF output'
    )

    parser.add_argument(
        '--exact',
        dest='exact_render',
        action='store_true',
        default=True,  # Exact rendering default
        help='Use Chrome print-to-PDF for pixel-perfect output (default)'
    )

    parser.add_argument(
        '--no-exact',
        dest='exact_render',
        action='store_false',
        help='Disable exact rendering; use HTML renderer with optional LLM CSS'
    )
    
    parser.add_argument(
        '--no-llm-optimization',
        action='store_true',
        help='Disable LLM training optimizations'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    return parser.parse_args()


def main():
    """
    Main function to start the OJ Problem Editorial Downloader application.
    """
    app_manager = None
    
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Create and initialize application manager
        app_manager = ApplicationManager()
        
        # Override settings with command line arguments
        if args.log_level:
            app_manager.settings["log_level"] = args.log_level
        
        if args.output:
            app_manager.settings["output_directory"] = args.output
        
        if args.config:
            app_manager.config_file = Path(args.config)
        
        # Initialize the application
        app_manager.initialize()
        
        # Process CLI arguments for modes
        direct_pdf_mode = args.direct_pdf and not args.traditional_mode
        llm_optimized = args.llm_optimized and not args.no_llm_optimization
        exact_render = getattr(args, 'exact_render', True)
        
        # Log the mode being used
        mode_description = "traditional scraping" if not direct_pdf_mode else ("direct PDF (exact)" if exact_render else "direct PDF (HTML renderer)")
        if direct_pdf_mode and not exact_render and llm_optimized:
            mode_description += " + LLM-optimized"
        logging.info(f"Using {mode_description} mode")
        
        # Determine run mode
        if args.batch:
            # Batch processing mode
            batch_file = Path(args.batch)
            if not batch_file.exists():
                logging.error(f"Batch file not found: {batch_file}")
                sys.exit(1)
            
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f if line.strip()]
                
                if not urls:
                    logging.error("No URLs found in batch file")
                    sys.exit(1)
                
                logging.info(f"Processing {len(urls)} URLs from batch file")
                successful, failed = app_manager.run_batch_processing(
                    urls, args.output, direct_pdf=direct_pdf_mode, llm_optimized=llm_optimized, exact_render=exact_render
                )
                
                if failed > 0:
                    logging.warning(f"Some URLs failed to process: {failed}/{len(urls)}")
                    sys.exit(1)
                else:
                    logging.info("All URLs processed successfully")
                    
            except Exception as e:
                logging.error(f"Batch processing failed: {e}")
                sys.exit(1)
        
        elif args.url:
            # Single URL processing mode
            logging.info(f"Processing single URL: {args.url}")
            successful, failed = app_manager.run_batch_processing(
                [args.url], args.output, direct_pdf=direct_pdf_mode, llm_optimized=llm_optimized, exact_render=exact_render
            )
            
            if failed > 0:
                logging.error("Failed to process URL")
                sys.exit(1)
            else:
                logging.info("URL processed successfully")
        
        elif args.no_gui:
            logging.error("No-GUI mode requires --batch or --url")
            sys.exit(1)
        
        else:
            # GUI mode (default)
            logging.info("Starting GUI mode")
            app_manager.run_gui()
    
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
        if app_manager:
            app_manager.shutdown()
        sys.exit(0)
    
    except Exception as e:
        error_msg = f"Fatal application error: {e}"
        if app_manager:
            app_manager._handle_error(e, "Main Application")
            app_manager.shutdown()
        else:
            print(error_msg, file=sys.stderr)
            logging.error(error_msg)
            logging.error(traceback.format_exc())
        sys.exit(1)
    
    finally:
        # Ensure cleanup
        if app_manager:
            app_manager.shutdown()


if __name__ == "__main__":
    # Import required modules for error handling
    import time
    import re
    
    main()
