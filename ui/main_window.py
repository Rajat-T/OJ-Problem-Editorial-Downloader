"""
Main Window for OJ Problem Editorial Downloader
Provides graphical user interface using tkinter
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Import project modules
from utils.url_parser import URLParser
from utils.file_manager import FileManager
from scraper.atcoder_scraper import AtCoderScraper
from scraper.codeforces_scraper import CodeforcesScraper
from scraper.spoj_scraper import SPOJScraper
from pdf_generator.pdf_creator import PDFCreator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MainWindow:
    """
    Main application window for OJ Problem Editorial Downloader
    """
    
    def __init__(self):
        """
        Initialize the main window
        """
        self.root = tk.Tk()
        self.root.title("OJ Problem Editorial Downloader")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # Initialize components
        self.url_parser = URLParser()
        self.file_manager = FileManager()
        self.pdf_creator = PDFCreator()
        
        # Scrapers
        self.scrapers = {
            'AtCoder': AtCoderScraper(),
            'Codeforces': CodeforcesScraper(),
            'SPOJ': SPOJScraper()
        }
        
        # Variables
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "output"))
        self.current_url = tk.StringVar()
        self.download_type = tk.StringVar(value="both")  # problem, editorial, both
        self.headless_mode = tk.BooleanVar(value=True)
        
        # Setup GUI
        self._setup_gui()
        
        # Center the window
        self._center_window()
    
    def _center_window(self):
        """
        Center the window on screen
        """
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _setup_gui(self):
        """
        Setup the graphical user interface
        """
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="OJ Problem Editorial Downloader", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # URL input section
        url_frame = ttk.LabelFrame(main_frame, text="URL Input", padding="10")
        url_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        url_frame.columnconfigure(1, weight=1)
        
        ttk.Label(url_frame, text="Problem/Editorial URL:").grid(row=0, column=0, sticky=tk.W)
        self.url_entry = ttk.Entry(url_frame, textvariable=self.current_url, width=50)
        self.url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        
        validate_btn = ttk.Button(url_frame, text="Validate URL", command=self._validate_url)
        validate_btn.grid(row=0, column=2, padx=(5, 0))
        
        # URL status
        self.url_status = ttk.Label(url_frame, text="", foreground="gray")
        self.url_status.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
        # Download options section
        options_frame = ttk.LabelFrame(main_frame, text="Download Options", padding="10")
        options_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(options_frame, text="Download Type:").grid(row=0, column=0, sticky=tk.W)
        
        type_frame = ttk.Frame(options_frame)
        type_frame.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Radiobutton(type_frame, text="Problem Only", variable=self.download_type, 
                       value="problem").grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(type_frame, text="Editorial Only", variable=self.download_type, 
                       value="editorial").grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        ttk.Radiobutton(type_frame, text="Both (Combined PDF)", variable=self.download_type, 
                       value="both").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        
        # Browser options
        ttk.Checkbutton(options_frame, text="Headless Browser Mode", 
                       variable=self.headless_mode).grid(row=1, column=0, columnspan=3, 
                                                        sticky=tk.W, pady=(10, 0))
        
        # Output directory section
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="10")
        output_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        output_frame.columnconfigure(1, weight=1)
        
        ttk.Label(output_frame, text="Output Directory:").grid(row=0, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_dir, width=50)
        self.output_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        
        browse_btn = ttk.Button(output_frame, text="Browse", command=self._browse_output_dir)
        browse_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Action buttons section
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=4, column=0, columnspan=3, pady=(0, 10))
        
        self.download_btn = ttk.Button(action_frame, text="Download & Generate PDF", 
                                      command=self._start_download, state="disabled")
        self.download_btn.grid(row=0, column=0, padx=(0, 10))
        
        clear_btn = ttk.Button(action_frame, text="Clear", command=self._clear_form)
        clear_btn.grid(row=0, column=1, padx=(0, 10))
        
        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=0, column=0, sticky=tk.W)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Log section
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state='disabled')
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Clear log button
        clear_log_btn = ttk.Button(log_frame, text="Clear Log", command=self._clear_log)
        clear_log_btn.grid(row=1, column=0, pady=(5, 0))
    
    def _validate_url(self):
        """
        Validate the entered URL
        """
        url = self.current_url.get().strip()
        if not url:
            self.url_status.config(text="Please enter a URL", foreground="red")
            self.download_btn.config(state="disabled")
            return
        
        # Check which platform supports this URL
        supported_platform = None
        for platform, scraper in self.scrapers.items():
            if scraper.is_valid_url(url):
                supported_platform = platform
                break
        
        if supported_platform:
            self.url_status.config(text=f"✓ Valid {supported_platform} URL", foreground="green")
            self.download_btn.config(state="normal")
            self._log(f"URL validated for {supported_platform}")
        else:
            self.url_status.config(text="✗ Unsupported URL format", foreground="red")
            self.download_btn.config(state="disabled")
            self._log("Invalid or unsupported URL format")
    
    def _browse_output_dir(self):
        """
        Browse for output directory
        """
        directory = filedialog.askdirectory(initialdir=self.output_dir.get())
        if directory:
            self.output_dir.set(directory)
            self._log(f"Output directory set to: {directory}")
    
    def _clear_form(self):
        """
        Clear the form fields
        """
        self.current_url.set("")
        self.url_status.config(text="")
        self.download_btn.config(state="disabled")
        self.progress_var.set("Ready")
        self._log("Form cleared")
    
    def _clear_log(self):
        """
        Clear the log text
        """
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
    
    def _log(self, message: str):
        """
        Add message to log
        
        Args:
            message (str): Message to log
        """
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        logger.info(message)
    
    def _start_download(self):
        """
        Start the download process in a separate thread
        """
        # Disable the download button
        self.download_btn.config(state="disabled")
        self.progress_bar.start()
        self.progress_var.set("Starting download...")
        
        # Start download in separate thread
        thread = threading.Thread(target=self._download_worker)
        thread.daemon = True
        thread.start()
    
    def _download_worker(self):
        """
        Worker function for downloading and generating PDF
        """
        try:
            url = self.current_url.get().strip()
            download_type = self.download_type.get()
            output_dir = self.output_dir.get()
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            self.pdf_creator.output_dir = Path(output_dir)
            
            # Find appropriate scraper
            scraper = None
            platform = None
            for platform_name, scraper_instance in self.scrapers.items():
                if scraper_instance.is_valid_url(url):
                    scraper = scraper_instance
                    platform = platform_name
                    break
            
            if not scraper:
                raise ValueError("No suitable scraper found for URL")
            
            # Update scraper settings
            scraper.headless = self.headless_mode.get()
            
            self._update_progress("Extracting data...")
            
            problem_data = {}
            editorial_data = {}
            
            # Extract based on download type
            if download_type in ["problem", "both"]:
                self._log(f"Extracting problem data from {platform}...")
                problem_data = scraper.extract_problem_info(url)
                if not problem_data:
                    raise ValueError("Failed to extract problem data")
                self._log("Problem data extracted successfully")
            
            if download_type in ["editorial", "both"]:
                self._log(f"Extracting editorial data from {platform}...")
                
                # For problem URLs, try to find editorial URL
                if download_type == "both" and "editorial_url" in problem_data:
                    editorial_url = problem_data["editorial_url"]
                    self._log(f"Using editorial URL: {editorial_url}")
                else:
                    editorial_url = url
                
                editorial_data = scraper.extract_editorial_info(editorial_url)
                if not editorial_data:
                    self._log("Warning: Failed to extract editorial data")
                else:
                    self._log("Editorial data extracted successfully")
            
            self._update_progress("Generating PDF...")
            
            # Generate PDF based on type
            pdf_path = ""
            if download_type == "problem":
                pdf_path = self.pdf_creator.create_problem_pdf(problem_data)
            elif download_type == "editorial":
                pdf_path = self.pdf_creator.create_editorial_pdf(editorial_data)
            elif download_type == "both":
                if editorial_data:
                    pdf_path = self.pdf_creator.create_combined_pdf(problem_data, editorial_data)
                else:
                    # Fall back to problem only
                    pdf_path = self.pdf_creator.create_problem_pdf(problem_data)
                    self._log("Generated problem PDF only (editorial not available)")
            
            self._update_progress("Complete!")
            self._log(f"PDF generated successfully: {pdf_path}")
            
            # Show success message
            self.root.after(0, lambda: messagebox.showinfo("Success", 
                f"PDF generated successfully!\n\nFile: {pdf_path}"))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self._log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        
        finally:
            # Re-enable controls
            self.root.after(0, self._download_complete)
    
    def _update_progress(self, message: str):
        """
        Update progress message
        
        Args:
            message (str): Progress message
        """
        self.root.after(0, lambda: self.progress_var.set(message))
        self._log(message)
    
    def _download_complete(self):
        """
        Called when download is complete
        """
        self.progress_bar.stop()
        self.download_btn.config(state="normal")
        self.progress_var.set("Ready")
    
    def run(self):
        """
        Start the GUI application
        """
        self._log("OJ Problem Editorial Downloader started")
        self._log("Supported platforms: AtCoder, Codeforces, SPOJ")
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._log("Application interrupted by user")
        finally:
            # Cleanup
            for scraper in self.scrapers.values():
                if hasattr(scraper, 'close_driver'):
                    scraper.close_driver()
    
    def __del__(self):
        """
        Cleanup when object is destroyed
        """
        # Cleanup scrapers
        for scraper in self.scrapers.values():
            if hasattr(scraper, 'close_driver'):
                scraper.close_driver()