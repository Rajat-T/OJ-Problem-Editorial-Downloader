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
from pathlib import Path
from typing import Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# Project imports
from scraper.atcoder_scraper import AtCoderScraper
from scraper.codeforces_scraper import CodeforcesScraper
from scraper.spoj_scraper import SPOJScraper
from pdf_generator.pdf_creator import PDFCreator


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
    ) -> None:
        """Display scraped content and allow saving to PDF."""

        win = tk.Toplevel(self.root)
        win.title("Preview")
        text = scrolledtext.ScrolledText(win, width=80, height=25)
        text.pack(fill="both", expand=True)
        content = ""
        if problem_data:
            content += str(problem_data.get("content", "")) + "\n"
        if editorial_data:
            content += "\n=== Editorial ===\n" + str(editorial_data.get("content", ""))
        text.insert("1.0", content)
        text.configure(state="disabled")

        btn = ttk.Frame(win)
        btn.pack(pady=5)

        def save_pdf() -> None:
            pdf_path = ""
            if scrape_type == "problem":
                pdf_path = self.pdf_creator.create_problem_pdf(problem_data)
            elif scrape_type == "editorial":
                pdf_path = self.pdf_creator.create_editorial_pdf(editorial_data)
            else:
                pdf_path = self.pdf_creator.create_combined_pdf(problem_data, editorial_data)
            self._log(f"PDF saved: {pdf_path}")
            messagebox.showinfo("Success", f"PDF saved to:\n{pdf_path}")
            self._store_history(url)
            win.destroy()

        ttk.Button(btn, text="Save PDF", command=save_pdf).pack(side="left", padx=5)
        ttk.Button(btn, text="Close", command=win.destroy).pack(side="left", padx=5)

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

    def _scrape(self, scrape_type: str) -> None:
        """Perform the scraping operation."""

        self._set_progress(True)
        try:
            problem_url = self.problem_url_var.get().strip()
            editorial_url = self.editorial_url_var.get().strip()
            output_dir = self.output_dir_var.get().strip()

            if not problem_url:
                raise ValueError("Problem URL is required")

            scraper = self._get_scraper(problem_url)
            if not scraper:
                raise ValueError("Unsupported problem URL")

            os.makedirs(output_dir, exist_ok=True)
            self.pdf_creator.output_dir = Path(output_dir)

            problem_data: Dict[str, object] = {}
            editorial_data: Dict[str, object] = {}

            if scrape_type in {"problem", "both"}:
                self._log("Scraping problem...")
                problem_data = scraper.extract_problem_info(problem_url)
                if not problem_data:
                    raise ValueError("Failed to scrape problem data")
                self._log("Problem scraped successfully")

            if scrape_type in {"editorial", "both"}:
                if not editorial_url:
                    if problem_data and "editorial_url" in problem_data:
                        editorial_url = str(problem_data["editorial_url"])
                        self._log(f"Detected editorial URL: {editorial_url}")
                    else:
                        raise ValueError("Editorial URL is required")

                self._log("Scraping editorial...")
                editorial_data = scraper.extract_editorial_info(editorial_url)
                if not editorial_data:
                    raise ValueError("Failed to scrape editorial data")
                self._log("Editorial scraped successfully")

            # Preview before saving --------------------------------------
            self.root.after(
                0,
                lambda: self._show_preview(
                    problem_data, editorial_data, scrape_type, problem_url
                ),
            )

        except Exception as exc:  # noqa: BLE001
            self._log(f"Error: {exc}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(exc)))
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

