"""Main window for the OJ Problem Editorial Downloader.

This module defines a :class:`MainWindow` class that provides a Tkinter
based graphical interface for downloading problem statements and
editorials from supported online judges. The interface offers fields for
problem and editorial URLs, output directory selection, automatic
platform detection, progress feedback, logging, and several scraping
options.
"""

from __future__ import annotations

import os
import re
import threading
import traceback
from pathlib import Path
from typing import Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# Project imports
from scraper.atcoder_scraper import AtCoderScraper
from scraper.codeforces_scraper import CodeforcesScraper
from scraper.spoj_scraper import SPOJScraper
from pdf_generator.pdf_creator import PDFCreator

# Import comprehensive error handling
from utils.error_handler import (
    URLValidationError, NetworkError, ContentMissingError, CaptchaDetectedError,
    RateLimitError, PDFGenerationError, FileSystemError, handle_exception,
    error_reporter, ErrorCategory, ErrorSeverity
)
from utils.url_validator import url_validator


class MainWindow:
    """Tkinter based GUI application."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("OJ Problem Editorial Downloader")
        self.root.geometry("800x600")

        # Variables
        self.problem_url_var = tk.StringVar()
        self.editorial_url_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "output"))
        self.platform_var = tk.StringVar(value="Unknown")

        # UI state
        self.url_history: list[str] = []
        self.dark_mode = False
        self.style = ttk.Style(self.root)

        # Tools
        self.pdf_creator = PDFCreator()
        self.scrapers: Dict[str, object] = {
            "AtCoder": AtCoderScraper(),
            "Codeforces": CodeforcesScraper(),
            "SPOJ": SPOJScraper(),
        }

        # Build UI
        self._build_menu()
        self._build_widgets()
        self._center_window()
        self._bind_shortcuts()

    # ------------------------------------------------------------------
    # UI setup
    def _build_menu(self) -> None:
        """Create the application menu bar."""

        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Batch Process", command=self._open_batch_dialog, accelerator="Ctrl+B"
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Theme", command=self._toggle_theme)
        menubar.add_cascade(label="View", menu=view_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Preferences", command=self._show_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_widgets(self) -> None:
        """Create all Tkinter widgets for the main window."""

        main = ttk.Frame(self.root, padding=10)
        main.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        # Problem URL ---------------------------------------------------
        ttk.Label(main, text="Problem URL:").grid(row=0, column=0, sticky="w")
        self.problem_combo = ttk.Combobox(
            main, textvariable=self.problem_url_var, values=self.url_history
        )
        self.problem_combo.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)
        self.problem_combo.bind("<KeyRelease>", self._on_problem_change)
        self.problem_combo.bind("<<ComboboxSelected>>", self._on_problem_change)
        self.url_feedback = ttk.Label(main, text="", foreground="red")
        self.url_feedback.grid(row=1, column=1, columnspan=2, sticky="w")

        # Editorial URL -------------------------------------------------
        ttk.Label(main, text="Editorial URL (optional):").grid(row=2, column=0, sticky="w")
        self.editorial_entry = ttk.Entry(main, textvariable=self.editorial_url_var)
        self.editorial_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=2)

        # Output directory ----------------------------------------------
        ttk.Label(main, text="Output Directory:").grid(row=3, column=0, sticky="w")
        ttk.Entry(main, textvariable=self.output_dir_var).grid(
            row=3, column=1, sticky="ew", pady=2
        )
        ttk.Button(main, text="Browse", command=self._browse_output).grid(
            row=3, column=2, padx=5, pady=2
        )

        # Platform display ----------------------------------------------
        platform_frame = ttk.Frame(main)
        platform_frame.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(platform_frame, text="Platform:").pack(side="left")
        ttk.Label(platform_frame, textvariable=self.platform_var, foreground="blue").pack(
            side="left"
        )

        # Action buttons -------------------------------------------------
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=10)
        ttk.Button(
            btn_frame, text="Scrape Problem", command=lambda: self._start_scrape("problem")
        ).grid(row=0, column=0, padx=5)
        ttk.Button(
            btn_frame, text="Scrape Editorial", command=lambda: self._start_scrape("editorial")
        ).grid(row=0, column=1, padx=5)
        ttk.Button(
            btn_frame, text="Scrape Both", command=lambda: self._start_scrape("both")
        ).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="Batch", command=self._open_batch_dialog).grid(
            row=0, column=3, padx=5
        )
        ttk.Button(btn_frame, text="Clear", command=self.clear_fields).grid(
            row=0, column=4, padx=5
        )

        # Progress bar --------------------------------------------------
        self.progress_bar = ttk.Progressbar(main, mode="indeterminate")
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky="ew")

        # Log text area -------------------------------------------------
        ttk.Label(main, text="Log:").grid(row=7, column=0, columnspan=3, sticky="w")
        self.log_text = scrolledtext.ScrolledText(main, height=10, state="disabled")
        self.log_text.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(0, 10))

        main.rowconfigure(8, weight=1)

    def _center_window(self) -> None:
        """Center the window on the screen."""

        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------
    # Utility methods
    def _browse_output(self) -> None:
        """Open a dialog to select an output directory."""

        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)

    def _detect_platform(self, _event: Optional[tk.Event] = None) -> None:
        """Detect platform from the problem URL and update the label."""

        url = self.problem_url_var.get().strip()
        platform = "Unknown"
        for name, scraper in self.scrapers.items():
            if scraper.is_valid_url(url):
                platform = name
                break
        self.platform_var.set(platform)

    def _on_problem_change(self, _event: Optional[tk.Event] = None) -> None:
        """Handle problem URL edits."""

        self._detect_platform()
        self._validate_problem_url()

    def _validate_problem_url(self) -> bool:
        """Validate the current problem URL and update feedback label."""

        url = self.problem_url_var.get().strip()
        valid = bool(re.match(r"^https?://", url)) and any(
            scraper.is_valid_url(url) for scraper in self.scrapers.values()
        )
        if not url:
            self.url_feedback.config(text="")
        elif valid:
            self.url_feedback.config(text="Valid URL", foreground="green")
        else:
            self.url_feedback.config(text="Invalid URL", foreground="red")
        return valid

    def _store_history(self, url: str) -> None:
        """Store URL in history dropdown."""

        if url and url not in self.url_history:
            self.url_history.insert(0, url)
            self.url_history = self.url_history[:10]
            self.problem_combo["values"] = self.url_history

    def _bind_shortcuts(self) -> None:
        """Bind common keyboard shortcuts."""

        self.root.bind("<Control-s>", lambda _e: self._start_scrape("both"))
        self.root.bind("<Control-b>", lambda _e: self._open_batch_dialog())
        self.root.bind("<Control-n>", lambda _e: self.clear_fields())
        self.root.bind("<Control-q>", lambda _e: self.root.quit())

    def _toggle_theme(self) -> None:
        """Toggle between light and dark themes."""

        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.style.theme_use("clam")
            self.style.configure(".", background="#2e2e2e", foreground="white")
            self.style.configure("TFrame", background="#2e2e2e")
            self.style.configure("TLabel", background="#2e2e2e", foreground="white")
            self.style.configure("TEntry", fieldbackground="#4d4d4d", foreground="white")
        else:
            self.style.theme_use("default")
            self.style.configure(".", background="SystemButtonFace", foreground="black")
            self.style.configure("TFrame", background="SystemButtonFace")
            self.style.configure("TLabel", background="SystemButtonFace", foreground="black")
            self.style.configure("TEntry", fieldbackground="white", foreground="black")

    def _open_batch_dialog(self) -> None:
        """Open dialog to input multiple URLs."""

        win = tk.Toplevel(self.root)
        win.title("Batch URLs")
        text = scrolledtext.ScrolledText(win, width=60, height=15)
        text.pack(fill="both", expand=True, padx=5, pady=5)

        def start() -> None:
            urls = [u.strip() for u in text.get("1.0", tk.END).splitlines() if u.strip()]
            win.destroy()
            self._start_batch_scrape(urls)

        ttk.Button(win, text="Start", command=start).pack(pady=5)

    def _start_batch_scrape(self, urls: list[str]) -> None:
        threading.Thread(target=self._scrape_batch, args=(urls,), daemon=True).start()

    def _scrape_batch(self, urls: list[str]) -> None:
        for url in urls:
            self.problem_url_var.set(url)
            self.editorial_url_var.set("")
            self._scrape("both")

    def _show_preview(
        self,
        problem_data: Dict[str, object],
        editorial_data: Dict[str, object],
        scrape_type: str,
        url: str,
        has_errors: bool = False,
    ) -> None:
        """Display scraped content and allow saving to PDF with error handling."""

        win = tk.Toplevel(self.root)
        win.title("Content Preview")
        win.geometry("900x700")
        
        # Add error indicator if there were issues
        if has_errors:
            error_frame = ttk.Frame(win)
            error_frame.pack(fill="x", padx=5, pady=5)
            ttk.Label(error_frame, text="⚠️ Some errors occurred during scraping. Content may be incomplete.", 
                     foreground="orange").pack()
        
        # Main content area
        text_frame = ttk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        text = scrolledtext.ScrolledText(text_frame, width=80, height=25, wrap=tk.WORD)
        text.pack(fill="both", expand=True)
        
        # Build content preview
        content = ""
        if problem_data:
            content += "=== PROBLEM DATA ===\n"
            if problem_data.get('error_occurred'):
                content += f"⚠️ Error: {problem_data.get('error_message', 'Unknown error')}\n\n"
            else:
                content += f"Title: {problem_data.get('title', 'N/A')}\n"
                content += f"Platform: {problem_data.get('platform', 'N/A')}\n\n"
                content += f"Statement: {str(problem_data.get('problem_statement', 'N/A'))[:500]}...\n\n"
                if problem_data.get('examples'):
                    content += f"Examples: {len(problem_data.get('examples', []))} found\n\n"
        
        if editorial_data:
            content += "\n=== EDITORIAL DATA ===\n"
            if editorial_data.get('error_occurred'):
                content += f"⚠️ Error: {editorial_data.get('error_message', 'Unknown error')}\n\n"
            else:
                content += f"Title: {editorial_data.get('title', 'N/A')}\n"
                content += f"Content: {str(editorial_data.get('problem_statement', 'N/A'))[:500]}...\n\n"
        
        if not content:
            content = "No content available to preview."
        
        text.insert("1.0", content)
        text.configure(state="disabled")

        # Button frame
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)

        def save_pdf() -> None:
            """Save content to PDF with error handling."""
            try:
                self._log("Generating PDF...")
                
                # Validate that we have some content
                if not problem_data and not editorial_data:
                    self._show_error_dialog("No Content", "No content available to save as PDF.")
                    return
                
                # Generate PDF based on available content
                pdf_path = ""
                try:
                    if scrape_type == "problem" and problem_data:
                        pdf_path = self.pdf_creator.create_problem_pdf(problem_data)
                    elif scrape_type == "editorial" and editorial_data:
                        pdf_path = self.pdf_creator.create_editorial_pdf(editorial_data)
                    elif scrape_type == "both":
                        if problem_data and editorial_data:
                            pdf_path = self.pdf_creator.create_combined_pdf(problem_data, editorial_data)
                        elif problem_data:
                            pdf_path = self.pdf_creator.create_problem_pdf(problem_data)
                        elif editorial_data:
                            pdf_path = self.pdf_creator.create_editorial_pdf(editorial_data)
                        else:
                            raise PDFGenerationError("No valid content available for PDF generation")
                    else:
                        raise PDFGenerationError("No matching content for the requested scrape type")
                    
                    self._log(f"PDF saved: {pdf_path}")
                    
                    # Show success message
                    success_msg = f"PDF saved successfully:\n{pdf_path}"
                    if has_errors:
                        success_msg += "\n\n⚠️ Note: PDF was generated despite some scraping errors."
                    
                    messagebox.showinfo("Success", success_msg)
                    self._store_history(url)
                    win.destroy()
                    
                except PDFGenerationError as e:
                    self._log(f"PDF generation error: {e}")
                    self._show_error_dialog("PDF Generation Failed", 
                        e.error_info.user_message or str(e))
                except FileSystemError as e:
                    self._log(f"File system error during PDF generation: {e}")
                    self._show_error_dialog("File System Error", 
                        e.error_info.user_message or str(e))
                except Exception as e:
                    self._log(f"Unexpected error during PDF generation: {e}")
                    self._show_error_dialog("PDF Generation Error", 
                        f"An unexpected error occurred while generating the PDF: {str(e)}")
                    
            except Exception as e:
                self._log(f"Error in save_pdf: {e}")
                self._show_error_dialog("Error", f"An error occurred: {str(e)}")

        ttk.Button(btn_frame, text="Save PDF", command=save_pdf).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side="left", padx=5)
        
        # Add error summary button if there were errors
        if has_errors:
            def show_error_summary():
                summary = error_reporter.get_error_summary()
                summary_text = f"Total errors: {summary['total_errors']}\n\n"
                summary_text += "Error categories:\n"
                for category, count in summary.get('categories', {}).items():
                    summary_text += f"  • {category}: {count}\n"
                
                if summary.get('recent_errors'):
                    summary_text += "\nRecent errors:\n"
                    for error in summary['recent_errors'][-3:]:
                        summary_text += f"  • {error['message']}\n"
                
                self._show_error_dialog("Error Summary", summary_text)
            
            ttk.Button(btn_frame, text="Error Details", command=show_error_summary).pack(side="left", padx=5)
    
    def _show_error_dialog(self, title: str, message: str) -> None:
        """Show user-friendly error dialog with detailed information."""
        try:
            # Create custom error dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            
            # Error message
            text_frame = ttk.Frame(dialog)
            text_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=12)
            text_widget.pack(fill="both", expand=True)
            text_widget.insert("1.0", message)
            text_widget.configure(state="disabled")
            
            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=10)
            
            ttk.Button(btn_frame, text="OK", command=dialog.destroy).pack(side="left", padx=5)
            
            def copy_to_clipboard():
                dialog.clipboard_clear()
                dialog.clipboard_append(message)
                
            ttk.Button(btn_frame, text="Copy to Clipboard", command=copy_to_clipboard).pack(side="left", padx=5)
            
        except Exception as e:
            # Fallback to simple messagebox if custom dialog fails
            messagebox.showerror(title, message)

    def _log(self, message: str) -> None:
        """Append a message to the log text area."""

        def append() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")

        self.root.after(0, append)

    def _set_progress(self, running: bool) -> None:
        """Start or stop the progress bar."""

        def update() -> None:
            if running:
                self.progress_bar.start()
            else:
                self.progress_bar.stop()

        self.root.after(0, update)

    def _get_scraper(self, url: str):
        """Return a scraper instance suitable for the given URL."""

        for name, scraper in self.scrapers.items():
            if scraper.is_valid_url(url):
                self.platform_var.set(name)
                return scraper
        return None

    # ------------------------------------------------------------------
    # Scraping logic
    def _start_scrape(self, scrape_type: str) -> None:
        """Start scraping in a separate thread."""

        threading.Thread(target=self._scrape, args=(scrape_type,), daemon=True).start()

    @handle_exception
    def _scrape(self, scrape_type: str) -> None:
        """
        Perform the scraping operation with comprehensive error handling.
        """
        self._set_progress(True)
        error_occurred = False
        
        try:
            problem_url = self.problem_url_var.get().strip()
            editorial_url = self.editorial_url_var.get().strip()
            output_dir = self.output_dir_var.get().strip()

            # Validate inputs
            if not problem_url:
                raise URLValidationError("Problem URL is required", problem_url)
            
            # Validate problem URL
            url_info = url_validator.validate_url(problem_url)
            if not url_info.is_valid:
                error_msg = url_info.error_message or "Invalid URL format"
                suggestions = url_validator.suggest_corrections(problem_url)
                if suggestions:
                    error_msg += f"\n\nSuggested corrections:\n" + "\n".join(f"• {s}" for s in suggestions[:3])
                raise URLValidationError(error_msg, problem_url)

            # Get appropriate scraper
            scraper = self._get_scraper(problem_url)
            if not scraper:
                raise URLValidationError("Unsupported platform or invalid URL format", problem_url)

            # Validate and create output directory
            try:
                os.makedirs(output_dir, exist_ok=True)
                self.pdf_creator.output_dir = Path(output_dir)
            except PermissionError:
                raise FileSystemError(f"Permission denied: Cannot create output directory {output_dir}", output_dir)
            except OSError as e:
                raise FileSystemError(f"Cannot create output directory {output_dir}: {str(e)}", output_dir, e)

            problem_data: Dict[str, object] = {}
            editorial_data: Dict[str, object] = {}

            # Scrape problem with error handling
            if scrape_type in {"problem", "both"}:
                try:
                    self._log("Scraping problem...")
                    problem_data = scraper.safe_get_problem_statement(problem_url)
                    
                    if not problem_data or problem_data.get('error_occurred'):
                        error_msg = problem_data.get('error_message', 'Unknown error') if problem_data else 'No data returned'
                        self._log(f"Problem scraping failed: {error_msg}")
                        error_occurred = True
                    else:
                        self._log("Problem scraped successfully")
                        
                except CaptchaDetectedError as e:
                    self._log(f"CAPTCHA detected: {e.error_info.user_message}")
                    self._show_error_dialog("CAPTCHA Detected", 
                        "CAPTCHA detected on the website. Please try again later or access the site manually first.")
                    return
                except RateLimitError as e:
                    retry_after = e.error_info.context.get('retry_after', 60)
                    self._log(f"Rate limited: Please wait {retry_after} seconds")
                    self._show_error_dialog("Rate Limited", 
                        f"Too many requests. Please wait {retry_after} seconds before trying again.")
                    return
                except NetworkError as e:
                    self._log(f"Network error: {e.error_info.user_message or str(e)}")
                    error_occurred = True
                except ContentMissingError as e:
                    self._log(f"Content not found: {e.error_info.user_message or str(e)}")
                    error_occurred = True

            # Scrape editorial with error handling
            if scrape_type in {"editorial", "both"}:
                try:
                    if not editorial_url:
                        if problem_data and "editorial_url" in problem_data:
                            editorial_url = str(problem_data["editorial_url"])
                            self._log(f"Using detected editorial URL: {editorial_url}")
                        else:
                            self._log("No editorial URL provided and none could be detected")
                            if scrape_type == "editorial":
                                raise URLValidationError("Editorial URL is required", editorial_url)
                            # For "both", continue without editorial
                            editorial_url = None

                    if editorial_url:
                        self._log("Scraping editorial...")
                        editorial_data = scraper.safe_get_editorial(editorial_url)
                        
                        if not editorial_data or editorial_data.get('error_occurred'):
                            error_msg = editorial_data.get('error_message', 'Unknown error') if editorial_data else 'No data returned'
                            self._log(f"Editorial scraping failed: {error_msg}")
                            error_occurred = True
                        else:
                            self._log("Editorial scraped successfully")
                            
                except Exception as e:
                    self._log(f"Editorial scraping error: {str(e)}")
                    error_occurred = True

            # Show preview with error indication
            if problem_data or editorial_data:
                if error_occurred:
                    self._log("Some errors occurred during scraping, but partial content is available")
                
                self.root.after(
                    0,
                    lambda: self._show_preview(
                        problem_data, editorial_data, scrape_type, problem_url, error_occurred
                    ),
                )
            else:
                self._show_error_dialog("Scraping Failed", 
                    "No content could be scraped. Please check the URL and try again.")

        except URLValidationError as e:
            self._log(f"URL validation error: {e}")
            self._show_error_dialog("Invalid URL", str(e))
        except FileSystemError as e:
            self._log(f"File system error: {e}")
            self._show_error_dialog("File System Error", e.error_info.user_message or str(e))
        except Exception as e:
            self._log(f"Unexpected error: {e}")
            self._show_error_dialog("Unexpected Error", 
                f"An unexpected error occurred: {str(e)}\n\nPlease check the logs for more details.")
            error_reporter.report_error(None, {"operation": "scrape", "error": str(e), "traceback": traceback.format_exc()})
        finally:
            self._set_progress(False)

    # ------------------------------------------------------------------
    # Miscellaneous callbacks
    def clear_fields(self) -> None:
        """Clear all input fields and the log."""

        self.problem_url_var.set("")
        self.editorial_url_var.set("")
        self.platform_var.set("Unknown")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def _show_settings(self) -> None:
        """Display settings dialog for PDF options."""

        win = tk.Toplevel(self.root)
        win.title("Settings")
        ttk.Label(win, text="Base Font Size:").grid(row=0, column=0, sticky="w")
        font_var = tk.IntVar(value=self.pdf_creator.base_font_size)
        ttk.Spinbox(win, from_=6, to=20, textvariable=font_var).grid(
            row=0, column=1, pady=2
        )
        ttk.Label(win, text="Body Font:").grid(row=1, column=0, sticky="w")
        body_var = tk.StringVar(value=self.pdf_creator.body_font)
        ttk.Entry(win, textvariable=body_var).grid(row=1, column=1, pady=2)

        def save() -> None:
            self.pdf_creator.base_font_size = font_var.get()
            self.pdf_creator.body_font = body_var.get()
            self.pdf_creator._setup_custom_styles()
            win.destroy()

        ttk.Button(win, text="Save", command=save).grid(row=2, column=0, columnspan=2, pady=5)

    def _show_about(self) -> None:
        """Show application information."""

        messagebox.showinfo(
            "About",
            "OJ Problem Editorial Downloader\n\n"
            "Usage:\n"
            "1. Enter problem URL and optional editorial URL.\n"
            "2. Use scrape buttons or Ctrl+S to start.\n"
            "3. Batch process via File -> Batch Process.\n"
            "4. Adjust PDF options in Settings.",
        )

    def run(self) -> None:
        """Start the Tkinter event loop."""

        self.root.mainloop()

    def __del__(self) -> None:  # pragma: no cover - cleanup
        for scraper in self.scrapers.values():
            if hasattr(scraper, "close_driver"):
                scraper.close_driver()


__all__ = ["MainWindow"]

